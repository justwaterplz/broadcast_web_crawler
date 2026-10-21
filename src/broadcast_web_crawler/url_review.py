"""Preview explicitly supplied source URLs; never search or guess another work."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from . import tvn
from .output_paths import KST
from .tving import _get_text, normalize_content_url, parse_detail_raw
from .tving_batch import CATEGORIES, _category_url, _listing_page, category_name


def inspect_official_url(url: str, kind: str, category: str) -> dict[str, Any]:
    result: dict[str, Any] = {"url": url, "kind": kind, "status": "ready",
                              "checked_at": datetime.now(KST).isoformat()}
    if kind == "tving_detail":
        info = parse_detail_raw(_get_text(url))["content_info"]
        _, requested = normalize_content_url(url)
        returned = info.get("code") if requested.startswith("E") else info["program_code"]
        if returned != requested:
            raise ValueError("입력 URL과 응답의 콘텐츠 ID가 다릅니다.")
        result.update(title=info.get("title"), program_id=info["program_code"],
                      site="TVING", scope="작품 상세", genre=info.get("genre_name"))
    elif kind == "tving_category":
        url = _category_url(url)
        subcategory = category_name(category, url)
        page = _listing_page(_get_text(url), url)
        result.update(site="TVING", title=f"{CATEGORIES[category]['name']} · {subcategory}",
                      scope="작품 목록", first_page_count=len(page["band"]["items"]),
                      category=category)
    elif kind.startswith("tvn_"):
        props = tvn.parse_page(tvn._get_text(url))
        if kind == "tvn_category":
            config = tvn._listing_config(props, url)
            result.update(title="tvN 프로그램 · " + config["channel_tab"], scope="프로그램 목록",
                          filters=config["filters"])
        else:
            fallback = props["fallback"]
            modules = [v for k, v in fallback.items() if k.isdigit() and isinstance(v, dict)]
            ids = {str(v["modulAttrInfo"]["pgmSeq"]) for v in modules
                   if isinstance(v.get("modulAttrInfo"), dict)
                   and v["modulAttrInfo"].get("pgmSeq") is not None}
            meta = (props.get("pageInfo") or {}).get("pageInfo") or {}
            title = next((v["data"].get("pgmNm") for v in modules
                          if isinstance(v.get("data"), dict) and v["data"].get("pgmNm")),
                         meta.get("snsTitTagCnts"))
            if not ids or not title:
                raise ValueError("tvN 작품 상세 데이터가 확인되지 않습니다.")
            result.update(title=title, program_ids=sorted(ids), genre=meta.get("repGenreInfo"),
                          scope="작품 상세")
        result["site"] = "tvN"
    else:
        raise ValueError("공식 사이트 URL 확인을 지원하지 않는 입력입니다.")
    return result
