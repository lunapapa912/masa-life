"""週次記録(WeeklyRecord)のローカルJSONL永続化。

複数週にわたる記録を追記していくだけの単純な実装にとどめる。
統計集計(勝率・順位帯別など、【28.統計更新】)は今回のスコープ外で、
必要になった時点で load_weekly_records() の結果を集計する形で追加する。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from masa_trade.logic.weekly.schema import WeeklyRecord


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"JSON化できない型です: {type(value)!r}")


def save_weekly_record(record: WeeklyRecord, path: Path) -> None:
    """WeeklyRecordを1行のJSONとして追記する(JSONL形式)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, default=_json_default)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_weekly_records(path: Path) -> list[dict[str, Any]]:
    """保存済みのWeeklyRecordを辞書のリストとして読み込む。

    現状はdataclassへの復元は行わず、生の辞書を返す(統計集計・目視確認用)。
    プログラムからWeeklyRecordとして再利用する必要が出てきたら、
    ここにデシリアライズ処理を追加する。
    """
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                records.append(json.loads(stripped))
    return records
