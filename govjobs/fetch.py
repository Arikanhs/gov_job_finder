"""Polite HTTP: robots.txt checks, per-host rate limiting, and a disk cache.

Every network request in the tool goes through Fetcher so these rules can't be
skipped by accident.
"""
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests


class FetchError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status


class RobotsDisallowed(FetchError):
    pass


class Fetcher:
    def __init__(self, cfg: dict, log=print):
        h = cfg["http"]
        self.ua = h["user_agent"]
        self.min_interval = float(h["min_interval_seconds"])
        self.timeout = float(h["timeout_seconds"])
        self.ttl = {k: v * 3600 for k, v in h["cache_ttl_hours"].items()}
        self.cache_dir = Path(cfg["cache_dir"]) / "http"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = self.ua
        self._last = {}      # host -> monotonic time of last request
        self._robots = {}    # origin -> RobotFileParser | None (None = allow all)
        self.log = log
        self.stats = {"network": 0, "cached": 0}

    # ---- public API -------------------------------------------------------

    def get(self, url, *, kind="detail", headers=None, params=None, robots=True) -> str:
        return self._request("GET", url, kind=kind, headers=headers, params=params, robots=robots)

    def get_json(self, url, **kw):
        return json.loads(self.get(url, **kw))

    def post_json(self, url, payload, *, kind="listing", robots=True):
        body = json.dumps(payload, sort_keys=True)
        text = self._request("POST", url, kind=kind, data=body, robots=robots,
                             headers={"Content-Type": "application/json", "Accept": "application/json"})
        return json.loads(text)

    def allowed(self, url) -> bool:
        rp = self._robots_for(url)
        return rp is None or rp.can_fetch(self.ua, url)

    # ---- internals --------------------------------------------------------

    def _request(self, method, url, *, kind, headers=None, params=None, data=None, robots=True):
        if params:
            url = requests.Request("GET", url, params=params).prepare().url
        key = hashlib.sha256(f"{method} {url} {data or ''}".encode()).hexdigest()[:32]
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            c = json.loads(path.read_text())
            if time.time() - c["t"] < self.ttl.get(kind, self.ttl["detail"]):
                self.stats["cached"] += 1
                return c["text"]
        if robots and not self.allowed(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")
        self._throttle(url)
        try:
            r = self.session.request(method, url, headers=headers, data=data, timeout=self.timeout)
        except requests.RequestException as e:
            raise FetchError(f"{type(e).__name__}: {e}") from e
        self.stats["network"] += 1
        if r.status_code != 200:
            raise FetchError(f"HTTP {r.status_code} for {url}", r.status_code)
        if "challenge-platform" in r.text[:5000] or "<title>Just a moment" in r.text[:2000]:
            raise FetchError(f"bot challenge page at {url}", r.status_code)
        path.write_text(json.dumps({"t": time.time(), "url": url, "text": r.text}))
        return r.text

    def _throttle(self, url):
        host = urlsplit(url).netloc
        delay = self.min_interval
        rp = self._robots.get(self._origin(url))
        if rp is not None:
            cd = rp.crawl_delay(self.ua)
            if cd:
                delay = max(delay, float(cd))
        wait = self._last.get(host, 0) + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last[host] = time.monotonic()

    @staticmethod
    def _origin(url):
        p = urlsplit(url)
        return f"{p.scheme}://{p.netloc}"

    def _robots_for(self, url):
        origin = self._origin(url)
        if origin in self._robots:
            return self._robots[origin]
        rp = RobotFileParser()
        try:
            self._throttle(origin)
            r = self.session.get(origin + "/robots.txt", timeout=self.timeout)
            self.stats["network"] += 1
            if r.status_code >= 500 or "challenge-platform" in r.text[:5000]:
                raise FetchError(f"robots.txt unavailable at {origin} (HTTP {r.status_code})", r.status_code)
            ctype = r.headers.get("Content-Type", "")
            if r.status_code >= 400 or "html" in ctype:
                rp = None                      # no robots.txt -> everything allowed
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException as e:
            raise FetchError(f"robots.txt fetch failed at {origin}: {e}") from e
        self._robots[origin] = rp
        return rp
