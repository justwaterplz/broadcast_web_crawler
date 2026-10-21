from __future__ import annotations

from broadcast_web_crawler.main import build_app
from broadcast_web_crawler.settings import Settings


def test_composition_root_builds_without_browser_or_network(tmp_path) -> None:
    app = build_app(
        Settings(
            database_url=f"sqlite+pysqlite:///{tmp_path / 'metadata.db'}",
            object_store_root=tmp_path / "objects",
            llm_api_key="test-only",
        )
    )
    paths = {route.path for route in app.routes}
    assert {"/health", "/runs", "/runs/{run_id}"} <= paths
