"""TDnet適時開示情報の取得。

【データソース確認結果】(実装前の調査)
    - `pip install tdnet`: Python 3.12以上必須(本プロジェクトは3.11)かつ、
      XBRL財務諸表を丸ごとパース・タクソノミ解決する大規模ライブラリで、
      今回必要な「開示タイトル一覧」には過剰。不採用。
    - 公式サイト release.tdnet.info: このセッションの実行環境からは
      プロキシ越しに到達不可(CONNECT 502)。将来別環境で動かす場合は
      再検討の余地がある。
    - やのしんの非公式WEB-API(https://webapi.yanoshin.jp/): 無料・認証不要・
      到達確認済み。日付範囲を指定すると全市場分の開示をまとめて返すため、
      証券コードのマッピングなしに会社名の部分一致で絞り込める
      (週間ランキング画像には証券コードが載っていないことが多いため、
      これはむしろ好都合)。今回はこちらを採用する。

【レート制限への配慮】
    日付範囲を指定すれば1回のリクエストで全市場・複数日分が返るため、
    銘柄ごとに個別リクエストする必要はない。呼び出し側は日次バッチで
    1日1回程度の頻度に留めること(このモジュール自体はリトライやポーリングを
    行わない、単発のGETのみ)。
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import requests

from masa_trade.logic.weekly.schema import DisclosureRecord

_BASE_URL = "https://webapi.yanoshin.jp/webapi/tdnet/list/{date_range}.json"
_USER_AGENT = "masa-trade/0.1 (weekly-catalyst-scoring; https://github.com/)"
_JST = ZoneInfo("Asia/Tokyo")  # TDnetのpubdateは常に日本時間


def fetch_disclosures(start_date: date, end_date: date, timeout: float = 15.0) -> list[DisclosureRecord]:
    """指定期間(両端の日付を含む)の全市場のTDnet適時開示を1回のリクエストで取得する。

    Args:
        start_date: 取得開始日(この日を含む)。
        end_date: 取得終了日(この日を含む)。
        timeout: HTTPタイムアウト秒数。

    Returns:
        DisclosureRecordのリスト(pubdate降順、やのしんAPIの応答順)。
    """
    date_range = f"{start_date:%Y%m%d}-{end_date:%Y%m%d}"
    url = _BASE_URL.format(date_range=date_range)
    response = requests.get(url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
    response.raise_for_status()
    payload = response.json()

    records = []
    for item in payload.get("items", []):
        raw = item.get("Tdnet", item)  # list/recent系は{"Tdnet": {...}}、日付範囲系はフラット
        records.append(
            DisclosureRecord(
                company_name=raw["company_name"],
                title=raw["title"],
                pubdate=datetime.strptime(raw["pubdate"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=_JST),
                company_code=raw.get("company_code"),
                source_url=raw.get("document_url"),
            )
        )
    return records


def filter_by_company_name(disclosures: list[DisclosureRecord], company_name: str) -> list[DisclosureRecord]:
    """会社名の部分一致で絞り込む。

    TDnet上の表記(例: "Ｇ－テラドローン")と週間ランキング画像上の表記
    (例: "テラドローン")で接頭辞・全角/略称の差異があるため、双方向の部分一致で見る。
    """
    return [d for d in disclosures if company_name in d.company_name or d.company_name in company_name]


def filter_up_to(disclosures: list[DisclosureRecord], cutoff: datetime) -> list[DisclosureRecord]:
    """指定時刻以前(cutoffを含む)に公表された開示だけを残す(LOOK-AHEAD BIAS禁止用)。"""
    return [d for d in disclosures if d.pubdate <= cutoff]
