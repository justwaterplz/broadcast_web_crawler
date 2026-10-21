"""Explicit crawl-access policy evaluated before any URL is queued."""

from __future__ import annotations

import re
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from pydantic import Field, PrivateAttr

from .contracts import Contract
from .urls import canonicalize_url, same_origin


class CrawlAccessPolicy(Contract):
    """Per-job legal and resource policy.

    Callers are responsible for obtaining terms/permission. ``robots_txt`` can be
    recorded with the job so a run remains auditable even if robots.txt later changes.
    """

    origin_url: str
    user_agent: str = "broadcast-metadata-research-bot"
    obey_robots: bool = True
    robots_txt: str | None = None
    allow_path_patterns: tuple[str, ...] = ()
    deny_path_patterns: tuple[str, ...] = (
        r"/(?:login|logout|account|mypage)(?:/|$)",
        r"/(?:search|calendar)(?:/|$)",
    )
    min_request_interval_seconds: float = Field(default=0.5, ge=0)
    _robots: RobotFileParser | None = PrivateAttr(default=None)

    def model_post_init(self, __context: object) -> None:
        if self.robots_txt is not None:
            parser = RobotFileParser()
            parser.set_url(f"{self.origin_url.rstrip('/')}/robots.txt")
            parser.parse(self.robots_txt.splitlines())
            self._robots = parser

    def allows(self, url: str) -> bool:
        canonical = canonicalize_url(url)
        if canonical is None or not same_origin(canonical, self.origin_url):
            return False
        path = urlsplit(canonical).path
        if any(re.search(pattern, path, re.I) for pattern in self.deny_path_patterns):
            return False
        if self.allow_path_patterns and not any(
            re.search(pattern, path, re.I) for pattern in self.allow_path_patterns
        ):
            return False
        return not (
            self.obey_robots
            and self._robots is not None
            and not self._robots.can_fetch(self.user_agent, canonical)
        )
