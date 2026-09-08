"""JPX(日本取引所グループ)公式の33業種区分マスタの取得・名寄せ。

【経緯】
    当初はみんかぶの人気テーマランキング・株探のテーマ別銘柄一覧の利用を検討したが、
    みんかぶの利用規約フッターに「営業に利用することはもちろん、第三者へ提供する
    目的で情報を転用、複製、販売、加工、再利用及び再配信することを固く禁じます」
    と明記されているのを確認した。株探(kabutan.jp)はみんかぶと同一運営会社
    (MINKABU THE INFONOID, Inc.、両サイトのフッターに同一著作権表記)であり、
    同種の制限を受ける可能性が高い。今回作ろうとしているのは「取得したランキング
    情報をスコアに加工する」処理そのものであり、この禁止事項に抵触するため、
    両サイトは不採用とした。

    代わりに、JPXが無料公開している「東証上場銘柄一覧」
    (https://www.jpx.co.jp/markets/statistics-equities/misc/01.html、
    data_j.xlsx)を使う。取引所自身が公開する銘柄コード・33業種区分の
    単純な分類一覧であり、ランキング等の加工物ではない。毎月第3営業日に
    前月末データへ更新される。

【名寄せについて】
    週間ランキング画像上の銘柄名表記(カタカナ略称等)とJPXデータ上の正式名称
    (ローマ字表記や中点区切りを含む)には差異があるため、既知の対応を
    SECTOR_NAME_ALIASES に持たせ、それでも一致しない場合は部分一致で
    フォールバックする。新しい不一致が見つかったら随時追加すること。
"""

from __future__ import annotations

from io import BytesIO

import requests

_JPX_XLSX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xlsx"
_USER_AGENT = "masa-trade/0.1 (weekly-sector-scoring; https://github.com/)"

# 週間ランキング画像上の表記 ⇔ JPXデータ上の正式名称の既知の対応。
# 「エプリー」は2026-09-07週の実データ照合時、JPX名簿に該当が見つからず、
# 表記(「ブ」を「プ」と誤読した可能性)が近い「エブリー」(コード607A)を
# 暫定的に採用した。転記元の画像を再確認できる場合は要検証。
SECTOR_NAME_ALIASES: dict[str, str] = {
    "テラドローン": "Ｔｅｒｒａ　Ｄｒｏｎｅ",
    "エプリー": "エブリー",
    "カイオムバイオ": "カイオム・バイオサイエンス",
    "VRAIN Solution": "ＶＲＡＩＮ　Ｓｏｌｕｔｉｏｎ",
    "QDレーザ": "ＱＤレーザ",
    "INTLOOP": "ＩＮＴＬＯＯＰ",
    "スカパー": "スカパーＪＳＡＴ",
    "イメージ情報": "イメージ情報開発",
}


def download_sector_master_bytes(timeout: float = 30.0) -> bytes:
    """JPXのdata_j.xlsxをダウンロードする(単発のGETのみ、月1回程度の利用を想定)。"""
    response = requests.get(_JPX_XLSX_URL, timeout=timeout, headers={"User-Agent": _USER_AGENT})
    response.raise_for_status()
    return response.content


def parse_sector_master(xlsx_bytes: bytes) -> dict[str, str]:
    """xlsxのバイト列から {正式銘柄名: 33業種区分} の辞書を作る。

    列構成(JPX公表フォーマット): 日付, コード, 銘柄名, 市場・商品区分,
    33業種コード, 33業種区分, 17業種コード, 17業種区分, 規模コード, 規模区分。
    ETF・REIT等、業種区分が「-」の行は除外する。
    """
    import openpyxl  # 起動コストが大きいため遅延import

    workbook = openpyxl.load_workbook(BytesIO(xlsx_bytes), read_only=True)
    worksheet = workbook.active
    rows = worksheet.iter_rows(values_only=True)
    next(rows)  # ヘッダー行をスキップ

    master: dict[str, str] = {}
    for row in rows:
        name, sector = row[2], row[5]
        if name and sector and sector != "-":
            master[str(name)] = str(sector)
    return master


def fetch_sector_master(timeout: float = 30.0) -> dict[str, str]:
    """JPXの業種マスタをダウンロードしてパースする(ダウンロード+パースの一括ヘルパー)。"""
    return parse_sector_master(download_sector_master_bytes(timeout))


def resolve_sector(name: str, master: dict[str, str]) -> str | None:
    """週間ランキング画像上の銘柄名から33業種区分を引く。

    1. 完全一致 → 2. SECTOR_NAME_ALIASES経由の完全一致 → 3. 双方向部分一致、
    の順で試す。どれにも該当しなければNone(呼び出し側は中立点として扱う)。
    """
    if name in master:
        return master[name]

    aliased = SECTOR_NAME_ALIASES.get(name)
    if aliased and aliased in master:
        return master[aliased]

    for master_name, sector in master.items():
        if name in master_name or master_name in name:
            return sector
    return None
