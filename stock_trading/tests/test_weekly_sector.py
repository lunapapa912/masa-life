"""logic/weekly/sector.py のユニットテスト。

ネットワークには依存せず、openpyxlで組み立てた小さなxlsxをバイト列化して
parse_sector_master() に渡す。resolve_sector() の名寄せ(完全一致・エイリアス・
部分一致)を確認する。
"""

from io import BytesIO

import openpyxl
import pytest

from masa_trade.logic.weekly.sector import parse_sector_master, resolve_sector


def _build_master_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["日付", "コード", "銘柄名", "市場・商品区分", "33業種コード", "33業種区分", "17業種コード", "17業種区分", "規模コード", "規模区分"])
    ws.append([20260831, 8995, "誠建設工業", "スタンダード（内国株式）", 8050, "不動産業", 17, "不動産", "-", "-"])
    ws.append([20260831, 4588, "オンコリスバイオファーマ", "グロース（内国株式）", 3250, "医薬品", 5, "医薬品", "-", "-"])
    ws.append([20260831, "278A", "Ｔｅｒｒａ　Ｄｒｏｎｅ", "グロース（内国株式）", 3750, "精密機器", 9, "電機・精密", "-", "-"])
    ws.append([20260831, 1305, "ｉＦｒｅｅＥＴＦ　ＴＯＰＩＸ", "ETF・ETN", "-", "-", "-", "-", "-", "-"])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.fixture
def master() -> dict[str, str]:
    return parse_sector_master(_build_master_xlsx_bytes())


def test_parse_sector_master_excludes_etf_rows(master):
    assert master["誠建設工業"] == "不動産業"
    assert master["オンコリスバイオファーマ"] == "医薬品"
    assert "ｉＦｒｅｅＥＴＦ　ＴＯＰＩＸ" not in master


def test_resolve_sector_exact_match(master):
    assert resolve_sector("誠建設工業", master) == "不動産業"


def test_resolve_sector_partial_match(master):
    # 週間ランキング画像上は「オンコリスバイオ」(正式名称の一部)。
    assert resolve_sector("オンコリスバイオ", master) == "医薬品"


def test_resolve_sector_via_alias(master):
    # 「テラドローン」はJPX正式名称が英語表記「Ｔｅｒｒａ　Ｄｒｏｎｅ」のため
    # 部分一致では引けず、SECTOR_NAME_ALIASES経由でのみ解決できる。
    assert resolve_sector("テラドローン", master) == "精密機器"


def test_resolve_sector_returns_none_when_not_found(master):
    assert resolve_sector("存在しない銘柄", master) is None
