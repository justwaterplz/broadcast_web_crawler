from __future__ import annotations

from broadcast_web_crawler.metrics import quality_report
from broadcast_web_crawler.models import NormalizationResult
from broadcast_web_crawler.policy import CrawlAccessPolicy


def test_access_policy_enforces_origin_paths_and_robots() -> None:
    policy = CrawlAccessPolicy(
        origin_url="https://example.test/programs",
        robots_txt="User-agent: *\nDisallow: /private\n",
        allow_path_patterns=(r"^/(?:program|private)",),
    )
    assert policy.allows("https://example.test/program/42")
    assert not policy.allows("https://example.test/private/42")
    assert not policy.allows("https://example.test/search?q=show")
    assert not policy.allows("https://other.test/program/42")


def test_empty_quality_report_is_well_defined() -> None:
    report = quality_report(
        NormalizationResult(
            schema_version="1.0.0",
            entities=(),
            assertions=(),
        )
    )
    assert report.evidence_coverage == 1.0
    assert report.review_rate == 0.0
