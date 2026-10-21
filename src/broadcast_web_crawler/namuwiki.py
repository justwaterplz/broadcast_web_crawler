"""NamuWiki document resolution and evidence-backed broadcast metadata extraction."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, NavigableString, Tag

from broadcast_web_crawler.metadata import program_metadata
from broadcast_web_crawler.output_paths import KST, create_run_folder, safe_folder_name
from broadcast_web_crawler.source_records import save_source_record, wiki_source_record

LABELS = {"시청 등급", "장르", "방송 기간", "방송 시간", "방송 횟수", "채널",
          "제작", "제작사", "제작진", "연출", "작가", "극본", "진행", "출연",
          "공개 기간", "공개일", "공개 회차"}
SECTION_NAMES = {"개요", "기획 의도", "프로그램 소개", "프로그램 구성", "등장인물",
                 "출연진", "역대 출연진", "역대 진행자", "셰프 군단", "제작진"}


class WikiError(RuntimeError):
    pass


def resolve_document(value: str) -> str:
    """Accept a document title or URL; this resolves an exact title, not a search."""
    value = value.strip()
    if "://" in value:
        parts = urlsplit(value)
        if parts.scheme != "https" or parts.netloc.lower() != "namu.wiki":
            raise ValueError("Expected an HTTPS namu.wiki document URL")
        if not parts.path.startswith("/w/"):
            raise ValueError("Expected the /w/<document-title> path")
        title = unquote(parts.path[3:])
    else:
        title = unquote(value)
    if not title or len(title) > 250 or any(ord(c) < 32 for c in title):
        raise ValueError("Invalid document title")
    return "https://namu.wiki/w/" + quote(title, safe="/")


def _clean(text: str) -> str:
    text = re.sub(r"\[\d+\]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_document(html: str, http_status: int) -> str:
    """Never equate HTTP 200 alone with a real article or 403 with absence."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if http_status in {401, 403, 429}:
        return "access_denied"
    if any(marker in page_title.lower() for marker in (
        "just a moment", "attention required", "captcha", "access denied",
    )) or soup.select_one("#challenge-form, #cf-challenge-running"):
        return "access_denied"
    if http_status == 404 or any(marker in text for marker in (
        "해당 문서가 존재하지 않습니다", "이 문서는 존재하지 않습니다", "문서를 찾을 수 없습니다",
    )):
        return "not_found"
    if http_status != 200:
        return "http_error"
    if soup.find("h1") and (soup.find(["h2", "h3"]) or soup.find("table")):
        return "exists"
    return "unknown"


def fetch_document(value: str) -> tuple[str, dict[str, Any]]:
    url = resolve_document(value)
    report: dict[str, Any] = {"requested_url": url, "checked_at": datetime.now(KST).isoformat()}
    request = Request(url, headers={"User-Agent": "broadcast-metadata-research-bot/0.1"})
    try:
        with urlopen(request, timeout=30) as response:
            if urlsplit(response.url).netloc != "namu.wiki":
                raise WikiError("Unexpected document redirect origin")
            raw = response.read(8_000_001)
            if len(raw) > 8_000_000:
                raise WikiError("Wiki response exceeds the 8 MB limit")
            html = raw.decode("utf-8")
            report.update(http_status=response.status, final_url=response.url)
    except HTTPError as exc:
        html = exc.read(8_000_000).decode("utf-8", errors="replace")
        report.update(http_status=exc.code, final_url=url)
    except (URLError, TimeoutError) as exc:
        report.update(status="network_error", error=type(exc).__name__)
        return "", report
    report["status"] = classify_document(html, report["http_status"])
    return html, report


def check_document(value: str) -> dict[str, Any]:
    """Check an exact document title/URL without saving or extracting content."""
    return fetch_document(value)[1]


def _table_fields(table: Tag) -> dict[str, str]:
    fields = {}
    for row in table.find_all("tr"):
        if row.find_parent("table") is not table:
            continue
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) in {2, 3}:
            # A rowspan '제작진' header creates a three-cell first credits row.
            key = _clean(cells[-2].get_text(" ", strip=True))
            if key in LABELS:
                fields[key] = _clean(cells[-1].get_text(" ", strip=True))
    return fields


def _sections(soup: BeautifulSoup) -> dict[str, str]:
    """Read in document order, independent of randomized CSS class names."""
    result = {}
    for heading in soup.find_all(["h2", "h3", "h4"]):
        name = _clean(heading.get_text(" ", strip=True))
        name = re.sub(r"^\d+(?:\.\d+)*\.\s*", "", name).replace("[편집]", "").strip()
        if name not in SECTION_NAMES:
            continue
        texts = []
        for node in heading.next_elements:
            if isinstance(node, Tag) and node.name in {"h2", "h3", "h4"}:
                break
            if isinstance(node, NavigableString) and not node.find_parent(
                ["h2", "h3", "h4", "script", "style", "sup", "noscript"]
            ):
                text = str(node).strip()
                if text:
                    texts.append(text)
        text = _clean(" ".join(texts))
        if text:
            result[name] = text
    return result


def parse_document(html: str, url: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if classify_document(html, 200) != "exists":
        raise WikiError("Response is not an accessible wiki document")
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(["script", "style", "noscript", "img"]):
        element.decompose()
    title = _clean(soup.find("h1").get_text(" ", strip=True))
    candidates = [(table, _table_fields(table)) for table in soup.find_all("table")]
    if not candidates:
        raise WikiError("Document exists but has no broadcast information table")
    table, fields = max(candidates, key=lambda item: len(item[1]))
    if len(fields) < 4 or not ({"방송 기간", "채널", "방송 횟수", "공개 기간",
                               "공개 회차", "공개일"} & fields.keys()):
        raise WikiError("Document exists but no supported broadcast infobox was found")
    sections = _sections(soup)
    credits = fields.get("제작진", "")

    def names(text: str | None) -> list[str] | None:
        if not text or "문서 참조" in text:
            return None
        text = re.sub(r"\([^)]*\)", "", text)
        return [name.strip() for name in re.split(r"[,·]", text) if name.strip()]

    def credit(label: str) -> list[str] | None:
        if label in fields:
            return names(fields[label])
        match = re.search(r"(?:^|\s)" + label + r"\s*:\s*(.*?)(?=\s[가-힣]+\s*:|$)", credits)
        return names(match[1]) if match else None

    dates = re.findall(r"(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일",
                       fields.get("방송 기간") or fields.get("공개 기간")
                       or fields.get("공개일", ""))
    formatted_dates = [f"{int(y):04}-{int(m):02}-{int(d):02}" for y, m, d in dates]
    count = re.search(r"(\d+)\s*(?:부작|회)",
                      fields.get("방송 횟수") or fields.get("공개 회차", ""))
    official = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) == 2 and _clean(cells[0].get_text()) == "링크":
            official = [a["href"] for a in cells[1].find_all("a", href=True)
                        if a["href"].startswith("https://")]
    document_title = unquote(urlsplit(url).path[3:])
    related = {}
    for anchor in soup.find_all("a", href=True):
        target = urljoin(url, anchor["href"])
        parts = urlsplit(target)
        path = unquote(parts.path)
        if (parts.netloc == "namu.wiki" and path.startswith("/w/" + document_title + "/")
                and path.rsplit("/", 1)[-1] in {"방영 목록", "셰프 군단", "등장인물"}):
            normalized = resolve_document(target)
            related[normalized] = {"title": path[3:], "url": normalized}
    content = program_metadata(
        title=title,
        content_type=("드라마" if "드라마" in fields.get("장르", "")
                      or "드라마" in table.find("tr").get_text() or title.endswith("(드라마)") else
                      "TV쇼" if "예능" in fields.get("장르", "") else None),
        genre=fields.get("장르"), channel=fields.get("채널"),
        production_company=fields.get("제작사") or fields.get("제작"),
        directors=credit("연출"), writers=credit("작가") or credit("극본"),
        cast=names(fields.get("출연")), hosts=names(fields.get("진행")),
        synopsis=sections.get("개요") or sections.get("프로그램 소개"),
        age_rating=fields.get("시청 등급"),
        broadcast_start_date=formatted_dates[0] if formatted_dates else None,
        broadcast_end_date=formatted_dates[1] if len(formatted_dates) > 1 else None,
        broadcast_schedule=fields.get("방송 시간"),
        episode_count=int(count[1]) if count else None,
        content_sections=sections,
        cast_reference=fields.get("출연") if names(fields.get("출연")) is None else None,
        related_documents=list(related.values()), official_links=official,
    )
    scope = re.search(r"이 문서는.{0,150}?다루고 있습니다\.", soup.get_text(" ", strip=True))
    evidence = {
        "infobox_fields": fields,
        "section_names": list(sections),
        "document_scope_note": scope[0] if scope else None,
        "episode_details_collected": False,
        "related_documents_checked": False,
        "notes": [
            "Wiki statements are source claims, not independently verified broadcaster facts.",
            "An overview is a program description, not episode synopses or a screenplay.",
            "Related and official URLs are discovered but not followed by this collector.",
        ],
    }
    return content, evidence


def collect_document(value: str, output_root: Path) -> dict[str, Any]:
    html, report = fetch_document(value)
    title = unquote(urlsplit(report["requested_url"]).path[3:])
    now = datetime.now(KST)
    output = create_run_folder(output_root, "나무위키", title, now)
    if report["status"] == "exists":
        try:
            content, evidence = parse_document(html, report["final_url"])
            report.update(evidence)
            show = output / f"{safe_folder_name(content['title'])}_{now:%Y%m%d}"
            show.mkdir()
            text = json.dumps(content, ensure_ascii=False, indent=2)
            (show / "program.json").write_text(text, encoding="utf-8")
            record = wiki_source_record(content, report)
            save_source_record(show / "source-record.json", record)
            report.update(source_record_file=str((show / "source-record.json").resolve()),
                          review=record["review"], acquisition_method=record["acquisition_method"])
            (output / "contents.json").write_text(
                json.dumps({"programs": [content]}, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            report["content_file"] = str((output / "contents.json").resolve())
            report["extraction_status"] = "collected"
        except WikiError as exc:
            report.update(extraction_status="unsupported_document", error=str(exc))
    report["output_dir"] = str(output.resolve())
    (output / "collection-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("document", help="NamuWiki document title or URL")
    parser.add_argument(
        "--check-only", action="store_true", help="Check existence without extraction"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/namuwiki"))
    args = parser.parse_args()
    report = check_document(args.document) if args.check_only else collect_document(
        args.document, args.output_dir
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "exists" or report.get("extraction_status") == "unsupported_document":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
