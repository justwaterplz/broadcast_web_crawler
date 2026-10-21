"""Bounded same-origin traversal with an optional Playwright runtime."""

from __future__ import annotations

import asyncio
import importlib
import time
from collections import deque
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import Field

from .contracts import Contract
from .policy import CrawlAccessPolicy
from .urls import canonicalize_url, same_origin, score_program_url


class CrawlPolicy(Contract):
    max_pages: int = Field(default=100, ge=1)
    max_depth: int = Field(default=4, ge=0)
    max_discovered_urls: int = Field(default=10_000, ge=1)
    max_links_per_page: int = Field(default=2_000, ge=1)
    max_duration_seconds: float = Field(default=300, gt=0)
    navigation_timeout_ms: int = Field(default=30_000, ge=1)
    max_response_bytes: int = Field(default=5_000_000, ge=1)
    max_total_bytes: int = Field(default=100_000_000, ge=1)
    scroll_rounds: int = Field(default=4, ge=0, le=20)
    scroll_wait_ms: int = Field(default=400, ge=0)
    pagination_rounds: int = Field(default=3, ge=0, le=20)
    max_images_per_page: int = Field(default=100, ge=0, le=1_000)
    program_score_threshold: float = Field(default=2.0, ge=0)
    capture_resource_types: tuple[str, ...] = ("document", "xhr", "fetch", "image")
    blocked_resource_types: tuple[str, ...] = ("font", "media")
    pagination_selectors: tuple[str, ...] = (
        "button:has-text('더보기')",
        "button:has-text('More')",
        "button[aria-label*='next' i], [role='button'][aria-label*='next' i]",
    )
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class ResponseCapture:
    page_url: str
    url: str
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    resource_type: str


class CaptureHook(Protocol):
    def __call__(self, capture: ResponseCapture) -> Awaitable[None]: ...


@dataclass(frozen=True, slots=True)
class RawPage:
    url: str
    depth: int
    status: int | None
    score: float
    html: bytes
    links: tuple[str, ...]
    images: tuple[RawImage, ...] = ()


@dataclass(frozen=True, slots=True)
class RawImage:
    url: str
    alt: str
    width: int
    height: int
    kind: str


@dataclass(frozen=True, slots=True)
class CrawlOutput:
    start_url: str
    pages: tuple[RawPage, ...]
    program_urls: tuple[str, ...]
    skipped_urls: tuple[str, ...]
    total_bytes: int
    elapsed_seconds: float


class _ByteBudget:
    def __init__(self, maximum: int) -> None:
        self.maximum = maximum
        self.used = 0
        self._lock = asyncio.Lock()

    async def reserve(self, amount: int) -> bool:
        async with self._lock:
            if amount < 0 or self.used + amount > self.maximum:
                return False
            self.used += amount
            return True


def _html_candidate(url: str) -> bool:
    path = url.split("?", 1)[0].casefold()
    return not path.endswith(
        (
            ".7z",
            ".avi",
            ".css",
            ".csv",
            ".doc",
            ".docx",
            ".gif",
            ".gz",
            ".ico",
            ".jpeg",
            ".jpg",
            ".js",
            ".json",
            ".m4a",
            ".mkv",
            ".mov",
            ".mp3",
            ".mp4",
            ".pdf",
            ".png",
            ".ppt",
            ".pptx",
            ".rar",
            ".svg",
            ".tar",
            ".webp",
            ".xls",
            ".xlsx",
            ".xml",
            ".zip",
        )
    )


def normalize_links(
    links: Sequence[tuple[str, str]],
    *,
    page_url: str,
    origin_url: str,
    limit: int | None = None,
) -> tuple[tuple[str, str], ...]:
    """Canonicalize and de-duplicate crawlable same-origin links."""
    unique: dict[str, str] = {}
    for href, text in links:
        canonical = canonicalize_url(href, base_url=page_url)
        if (
            canonical
            and same_origin(canonical, origin_url)
            and _html_candidate(canonical)
            and canonical not in unique
        ):
            unique[canonical] = " ".join(text.split())
            if limit is not None and len(unique) >= limit:
                break
    return tuple(sorted(unique.items()))


class PlaywrightCrawler:
    def __init__(
        self,
        policy: CrawlPolicy | None = None,
        access_policy: CrawlAccessPolicy | None = None,
    ) -> None:
        self.policy = policy or CrawlPolicy()
        self.access_policy = access_policy

    async def crawl(
        self,
        start_url: str,
        *,
        hooks: Sequence[CaptureHook] = (),
    ) -> CrawlOutput:
        start = canonicalize_url(start_url)
        if start is None:
            raise ValueError("start_url must be an absolute HTTP(S) URL")
        if self.access_policy is not None and not self.access_policy.allows(start):
            raise PermissionError("start_url is blocked by the crawl access policy")
        try:
            playwright_api = importlib.import_module("playwright.async_api")
        except ModuleNotFoundError as error:
            raise RuntimeError(
                "Playwright is optional; install with `pip install -e '.[crawl]'` "
                "and run `playwright install chromium`"
            ) from error

        started = time.monotonic()
        budget = _ByteBudget(self.policy.max_total_bytes)
        pages: list[RawPage] = []
        programs: set[str] = set()
        skipped: set[str] = set()
        pending: deque[tuple[str, int]] = deque([(start, 0)])
        seen: set[str] = {start}
        response_tasks: set[asyncio.Task[None]] = set()

        async with playwright_api.async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            context_options = (
                {"user_agent": self.policy.user_agent} if self.policy.user_agent else {}
            )
            context = await browser.new_context(**context_options)
            page = await context.new_page()
            page.set_default_navigation_timeout(self.policy.navigation_timeout_ms)

            async def route_handler(route: Any) -> None:
                if route.request.resource_type in self.policy.blocked_resource_types:
                    await route.abort()
                else:
                    await route.continue_()

            await page.route("**/*", route_handler)

            async def capture_response(response: Any, owner_url: str) -> None:
                resource_type = str(response.request.resource_type)
                if resource_type not in self.policy.capture_resource_types:
                    return
                headers = {
                    str(key).casefold(): str(value) for key, value in response.headers.items()
                }
                declared = headers.get("content-length")
                if (
                    declared
                    and declared.isdigit()
                    and int(declared) > self.policy.max_response_bytes
                ):
                    return
                try:
                    body = await response.body()
                except Exception:
                    return
                if len(body) > self.policy.max_response_bytes or not await budget.reserve(
                    len(body)
                ):
                    return
                capture = ResponseCapture(
                    page_url=owner_url,
                    url=canonicalize_url(response.url) or str(response.url),
                    status=int(response.status),
                    headers=tuple(sorted(headers.items())),
                    body=body,
                    resource_type=resource_type,
                )
                await asyncio.gather(*(hook(capture) for hook in hooks))

            def schedule_response(response: Any) -> None:
                owner_url = canonicalize_url(response.request.frame.url) or start
                task = asyncio.create_task(capture_response(response, owner_url))
                response_tasks.add(task)

            if hooks:
                page.on("response", schedule_response)

            try:
                while pending and len(pages) < self.policy.max_pages:
                    if time.monotonic() - started >= self.policy.max_duration_seconds:
                        skipped.update(url for url, _ in pending)
                        break
                    url, depth = pending.popleft()
                    if self.access_policy is not None and not self.access_policy.allows(url):
                        skipped.add(url)
                        continue
                    try:
                        if self.access_policy is not None and pages:
                            await asyncio.sleep(
                                self.access_policy.min_request_interval_seconds
                            )
                        response = await page.goto(url, wait_until="domcontentloaded")
                        status = int(response.status) if response else None
                        anchors = await self._expand_and_collect(page)
                        current_url = canonicalize_url(page.url) or url
                        if not same_origin(current_url, start):
                            skipped.add(url)
                            continue
                        normalized = normalize_links(
                            anchors,
                            page_url=current_url,
                            origin_url=start,
                            limit=self.policy.max_links_per_page,
                        )
                        images = await self._collect_images(
                            page,
                            origin_url=start,
                            limit=self.policy.max_images_per_page,
                        )
                        html = (await page.content()).encode("utf-8")
                    except Exception:
                        skipped.add(url)
                        continue
                    if len(html) > self.policy.max_response_bytes or not await budget.reserve(
                        len(html)
                    ):
                        skipped.add(url)
                        continue

                    score = score_program_url(current_url) + await self._score_page(page)
                    if score >= self.policy.program_score_threshold:
                        programs.add(current_url)
                    links = tuple(link for link, _ in normalized)
                    pages.append(
                        RawPage(
                            url=current_url,
                            depth=depth,
                            status=status,
                            score=score,
                            html=html,
                            links=links,
                            images=images,
                        )
                    )
                    if depth >= self.policy.max_depth:
                        continue
                    for link, text in normalized:
                        if self.access_policy is not None and not self.access_policy.allows(link):
                            skipped.add(link)
                            continue
                        link_score = score_program_url(link, anchor_text=text)
                        if link_score >= self.policy.program_score_threshold:
                            programs.add(link)
                        if link not in seen:
                            if len(seen) >= self.policy.max_discovered_urls:
                                break
                            seen.add(link)
                            pending.append((link, depth + 1))
            finally:
                if response_tasks:
                    await asyncio.gather(*response_tasks)
                await context.close()
                await browser.close()

        return CrawlOutput(
            start_url=start,
            pages=tuple(pages),
            program_urls=tuple(sorted(programs)),
            skipped_urls=tuple(sorted(skipped)),
            total_bytes=budget.used,
            elapsed_seconds=time.monotonic() - started,
        )

    @staticmethod
    async def _score_page(page: Any) -> float:
        """Add explainable DOM signals to the URL score."""
        values = await page.evaluate(
            """() => ({
              jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')]
                .map(x => x.textContent || '').join(' '),
              text: (document.querySelector('main,article') || document.body)
                ?.innerText.slice(0, 20000) || ''
            })"""
        )
        haystack = f"{values.get('jsonld', '')} {values.get('text', '')}".casefold()
        score = 0.0
        if any(term in haystack for term in ("tvseries", "tvepisode", "방송 프로그램")):
            score += 2.0
        if any(term in haystack for term in ("출연", "제작진", "연출", "방송시간")):
            score += 1.0
        return score

    async def _expand_and_collect(self, page: Any) -> list[tuple[str, str]]:
        script = """els => els.map(a => [a.href || a.getAttribute('href'), a.innerText || ''])"""
        found: dict[str, str] = {}

        async def collect() -> None:
            values = await page.locator("a[href]").evaluate_all(script)
            for href, text in values:
                if href:
                    found[str(href)] = str(text)

        await collect()
        previous_height = -1
        for _ in range(self.policy.scroll_rounds):
            height = int(await page.evaluate("document.documentElement.scrollHeight"))
            await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            await page.wait_for_timeout(self.policy.scroll_wait_ms)
            await collect()
            new_height = int(await page.evaluate("document.documentElement.scrollHeight"))
            if new_height == height == previous_height:
                break
            previous_height = height

        for _ in range(self.policy.pagination_rounds):
            clicked = False
            for selector in self.policy.pagination_selectors:
                button = page.locator(selector).first
                if await button.count() and await button.is_visible() and await button.is_enabled():
                    await button.click()
                    await page.wait_for_timeout(self.policy.scroll_wait_ms)
                    await collect()
                    clicked = True
                    break
            if not clicked:
                break
        return list(found.items())

    @staticmethod
    async def _collect_images(
        page: Any,
        *,
        origin_url: str,
        limit: int,
    ) -> tuple[RawImage, ...]:
        if limit == 0:
            return ()
        values = await page.evaluate(
            """() => {
              const found = [];
              for (const image of document.images) {
                found.push({
                  url: image.currentSrc || image.src,
                  alt: image.alt || '',
                  width: image.naturalWidth || image.width || 0,
                  height: image.naturalHeight || image.height || 0,
                  kind: 'dom'
                });
              }
              for (const element of document.querySelectorAll('*')) {
                const value = getComputedStyle(element).backgroundImage;
                if (!value || value === 'none') continue;
                const rect = element.getBoundingClientRect();
                for (const match of value.matchAll(/url\\([\"']?([^\"')]+)[\"']?\\)/g)) {
                  found.push({
                    url: new URL(match[1], document.baseURI).href,
                    alt: element.getAttribute('aria-label') || '',
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    kind: 'css-background'
                  });
                }
              }
              return found;
            }"""
        )
        found: dict[str, RawImage] = {}
        for value in values:
            canonical = canonicalize_url(str(value.get("url", "")), base_url=page.url)
            if canonical is None or not same_origin(canonical, origin_url):
                continue
            candidate = RawImage(
                url=canonical,
                alt=" ".join(str(value.get("alt", "")).split()),
                width=max(int(value.get("width", 0)), 0),
                height=max(int(value.get("height", 0)), 0),
                kind=str(value.get("kind", "dom")),
            )
            previous = found.get(canonical)
            if previous is None or (
                candidate.width * candidate.height
                > previous.width * previous.height
            ):
                found[canonical] = candidate
            if len(found) >= limit:
                break
        return tuple(sorted(found.values(), key=lambda image: image.url))
