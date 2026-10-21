"""Source-preserving tvN collection; channel tabs never determine program genres."""

from __future__ import annotations

import argparse
import json
import re
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from .metadata import program_metadata
from .output_paths import KST, create_run_folder, safe_folder_name
from .tving_storage import write_bundle

ORIGIN = "https://tvn.cjenm.com"
API_ORIGIN = "https://poc-cf-api.cjenm.com"
BUNDLE_FORMAT = "tvn-source-bundle"
INDEX_FORMAT = "tvn-source-index"
INVENTORY_FORMAT = "tvn-program-inventory"
LISTING_URL = ORIGIN + "/ko/program/"
CHANNELS = {"ALL": "전체 채널", "MC010268": "tvN", "MC010273": "tvN STORY",
            "MC010271": "tvN DRAMA", "MC010272": "tvN SHOW"}
Progress = Callable[[dict[str, Any]], None]


class TvnError(RuntimeError):
    """An HTTP response or source structure could not be collected."""


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if (parts.scheme != "https" or parts.netloc.lower() != "tvn.cjenm.com"
            or not re.fullmatch(r"/ko/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/?", parts.path)):
        raise ValueError("tvN의 HTTPS 프로그램 목록 또는 작품 URL을 입력해 주세요.")
    if parts.path.split("/")[2] in {"signin", "signup", "mypage", "account"}:
        raise ValueError("tvN 프로그램 페이지 URL을 입력해 주세요.")
    return urlunsplit(("https", "tvn.cjenm.com", parts.path.rstrip("/") + "/",
                      parts.query, ""))


def is_listing(url: str) -> bool:
    return urlsplit(normalize_url(url)).path.startswith("/ko/program/")


def _get_text(url: str) -> str:
    if urlsplit(url).netloc not in {"tvn.cjenm.com", "poc-cf-api.cjenm.com"}:
        raise TvnError("Unexpected tvN request origin")
    try:
        request = Request(url, headers={"User-Agent": "broadcast-metadata-probe/0.1"})
        with urlopen(request, timeout=30) as response:
            if urlsplit(response.url).netloc != urlsplit(url).netloc:
                raise TvnError("Unexpected tvN redirect origin")
            raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                raise TvnError("tvN response exceeds the 10 MB limit")
            return raw.decode("utf-8")
    except (URLError, TimeoutError) as exc:
        raise TvnError(f"tvN HTTP request failed for {urlsplit(url).path}") from exc


def parse_page(html: str) -> dict[str, Any]:
    tag = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    try:
        props = json.loads(tag.get_text())["props"]["pageProps"] if tag else None
        if not isinstance(props, dict) or not isinstance(props.get("fallback"), dict):
            raise ValueError("Missing page fallback")
        return props
    except (ValueError, KeyError, TypeError) as exc:
        raise TvnError("tvN 페이지의 프로그램 데이터를 읽을 수 없습니다.") from exc


def _listing_config(props: dict[str, Any], url: str) -> dict[str, Any]:
    fallback = props["fallback"]
    templates = [v for v in fallback.values() if isinstance(v, dict) and "tempInfo" in v]
    modules = [m for template in templates for m in template["tempInfo"]]
    outer = parse_qs(urlsplit(url).query)
    candidates = [m for m in modules if isinstance(
        (fallback.get(str(m["tmplModulSeq"]), {}).get("data") or {}).get("dataInfo"), dict
    )]
    if len(candidates) != 1:
        raise TvnError("tvN 프로그램 목록 모듈을 확인할 수 없습니다.")
    module = candidates[0]
    module_id = str(module["tmplModulSeq"])
    params = dict(module.get("ajaxParams") or {})
    supplied = parse_qs(outer.get(module_id, [""])[0])
    allowed = {"removeCacheYn", "repGenreCdList", "sortType", "pageNum",
               "searchTlviseStatCd", "searchChnCd", "searchRepGenreCd", "searchKeyword"}
    unknown = supplied.keys() - allowed
    if unknown:
        raise ValueError("지원하지 않는 tvN 목록 필터: " + ", ".join(sorted(unknown)))
    params.update({key: values[-1] for key, values in supplied.items()})
    # Initial HTML ignores these query parameters. Always ask the module API from page 1.
    params["pageNum"] = 1
    endpoint = module["ajaxModulUrl"]
    if not re.fullmatch(r"/apis/v1/tmplModul/\d+", endpoint):
        raise TvnError("Unexpected tvN listing API path")
    return {"module_id": module_id, "endpoint": API_ORIGIN + endpoint,
            "filters": params, "channel_tab": CHANNELS.get(params.get("searchChnCd"),
                                                          params.get("searchChnCd", "전체 채널"))}


def discover_programs(
    url: str, *, limit: int | None = None, start_rank: int = 1, max_pages: int = 500,
    on_progress: Progress | None = None,
) -> dict[str, Any]:
    url = normalize_url(url)
    if not is_listing(url) or start_rank < 1 or max_pages < 1 or (limit is not None and limit < 1):
        raise ValueError("tvN 목록 URL과 수집 범위를 확인해 주세요.")
    config = _listing_config(parse_page(_get_text(url)), url)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    target = None if limit is None else start_rank + limit - 1
    duplicates = 0
    stagnant = 0
    report: dict[str, Any] = {"source_url": url, **config, "pages_read": 0,
                              "unique_count": 0, "duplicate_items_count": 0,
                              "complete_listing": False, "programs": rows}
    for page_number in range(1, max_pages + 1):
        params = {**config["filters"], "pageNum": page_number}
        payload = json.loads(_get_text(config["endpoint"] + "?" + urlencode(params)))
        if payload.get("resultCd") != "0000":
            raise TvnError("tvN 목록 API가 성공 응답을 반환하지 않았습니다.")
        paging = payload["result"]["data"]["dataInfo"]
        items = paging["list"]
        if int(paging["pageNum"]) != page_number or not isinstance(items, list):
            raise TvnError("tvN 목록 API의 페이지 번호 또는 목록 형식이 잘못되었습니다.")
        previous = len(rows)
        for item in items:
            code = str(item["pgmSeq"])
            if code in seen:
                duplicates += 1
                continue
            seen.add(code)
            rows.append({"rank": len(rows) + 1, "program_id": code,
                         "title": item["pgmNm"], "url": item.get("frontDetailUrlAddr"),
                         "listing_item": item})
        stagnant = stagnant + 1 if len(rows) == previous else 0
        last = paging.get("isLastPage") is True or paging.get("hasNextPage") is False
        total = int(paging["total"])
        complete = last and len(rows) == total
        report.update(pages_read=page_number, unique_count=len(rows), reported_total=total,
                      duplicate_items_count=duplicates, complete_listing=complete)
        if on_progress:
            on_progress(report)
        if target is not None and len(rows) >= target:
            return {**report, "programs": rows[start_rank - 1:target]}
        if last:
            if not complete:
                raise TvnError("tvN 마지막 페이지의 작품 수가 전체 수와 일치하지 않습니다.")
            if start_rank > len(rows):
                raise TvnError("요청한 수집 구간이 tvN 목록 범위를 벗어났습니다.")
            return {**report, "programs": rows[start_rank - 1:target]}
        if not items or stagnant >= 3:
            raise TvnError("tvN 목록 페이지 순회가 진행되지 않습니다.")
        if page_number < max_pages:
            time.sleep(1)
    raise TvnError("tvN 최대 목록 페이지에 도달했습니다. 범위를 줄이거나 상한을 늘려 주세요.")


def validate_inventory(inventory: dict[str, Any], *, url: str) -> None:
    if (inventory.get("format") != INVENTORY_FORMAT
            or normalize_url(inventory.get("source_url", "")) != normalize_url(url)
            or inventory.get("complete_listing") is not True):
        raise ValueError("완료된 동일 tvN URL의 저장 목록을 사용해 주세요.")
    entries = inventory.get("programs")
    if not isinstance(entries, list) or not entries:
        raise ValueError("저장 목록에 수집할 tvN 작품이 없습니다.")
    ids = set()
    for rank, item in enumerate(entries, 1):
        code = item["program_id"]
        if not isinstance(code, str) or not code.isdigit() or code in ids or item["rank"] != rank:
            raise ValueError("tvN 저장 목록의 ID·순서·중복 항목을 확인해 주세요.")
        if not isinstance(item.get("title"), str):
            raise ValueError("tvN 저장 목록의 작품명을 확인해 주세요.")
        ids.add(code)
    if len(entries) != inventory.get("unique_count"):
        raise ValueError("tvN 저장 목록의 작품 수가 일치하지 않습니다.")


def scan_inventory(
    output_root: Path, *, url: str, max_pages: int = 500, on_progress: Progress | None = None,
) -> tuple[dict[str, Any], Path]:
    url = normalize_url(url)
    run = create_run_folder(output_root, "tvN", "전체목록", datetime.now(KST))
    destination = run / "inventory.json"
    report: dict[str, Any] = {"format": INVENTORY_FORMAT, "schema_version": 1,
        "source_url": url, "category": "tvn", "checked_at": datetime.now(KST).isoformat(),
        "max_pages": max_pages, "complete_listing": False, "programs": [],
        "unique_count": 0, "pages_read": 0, "duplicate_items_count": 0}

    def checkpoint(value: dict[str, Any]) -> None:
        report.update(value)
        write_bundle(destination, report)
        if on_progress:
            on_progress(report)

    write_bundle(destination, report)
    try:
        report.update(discover_programs(url, max_pages=max_pages, on_progress=checkpoint))
    except (TvnError, ValueError, KeyError, TypeError) as exc:
        report.update(complete_listing=False, error=str(exc))
    report["checked_at"] = datetime.now(KST).isoformat()
    write_bundle(destination, report)
    return report, destination


def collect_program(
    url: str, destination: Path, *, listing_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = normalize_url(url)
    html = _get_text(url)
    props = parse_page(html)
    if is_listing(url):
        raise ValueError("tvN 작품 상세 URL을 입력해 주세요.")
    modules = {key: value for key, value in props["fallback"].items() if key.isdigit()}
    program_ids = {str(m.get("modulAttrInfo", {}).get("pgmSeq")) for m in modules.values()
                   if isinstance(m, dict) and isinstance(m.get("modulAttrInfo"), dict)
                   and m["modulAttrInfo"].get("pgmSeq") is not None}
    if listing_item and str(listing_item["pgmSeq"]) not in program_ids:
        raise TvnError("tvN 상세 페이지가 요청한 작품 ID와 일치하지 않습니다.")
    if not program_ids:
        raise TvnError("tvN 상세 페이지에 작품 데이터가 없습니다.")
    bundle = {"format": BUNDLE_FORMAT, "schema_version": 1,
        "collection": {"source_url": url, "collected_at": datetime.now(KST).isoformat(),
            "acquisition_method": "embedded_page_modules", "status": "collected",
            "program_ids": sorted(program_ids), "episode_coverage": "available_preview_modules",
            "complete_episode_list": False},
        "listingItem": listing_item, "pageInfo": props["pageInfo"], "modules": modules,
        "templates": {k: v for k, v in props["fallback"].items()
                      if isinstance(v, dict) and "tempInfo" in v}}
    write_bundle(destination, bundle)
    try:
        _collect_linked_previews(bundle, html, destination)
    except (TvnError, ValueError, KeyError, TypeError, OSError) as exc:
        bundle["collection"]["status"] = "collected_with_warnings"
        bundle["collection"]["preview_warning"] = str(exc)
    write_bundle(destination, bundle)
    return bundle


def _preview_modules(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    modules = [value for value in bundle["modules"].values() if isinstance(value, dict)]
    for page in bundle.get("linkedPages", []):
        modules.extend(page["modules"].values())
    modules.extend({"data": page["response"]["result"]["data"]}
                   for page in bundle.get("previewApiResponses", []))
    return modules


def _preview_rows(module: dict[str, Any]) -> list[dict[str, Any]]:
    data = module.get("data")
    if not isinstance(data, dict):
        return []
    rows = [*(data.get("previewInfoList") or []),
            *((data.get("dataInfo") or {}).get("list") or [])]
    return [row for row in rows if isinstance(row, dict) and "pgmTmnoPrevewSeq" in row]


def _collect_linked_previews(bundle: dict, html: str, destination: Path) -> None:
    source_url = bundle["collection"]["source_url"]
    program_root = "/".join(urlsplit(source_url).path.split("/")[:3]) + "/"
    props = {"fallback": {**bundle["templates"], **bundle["modules"]}}
    preview_url = source_url
    if urlsplit(source_url).path != program_root + "episodes/":
        links = [urljoin(source_url, str(a["href"])) for a in
                 BeautifulSoup(html, "html.parser").find_all("a", href=True)]
        preview_url = next((link for link in links if urlsplit(link).netloc == "tvn.cjenm.com"
                            and urlsplit(link).path == program_root + "episodes/"), "")
        if not preview_url:
            return  # Never synthesize or search for an absent menu URL.
        preview_url = normalize_url(preview_url)
        props = parse_page(_get_text(preview_url))
        modules = {k: v for k, v in props["fallback"].items() if k.isdigit()}
        ids = {str(v["modulAttrInfo"]["pgmSeq"]) for v in modules.values()
               if isinstance(v, dict) and isinstance(v.get("modulAttrInfo"), dict)
               and v["modulAttrInfo"].get("pgmSeq") is not None}
        if not ids.intersection(bundle["collection"]["program_ids"]):
            raise TvnError("연결된 미리보기 페이지의 작품 ID가 다릅니다.")
        bundle["linkedPages"] = [{"source_url": preview_url, "pageInfo": props["pageInfo"],
            "modules": modules, "templates": {k: v for k, v in props["fallback"].items()
                        if isinstance(v, dict) and "tempInfo" in v}}]
        write_bundle(destination, bundle)
    configurations = {str(m["tmplModulSeq"]): m for template in props["fallback"].values()
                      if isinstance(template, dict) and "tempInfo" in template
                      for m in template["tempInfo"]}
    for key, module in props["fallback"].items():
        if not key.isdigit() or not isinstance(module, dict):
            continue
        paging = (module.get("data") or {}).get("dataInfo")
        if not isinstance(paging, dict) or not _preview_rows(module):
            continue
        expected = int(paging["total"])
        seen = {str(r["pgmTmnoPrevewSeq"]) for r in _preview_rows(module)}
        last = paging.get("isLastPage") is True or paging.get("hasNextPage") is False
        pages_read = 1
        while not last and pages_read < 100:
            next_page = paging.get("nextPage")
            if not isinstance(next_page, int) or next_page <= int(paging["pageNum"]):
                raise TvnError("미리보기의 다음 페이지 정보가 유효하지 않습니다.")
            config = configurations[key]
            endpoint = config["ajaxModulUrl"]
            if not re.fullmatch(r"/apis/v1/tmplModul/\d+", endpoint):
                raise TvnError("Unexpected preview API path")
            params = {**config.get("ajaxParams", {}), "pageNum": next_page}
            api_url = API_ORIGIN + endpoint + "?" + urlencode(params)
            time.sleep(1)
            response = json.loads(_get_text(api_url))
            bundle.setdefault("previewApiResponses", []).append(
                {"source_url": api_url, "response": response})
            write_bundle(destination, bundle)
            if response.get("resultCd") != "0000":
                raise TvnError("미리보기 API가 성공 응답을 반환하지 않았습니다.")
            paging = response["result"]["data"]["dataInfo"]
            if int(paging["pageNum"]) != next_page or int(paging["total"]) != expected:
                raise TvnError("미리보기 페이지 번호 또는 전체 수가 변경되었습니다.")
            rows = _preview_rows({"data": {"dataInfo": paging}})
            previous = len(seen)
            seen.update(str(r["pgmTmnoPrevewSeq"]) for r in rows)
            last = paging.get("isLastPage") is True or paging.get("hasNextPage") is False
            pages_read += 1
            if len(seen) == previous and not last:
                raise TvnError("미리보기 페이지 수집이 진행되지 않습니다.")
        bundle["collection"]["preview_listing"] = {
            "source_url": preview_url, "reported_total": expected, "collected_unique": len(seen),
            "pages_read": pages_read,
            "complete_for_current_preview_listing": last and len(seen) == expected,
        }


def _plain(value: str | None) -> str | None:
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True) if value else None


def display_content(bundle: dict[str, Any]) -> dict[str, Any]:
    item = bundle.get("listingItem") or {}
    meta = bundle["pageInfo"].get("pageInfo") or {}
    genre = item.get("repGenreInfo") or meta.get("repGenreInfo")
    title = item.get("pgmNm") or meta.get("snsTitTagCnts")
    synopsis = None
    people: list[dict[str, Any]] = []
    previews: list[dict[str, Any]] = []
    episodes_seen = set()
    for module in _preview_modules(bundle):
        data = module.get("data")
        if not isinstance(data, dict):
            continue
        title = title or data.get("pgmNm")
        intro = data.get("plnngIntentInfo") or {}
        popup = data.get("plnngIntentDtlPopupInfo") or {}
        synopsis = synopsis or _plain(popup.get("dtlCnts") or intro.get("plnngIntentSumryCnts"))
        people.extend(data.get("simplePrsnInfoList") or [])
        for preview in _preview_rows(module):
            code = str(preview["pgmTmnoPrevewSeq"])
            if code in episodes_seen:
                continue
            episodes_seen.add(code)
            episode_title = preview.get("prevewTit")
            number = re.search(r"(\d+)\s*(?:화|회)", episode_title or "")
            previews.append({"episode_id": code, "number": int(number[1]) if number else None,
                             "title": episode_title, "synopsis": _plain(preview.get("prevewCnts")),
                             "broadcast_date": None})
    return program_metadata(
        program_id=str(item.get("pgmSeq") or bundle["collection"]["program_ids"][0]),
        title=title, content_type=genre,
        genre=item.get("ptclrGenreInfo") or meta.get("ptclrGenreInfo") or genre,
        synopsis=synopsis or _plain(item.get("pgmDescp")),
        channel=item.get("repChnNm"), channel_tab=bundle["collection"].get("channel_tab"),
        broadcast_schedule=item.get("bdTm"), broadcast_status=item.get("orgbcRendYn"),
        characters=people, episodes=previews, episode_kind="회차 미리보기",
        episode_coverage=("공식 미리보기 목록을 수집했습니다. 방송 전체 회차 여부와는 구분합니다."
                          if bundle["collection"].get("preview_listing", {}).get(
                              "complete_for_current_preview_listing")
                          else "상세 페이지가 제공한 미리보기이며 전체 회차 목록이 아닙니다."),
    )


def collect_programs(
    output_root: Path, limit: int | None = 20, *, url: str, start_rank: int = 1,
    max_pages: int = 500, inventory: dict[str, Any] | None = None,
    on_progress: Progress | None = None,
) -> dict[str, Any]:
    url = normalize_url(url)
    if start_rank < 1 or max_pages < 1 or (limit is not None and limit < 1):
        raise ValueError("tvN 수집 범위를 확인해 주세요.")
    if is_listing(url):
        if inventory is not None:
            validate_inventory(inventory, url=url)
            target = None if limit is None else start_rank + limit - 1
            entries = inventory["programs"][start_rank - 1:target]
            if not entries:
                raise ValueError("요청한 구간이 저장된 tvN 목록을 벗어났습니다.")
            listing = {**inventory, "programs": entries}
        else:
            listing = discover_programs(url, limit=limit, start_rank=start_rank,
                                        max_pages=max_pages, on_progress=on_progress)
        entries = listing["programs"]
        channel_tab = listing["channel_tab"]
    else:
        entries = [{"rank": 1, "title": urlsplit(url).path.split("/")[2], "url": url}]
        listing = None
        channel_tab = "작품상세"
    now = datetime.now(KST)
    run = create_run_folder(output_root, "tvN", channel_tab, now)
    report: dict[str, Any] = {"source_url": url, "started_at": now.isoformat(),
        "output_dir": str(run.resolve()), "scope": {"channel_tab": channel_tab,
            "start_rank": start_rank, "limit": limit, "max_pages": max_pages},
        "listing": {k: v for k, v in (listing or {}).items() if k != "programs"},
        "programs": [], "summary": {}}
    index: dict[str, Any] = {"format": INDEX_FORMAT, "schema_version": 1, "programs": []}
    index_path = run / "contents.json"
    for entry in entries:
        folder = run / f"{safe_folder_name(entry['title'])}_{now:%Y%m%d}"
        suffix = 2
        while folder.exists():
            folder = run / f"{safe_folder_name(entry['title'])}_{now:%Y%m%d}_{suffix}"
            suffix += 1
        record = {k: v for k, v in entry.items() if k != "listing_item"}
        try:
            if not entry.get("url"):
                raise TvnError("목록에 작품 상세 URL이 없습니다.")
            destination = folder / "metadata.json"
            bundle = collect_program(entry["url"], destination,
                                     listing_item=entry.get("listing_item"))
            bundle["collection"]["channel_tab"] = channel_tab
            write_bundle(destination, bundle)
            content = display_content(bundle)
            relative = destination.relative_to(run).as_posix()
            index["programs"].append({"title": content["title"], "metadata_file": relative})
            record.update(status="success", metadata_file=relative,
                          preview_count=len(content["episodes"]),
                          complete_preview_listing=bundle["collection"].get(
                              "preview_listing", {}).get(
                                  "complete_for_current_preview_listing", False),
                          warning=bundle["collection"].get("preview_warning"))
        except (TvnError, ValueError, KeyError, TypeError, OSError) as exc:
            record.update(status="error", error=str(exc))
        report["programs"].append(record)
        successes = sum(r["status"] == "success" for r in report["programs"])
        report["summary"] = {"requested_programs": len(entries),
            "processed_programs": len(report["programs"]), "successful_programs": successes,
            "failed_programs": len(report["programs"]) - successes,
            "collected_previews": sum(r.get("preview_count", 0) for r in report["programs"])}
        write_bundle(index_path, index)
        write_bundle(run / "collection-report.json", report)
        if on_progress:
            on_progress({"processed": len(report["programs"]), "total": len(entries),
                         "title": entry["title"], "status": record["status"],
                         "content_file": str(index_path.resolve())})
        time.sleep(1)
    report["finished_at"] = datetime.now(KST).isoformat()
    write_bundle(run / "collection-report.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--output-dir", type=Path, default=Path("data/tvn"))
    parser.add_argument("--start-rank", type=int, default=1)
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--limit", type=int, default=20)
    scope.add_argument("--all", action="store_true")
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--check-only", action="store_true",
                        help="입력 URL의 작품명 또는 목록 범위만 확인")
    args = parser.parse_args()
    if args.check_only:
        from .url_review import inspect_official_url
        url = normalize_url(args.url)
        kind = "tvn_category" if is_listing(url) else "tvn_detail"
        print(json.dumps(inspect_official_url(url, kind, "drama"), ensure_ascii=False, indent=2))
        return
    report = collect_programs(args.output_dir, None if args.all else args.limit, url=args.url,
                              start_rank=args.start_rank, max_pages=args.max_pages)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
