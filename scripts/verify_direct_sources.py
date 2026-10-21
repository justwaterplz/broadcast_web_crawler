"""Bounded verification using explicit official URLs and a user-saved CJ ENM response."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from broadcast_web_crawler import cjenm, tving, tvn
from broadcast_web_crawler.output_paths import KST
from broadcast_web_crawler.tving_storage import write_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tving-url", action="append", default=[])
    parser.add_argument("--tvn-url", action="append", default=[])
    parser.add_argument("--cjenm-url")
    parser.add_argument("--cjenm-response", type=Path)
    parser.add_argument("--characters-response", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.output_dir
    root.mkdir(parents=True, exist_ok=True)
    report = {"checked_at": datetime.now(KST).isoformat(), "automatic_title_search": False,
              "identity_matching": "explicit source URLs; no cross-source merge", "sources": []}
    for number, url in enumerate(args.tvn_url, 1):
        row = {"source": "tvn", "url": url}
        try:
            path = root / f"tvn-{number}" / "metadata.json"
            bundle = tvn.collect_program(url, path)
            view = tvn.display_content(bundle)
            row.update(status="collected", title=view["title"], metadata_file=str(path),
                       preview_count=len(view["episodes"]),
                       character_count=len(view.get("characters") or []),
                       complete_episode_list=bundle["collection"]["complete_episode_list"],
                       fields=[k for k, v in view.items() if v not in (None, [], "")])
        except Exception as exc:
            row.update(status="error", error=str(exc))
        report["sources"].append(row)
        write_bundle(root / "verification.json", report)
    for number, url in enumerate(args.tving_url, 1):
        row = {"source": "tving", "url": url}
        try:
            captured = tving.collect_program_with_report(url, root / f"tving-{number}")
            info = captured["bundle"]["contentInfo"]
            episodes = captured["episode_list"]
            country_pattern = r"(?:^|_)(?:country|nation|nationality|language|lang)(?:_|$)"
            country_fields = {k: v for k, v in info.items() if re.search(country_pattern, k, re.I)}
            row.update(status="collected", title=info["title"], fields=list(info),
                       episode_count=episodes["collected_count"],
                       total_count=episodes["total_count"],
                       complete=episodes["complete_for_current_api_listing"],
                       synopsis_count=sum(bool(e.get("synopsis")) for e in episodes["episodes"]),
                       country_source_fields=country_fields, country_classification="not_inferred")
        except Exception as exc:
            row.update(status="error", error=str(exc))
        report["sources"].append(row)
        write_bundle(root / "verification.json", report)
    if args.cjenm_response:
        original = json.loads(args.cjenm_response.read_text(encoding="utf-8-sig"))
        people = (json.loads(args.characters_response.read_text(encoding="utf-8-sig"))
                  if args.characters_response else None)
        imported = cjenm.import_saved_responses(args.cjenm_url, original, root / "cjenm",
                                                characters=people, confirmed_target=True)
        report["sources"].append({"source": "cjenm", "url": args.cjenm_url,
            "status": "saved_response_imported", "capture_time": None,
            "source_file": str(args.cjenm_response),
            "network_requests": 0, "metadata_file": str(Path(imported["output_dir"]) /
                                                         imported["metadata_file"]),
            "title": original["result"]["data"]["pgmNm"]})
    write_bundle(root / "verification.json", report)
    # Compare explicitly supplied samples only. Source response documents stay untouched.
    first_tvn = root / "tvn-1" / "metadata.json"
    first_tving = root / "tving-1" / "metadata.json"
    if first_tvn.exists() and first_tving.exists() and args.cjenm_response:
        a = json.loads(first_tvn.read_text(encoding="utf-8"))
        b = json.loads(first_tving.read_text(encoding="utf-8"))
        cj = original["result"]["data"]
        links = []
        def walk(value, path=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(child, path + "." + key)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    walk(child, path + f"[{index}]")
            elif isinstance(value, str) and value.startswith("https://www.tving.com/contents/"):
                links.append({"path": path, "url": value})
        walk(a["modules"], "modules")
        target = b["collection"]["source_url"]
        compared = {"title": cj["pgmNm"], "automatic_title_search": False,
            "same_work_evidence": {
                "cjenm_explicit_replay_url": cj.get("pgmReplayUrlAddr"),
                "tvn_explicit_replay_urls": links, "tving_input_url": target,
                "official_links_agree": cj.get("pgmReplayUrlAddr") == target
                and any(link["url"] == target for link in links)},
            "sources": [
                {"source": "CJ ENM", "program_id": cj["pgmSeq"],
                 "acquisition": "existing saved response; not a fresh crawl",
                 "episode_count_field": cj.get("allEpino"),
                 "episode_synopses": 0, "original_file": str(args.cjenm_response)},
                {"source": "TVING", "program_id": b["contentInfo"]["program_code"],
                 "cast_count": len(b["contentInfo"].get("actor") or []),
                 "creator_source_field": "director", "roles_inferred": False,
                 "episode_synopses": len(b["episodeApi"]["body"]["result"]),
                 "complete_listing": b["collection"]["complete_for_current_api_listing"]},
                {"source": "tvN", "program_ids": a["collection"]["program_ids"],
                 "character_count": len(tvn.display_content(a)["characters"]),
                 "episode_previews": len(tvn.display_content(a)["episodes"]),
                 "preview_listing": a["collection"].get("preview_listing"),
                 "screenplay_collected": False}],
            "country_filtering": "not inferred from channel, title or original flags",
            "raw_documents_merged": False}
        write_bundle(root / "source-comparison.json", compared)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
