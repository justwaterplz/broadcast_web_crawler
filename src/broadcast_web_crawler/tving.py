"""Single-program TVING metadata probe, usable from Python services or the CLI."""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from broadcast_web_crawler.metadata import program_metadata
from broadcast_web_crawler.tving_storage import BUNDLE_FILENAME, make_bundle, write_bundle


class TvingError(RuntimeError):
    """The page format, HTTP response, or API response cannot be used."""


def _program_code(value: str) -> str:
    if not re.fullmatch(r"P[0-9]+", value):
        raise ValueError("program_code must be a TVING program ID such as P001790587")
    return value


def normalize_content_url(value: str) -> tuple[str, str]:
    """Validate a TVING detail URL and discard tracking queries/fragments."""
    parts = urlsplit(value.strip())
    if (
        parts.scheme != "https"
        or parts.netloc.lower() not in {"www.tving.com", "tving.com"}
    ):
        raise ValueError("Enter an HTTPS TVING detail URL")
    match = re.fullmatch(r"/contents/([PE][0-9]+)/?", parts.path)
    if match is None:
        raise ValueError("Expected a URL such as https://www.tving.com/contents/P001790587")
    code = match[1]
    return f"https://www.tving.com/contents/{code}", code


def _without_images(value: Any) -> Any:
    """Exclude image fields throughout program, JSON-LD, and clip metadata."""
    if isinstance(value, dict):
        return {
            key: _without_images(item) for key, item in value.items()
            if "image" not in key.lower() and "thumbnail" not in key.lower()
        }
    if isinstance(value, list):
        return [_without_images(item) for item in value]
    return value


def _get_text(url: str) -> str:
    try:
        request = Request(url, headers={"User-Agent": "broadcast-metadata-probe/0.1"})
        with urlopen(request, timeout=30) as response:
            # Bound each response to keep this probe small.
            raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                raise TvingError("Response exceeds the 10 MB probe limit")
            return raw.decode(response.headers.get_content_charset() or "utf-8")
    except URLError as exc:
        # Do not expose query strings containing the public application key.
        raise TvingError(f"HTTP request failed for {urlsplit(url).path}") from exc


def parse_detail_raw(html: str) -> dict[str, Any]:
    """Read program metadata without renaming, filtering or converting values."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if script is None:
        raise TvingError("Missing __NEXT_DATA__; inspect the current page format")
    try:
        props = json.loads(script.get_text())["props"]["pageProps"]
        info = props["contentInfo"]
        if not isinstance(info, dict) or not info.get("program_code"):
            raise TvingError("Missing program metadata")
        json_ld = [json.loads(tag.get_text()) for tag in soup.find_all(
            "script", attrs={"type": "application/ld+json"}
        )]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise TvingError("Invalid detail metadata") from exc
    return {
        "content_info": info,
        "json_ld": json_ld,
        "pre_release_clips": props.get("preReleaseClipInfo"),
        "content_clips": props.get("contentClipInfo"),
    }


def parse_detail(html: str) -> dict[str, Any]:
    """Build the existing display projection; raw snapshots are saved separately."""
    raw = parse_detail_raw(html)
    return _without_images({
        **raw,
        "pre_release_clips": raw["pre_release_clips"] or [],
        "missing_or_empty_content_info_fields": [
            name for name, value in raw["content_info"].items() if value is None or value == ""
        ],
    })


def extract_public_client_key(script: str) -> str:
    """Read the anonymous web client's application key, never session tokens."""
    module = re.search(r"46900:function.{0,1500}", script, re.DOTALL)
    config = module.group() if module else ""
    exported = re.search(r"q1:function\(\)\{return (\w+)\}", config)
    variable = exported[1] if exported else "b"  # Older public bundles used b.
    match = re.search(r'\b' + re.escape(variable) + r'="([^\"]+)"', config)
    if match is None or match[1].startswith(("http:", "https:")):
        raise TvingError("Public client configuration changed; inspect the current bundle")
    return match[1]


def parse_episodes(payload: dict[str, Any], program_code: str) -> dict[str, Any]:
    """Check API status and retain completeness separately from the episode rows."""
    _program_code(program_code)
    header = payload.get("header") or {}
    body = payload.get("body")
    if header.get("status") != 200 or not isinstance(body, dict):
        raise TvingError(f"TVING API status {header.get('status')}; no usable episode list")
    rows = body.get("result")
    if not isinstance(rows, list):
        raise TvingError("Missing episode result list")
    episodes = []
    for row in rows:
        episode = row["episode"]
        episodes.append({
            "program_code": program_code,
            "program_name": row.get("program", {}).get("name", {}).get("ko"),
            "episode_code": episode["code"],
            "episode_number": episode.get("frequency"),
            "title": row.get("vod_name", {}).get("ko"),
            "synopsis": (episode.get("synopsis") or {}).get("ko"),
            "broadcast_date_raw": episode.get("broadcast_date"),
            "duration_seconds": episode.get("duration"),
            "grade_code": episode.get("grade_code"),
            "free_yn": episode.get("free_yn"),
        })
    unique_codes = {episode["episode_code"] for episode in episodes}
    return {
        "api_status": header["status"],
        "total_count": body.get("total_count"),
        "has_more": body.get("has_more"),
        "collected_count": len(episodes),
        "complete_for_current_api_listing": (
            body.get("has_more") == "N"
            and len(episodes) == body.get("total_count")
            and len(unique_codes) == len(episodes)
        ),
        "episodes": episodes,
    }


def content_metadata(result: dict[str, Any]) -> dict[str, Any]:
    """Project captured data into drama/TV-show facts only.

    Keep transport, site configuration, availability flags, and collection checks
    outside the content document. Missing source facts remain null.
    """
    info = result["detail"]["content_info"]

    def date(value: Any) -> str | None:
        text = str(value or "")
        if re.fullmatch(r"\d{8}", text):
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return None

    schema = next((item for item in result["detail"].get("json_ld", [])
                   if isinstance(item, dict) and item.get("@type") == "TVSeries"), {})
    hour, minute = info.get("broad_hour"), info.get("broad_minu")
    return program_metadata(**{
        "program_id": info["program_code"],
        "title": info.get("title"),
        "content_type": info.get("category_name"),
        "genre": info.get("genre_name"),
        "production_year": info.get("product_year"),
        "channel": info.get("channel"),
        # Legacy display key. TVING labels this array 'creators'; do not infer roles.
        "directors": info.get("director"),
        "writers": info.get("script"),
        "cast": info.get("actor"),
        "synopsis": info.get("synopsis"),
        "keywords": info.get("keywords"),
        "age_rating": schema.get("contentRating"),
        "broadcast_start_date": date(info.get("broad_dt")),
        "broadcast_end_date": date(info.get("broad_end_dt")),
        "broadcast_schedule": {
            "weekday": info.get("broad_week"),
            "time": f"{hour}:{minute}" if hour and minute else None,
        },
        "episodes": [{
            "episode_id": episode["episode_code"],
            "number": episode.get("episode_number"),
            "title": episode.get("title"),
            "synopsis": episode.get("synopsis"),
            "broadcast_date": date(episode.get("broadcast_date_raw")),
            "duration_seconds": episode.get("duration_seconds"),
        } for episode in result["episode_list"]["episodes"]],
    })


def collect_program_with_report(
    content_url: str, output_dir: Path, *, save_raw: bool = False
) -> dict[str, Any]:
    """Fetch one program, its current client config, and one episode-list response.

    This synchronous function can be called by a FastAPI sync endpoint or worker.
    Pagination and multiple seasons remain outside this bounded probe.
    """
    source_url, content_code = normalize_content_url(content_url)
    html = _get_text(source_url)
    detail = parse_detail(html)
    code = _program_code(detail["content_info"]["program_code"])
    if content_code.startswith("P") and code != content_code:
        raise TvingError("Returned page does not match the requested program")
    if content_code.startswith("E") and detail["content_info"].get("code") != content_code:
        raise TvingError("Returned page does not match the requested episode")
    raw_detail = parse_detail_raw(html)
    output_dir.mkdir(parents=True, exist_ok=True)
    collected_at = datetime.now(UTC).isoformat()
    bundle = make_bundle(raw_detail["content_info"], raw_detail["json_ld"], {
        "source_url": source_url, "collected_at": collected_at,
        "acquisition_method": "embedded_page_data_and_episode_api", "status": "page_collected",
    })
    destination = output_dir / BUNDLE_FILENAME
    write_bundle(destination, bundle)
    if save_raw:
        (output_dir / "page.html").write_text(html, encoding="utf-8")
    soup = BeautifulSoup(html, "html.parser")
    scripts = [str(tag.get("src", "")) for tag in soup.find_all("script", src=True)]
    client_path = next((path for path in scripts if "/chunks/pages/_app-" in path), None)
    if client_path is None:
        raise TvingError("Missing public application bundle")
    client_url = urljoin(source_url, client_path)
    if urlsplit(client_url).netloc != "www.tving.com":
        raise TvingError("Unexpected application bundle origin")
    key = extract_public_client_key(_get_text(client_url))
    endpoint = f"https://api.tving.com/v2/media/frequency/program/{code}"
    params = {
        "order": "new", "cacheType": "main", "pageSize": 20,
        "adult": "all", "free": "all", "guest": "all", "scope": "all",
        "screenCode": "CSSD0100", "networkCode": "CSND0900",
        "osCode": "CSOD0900", "teleCode": "CSCD0900", "apiKey": key,
    }
    raw_api = _get_text(endpoint + "?" + urlencode(params))
    bundle["collection"].update(episode_endpoint=endpoint, status="response_collected")
    try:
        bundle["episodeApi"] = json.loads(raw_api)
    except json.JSONDecodeError:
        bundle["episodeApiResponseText"] = raw_api
        bundle["collection"]["status"] = "invalid_api_json"
        write_bundle(destination, bundle)
        raise TvingError("Episode API returned invalid JSON") from None
    write_bundle(destination, bundle)
    try:
        episode_list = parse_episodes(bundle["episodeApi"], code)
    except (TvingError, KeyError, TypeError, ValueError) as exc:
        bundle["collection"].update(status="display_parser_failed", error=str(exc))
        write_bundle(destination, bundle)
        raise
    bundle["collection"].update(
        status="collected",
        complete_for_current_api_listing=episode_list["complete_for_current_api_listing"],
    )
    write_bundle(destination, bundle)
    result = {
        "source_url": source_url,
        "source_endpoint": endpoint,
        "collected_at": collected_at,
        "metadata_file": BUNDLE_FILENAME,
        "bundle": bundle,
        "detail": detail,
        "episode_list": episode_list,
        "notes": [
            "Episode synopsis is a description, not a screenplay.",
            "Completeness refers to the current API listing, not future episodes.",
            "This probe does not paginate or traverse multiple seasons.",
        ],
    }
    return result


def collect_program(
    content_url: str, output_dir: Path, *, save_raw: bool = False
) -> dict[str, Any]:
    """Return the source bundle saved as metadata.json."""
    return collect_program_with_report(
        content_url, output_dir, save_raw=save_raw
    )["bundle"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="TVING program or episode detail URL")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check-only", action="store_true",
                        help="Preview the supplied official URL without saving metadata")
    parser.add_argument(
        "--save-raw", action="store_true",
        help="Also save full page HTML; source metadata/API JSON is always saved",
    )
    args = parser.parse_args()
    if args.check_only:
        from .url_review import inspect_official_url
        url, _ = normalize_content_url(args.url)
        print(json.dumps(inspect_official_url(url, "tving_detail", "drama"),
                         ensure_ascii=False, indent=2))
        return
    _, content_code = normalize_content_url(args.url)
    output_dir = args.output_dir or Path("data/probes") / f"tving-{content_code}-python"
    result = collect_program_with_report(args.url, output_dir, save_raw=args.save_raw)
    summary = {name: value for name, value in result["episode_list"].items() if name != "episodes"}
    summary["output_file"] = str((output_dir / BUNDLE_FILENAME).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
