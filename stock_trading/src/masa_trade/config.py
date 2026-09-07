"""設定ファイル(config/*.yaml)と環境変数の読み込みをまとめる場所。"""

from __future__ import annotations

import datetime as dt
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_DIR = Path(os.environ.get("MASA_TRADE_CONFIG_DIR", PROJECT_ROOT / "config"))


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass(frozen=True)
class WatchlistItem:
    symbol: str
    name: str


@dataclass(frozen=True)
class Settings:
    raw: dict[str, Any]
    watchlist: list[WatchlistItem]
    config_dir: Path

    @property
    def masa_logic(self) -> dict[str, Any]:
        return self.raw["masa_logic"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def notify(self) -> dict[str, Any]:
        return self.raw["notify"]

    @property
    def logging(self) -> dict[str, Any]:
        return self.raw["logging"]

    def resolve_path(self, relative: str) -> Path:
        """config配下のyamlに書かれた相対パスを絶対パスに解決する。"""
        return (self.config_dir / relative).resolve()

    def now(self) -> dt.datetime:
        """app.timezone(既定 Asia/Tokyo)のタイムゾーン付き現在時刻を返す。"""
        tz_name = self.raw.get("app", {}).get("timezone", "Asia/Tokyo")
        return dt.datetime.now(tz=ZoneInfo(tz_name))


def load_settings(config_dir: str | Path | None = None) -> Settings:
    """.env を読み込んだうえで settings.yaml / watchlist.yaml をまとめて読み込む。"""
    load_dotenv(PROJECT_ROOT / ".env", override=False)

    directory = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    raw = _load_yaml(directory / "settings.yaml")
    watchlist_raw = _load_yaml(directory / "watchlist.yaml").get("watchlist", [])
    watchlist = [WatchlistItem(symbol=item["symbol"], name=item["name"]) for item in watchlist_raw]

    return Settings(raw=raw, watchlist=watchlist, config_dir=directory)
