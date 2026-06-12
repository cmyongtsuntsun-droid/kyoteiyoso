"""BoatraceOpenAPI からのデータ取得レイヤ。

設計書の方針に従い、自前クローリング負荷を避けて
BoatraceOpenAPI の静的 JSON (番組表/直前情報/結果) を参照する。
取得結果は data/raw/{kind}/{YYYYMMDD}.json にキャッシュする。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

from .constants import RAW_DIR

BASE_URL = "https://boatraceopenapi.github.io"
KINDS = ("programs", "previews", "results")
_USER_AGENT = "kyotei-yoso/0.1 (research)"


def api_url(kind: str, target: date | None = None) -> str:
    """対象日の API URL を返す。target=None は当日 (today.json)。"""
    if kind not in KINDS:
        raise ValueError(f"unknown kind: {kind}")
    if target is None:
        return f"{BASE_URL}/{kind}/v2/today.json"
    return f"{BASE_URL}/{kind}/v2/{target:%Y}/{target:%Y%m%d}.json"


def fetch_json(url: str, timeout: int = 30, retries: int = 2) -> dict | None:
    """URL から JSON を取得する。404 (未開催/未配信) は None を返す。"""
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return json.loads(res.read())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_error = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_error = e
        if attempt < retries:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"取得失敗: {url}") from last_error


class RawDataStore:
    """生 JSON のローカルキャッシュ付きフェッチャ。"""

    def __init__(self, raw_dir: Path = RAW_DIR) -> None:
        self.raw_dir = raw_dir

    def _cache_path(self, kind: str, target: date) -> Path:
        return self.raw_dir / kind / f"{target:%Y%m%d}.json"

    def load_day(self, kind: str, target: date) -> dict | None:
        """キャッシュ済みの1日分データを読む。なければ None。"""
        path = self._cache_path(kind, target)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if text else None

    def fetch_day(self, kind: str, target: date, force: bool = False) -> dict | None:
        """1日分を取得。キャッシュ優先 (force=True で再取得)。未開催日は None。"""
        if not force:
            cached = self.load_day(kind, target)
            if cached is not None:
                return cached
        data = fetch_json(api_url(kind, target))
        path = self._cache_path(kind, target)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 404 (未配信) も空ファイルとして記録し再アクセスを抑止する
        path.write_text(
            json.dumps(data, ensure_ascii=False) if data is not None else "",
            encoding="utf-8",
        )
        return data

    def fetch_range(
        self,
        start: date,
        end: date,
        kinds: tuple[str, ...] = KINDS,
        sleep_sec: float = 0.2,
        progress: bool = True,
    ) -> None:
        """start〜end (両端含む) の各種データを順次取得・キャッシュする。"""
        for target in iter_dates(start, end):
            for kind in kinds:
                cached = self._cache_path(kind, target).exists()
                self.fetch_day(kind, target)
                if not cached:
                    time.sleep(sleep_sec)
            if progress:
                print(f"  fetched {target:%Y-%m-%d}")


def iter_dates(start: date, end: date) -> Iterator[date]:
    """start〜end (両端含む) の日付を順に返す。"""
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def fetch_today(kind: str) -> dict | None:
    """当日データ (today.json) をキャッシュなしで取得する。"""
    return fetch_json(api_url(kind, None))
