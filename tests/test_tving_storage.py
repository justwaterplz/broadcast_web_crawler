import json

from broadcast_web_crawler.tving_storage import consolidate_run, display_content


def test_consolidation_preserves_sources_and_does_not_copy_display_metadata(tmp_path):
    old_run = tmp_path / "old"
    folder = old_run / "작품_20261012"
    folder.mkdir(parents=True)
    info = {"program_code": "P001", "title": "작품", "director": ["인명", "인명"],
            "broad_dt": 20260910, "extra": [False, None, "001", 0]}
    schema = [{"@type": "TVSeries", "name": "작품", "contentRating": "15"}]
    response = {"header": {"status": 200}, "body": {
        "total_count": 2, "has_more": "N", "result": [{
            "vod_name": {"ko": "같은 제목"},
            "episode": {"code": code, "synopsis": {"ko": "같은 설명"}},
        } for code in ("E001", "E002")],
    }}
    report = {"source_url": "https://www.tving.com/contents/P001",
              "collected_at": "2026-10-12T05:00:00+00:00",
              "acquisition_method": "embedded_page_data_and_episode_api"}
    for name, value in {
        "content-info.raw.json": info, "json-ld.raw.json": schema,
        "episodes-api.raw.json": response, "collection-report.json": report,
        "program.json": {"title": "processed title", "directors": ["processed person"]},
        "source-record.json": {"content": {"title": "another processed title"}},
    }.items():
        (folder / name).write_text(json.dumps(value), encoding="utf-8")
    original_bytes = {p.name: p.read_bytes() for p in folder.iterdir()}
    second = old_run / "AAA_20261012"
    second.mkdir()
    for path in folder.iterdir():
        value = json.loads(path.read_text(encoding="utf-8"))
        if path.name == "content-info.raw.json":
            value = {**value, "program_code": "P002", "title": "다른 작품"}
        (second / path.name).write_text(json.dumps(value), encoding="utf-8")
    (old_run / "collection-report.json").write_text(json.dumps({"programs": [
        {"folder": folder.name}, {"folder": second.name},
    ]}), encoding="utf-8")
    output = consolidate_run(old_run, tmp_path / "new")
    index = json.loads((output / "contents.json").read_text(encoding="utf-8"))
    path = output / index["programs"][0]["metadata_file"]
    bundle = json.loads(path.read_text(encoding="utf-8"))
    assert bundle["contentInfo"] == info
    assert bundle["jsonLd"] == schema
    assert bundle["episodeApi"] == response
    assert "processed" not in json.dumps(bundle)
    assert [p.name for p in path.parent.iterdir()] == ["metadata.json"]
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == original_bytes
    assert len(display_content(bundle)["episodes"]) == 2
    assert set(index["programs"][0]) == {"title", "metadata_file"}
    assert [entry["title"] for entry in index["programs"]] == ["작품", "다른 작품"]
