"""Small, polite HTTP helper: retries with backoff, a shared User-Agent, and no secrets."""
from __future__ import annotations

import time

import httpx

USER_AGENT = "xaikg-research-artefact/0.1 (academic research; contact via repository)"


def get(url: str, *, params: dict | None = None, timeout: float = 60.0, retries: int = 4,
        headers: dict | None = None) -> httpx.Response:
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)
    delay = 2.0
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = httpx.get(url, params=params, timeout=timeout, headers=hdrs, follow_redirects=True)
            if r.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(f"{r.status_code} from {url}", request=r.request, response=r)
            r.raise_for_status()
            return r
        except (httpx.HTTPError, httpx.TransportError) as e:  # network blips are expected here
            last = e
            if attempt == retries - 1:
                break
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last}")
