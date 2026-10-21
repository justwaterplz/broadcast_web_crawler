from __future__ import annotations

import pytest
from pydantic import ValidationError

from broadcast_web_crawler.contracts import CrawlPhase, CrawlRun
from broadcast_web_crawler.crawler import normalize_links
from broadcast_web_crawler.urls import canonicalize_url, same_origin, score_program_url


def test_crawl_state_machine_is_immutable_and_validated() -> None:
    queued = CrawlRun(start_url="https://example.com")
    discovering = queued.transition(CrawlPhase.DISCOVERING)

    assert queued.phase is CrawlPhase.QUEUED
    assert discovering.phase is CrawlPhase.DISCOVERING
    assert discovering.transitions[0].from_phase is CrawlPhase.QUEUED
    with pytest.raises(ValueError, match="invalid crawl transition"):
        discovering.transition(CrawlPhase.COMPLETED)
    with pytest.raises(ValueError, match="require a reason"):
        discovering.transition(CrawlPhase.FAILED)
    with pytest.raises(ValidationError):
        CrawlRun(start_url="https://example.com", unexpected=True)  # type: ignore[call-arg]


def test_url_canonicalization_and_origin_policy() -> None:
    actual = canonicalize_url(
        "../shows//detail/?utm_source=x&id=7&b=2#cast",
        base_url="HTTPS://Example.COM:443/category/list",
    )
    assert actual == "https://example.com/shows/detail?b=2&id=7"
    assert same_origin(actual or "", "https://example.com/")
    assert not same_origin("http://example.com/", "https://example.com/")
    assert canonicalize_url("javascript:alert(1)") is None


def test_link_normalization_is_same_origin_and_deterministic() -> None:
    links = [
        ("/program/42?utm_campaign=x", " A show "),
        ("https://other.example/program/9", "Other"),
        ("/program/42", "Duplicate"),
        ("/poster.jpg", "Image"),
    ]
    assert normalize_links(
        links,
        page_url="https://example.com/category",
        origin_url="https://example.com/",
    ) == (("https://example.com/program/42", "A show"),)
    assert score_program_url("https://example.com/program/detail?id=42") >= 2
