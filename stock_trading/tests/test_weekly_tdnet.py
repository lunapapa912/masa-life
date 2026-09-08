"""logic/weekly/tdnet.py のユニットテスト。

実ネットワークには依存せず、requests.get をモックして
やのしんWEB-APIのレスポンス形式(日付範囲検索はフラット、list/recentは
{"Tdnet": {...}}でラップ)の両方を正しく解釈できることを確認する。
"""

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

from masa_trade.logic.weekly.tdnet import fetch_disclosures, filter_by_company_name, filter_up_to


def _mock_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


def test_fetch_disclosures_parses_flat_date_range_response():
    payload = {
        "total_count": 1,
        "items": [
            {
                "id": "1279636",
                "pubdate": "2026-09-07 15:30:00",
                "company_code": "278A0",
                "company_name": "Ｇ－テラドローン",
                "title": "第21回新株予約権の大量行使に関するお知らせ",
                "document_url": "https://www.release.tdnet.info/inbs/xxx.pdf",
            }
        ],
    }
    with patch("masa_trade.logic.weekly.tdnet.requests.get", return_value=_mock_response(payload)) as mock_get:
        records = fetch_disclosures(date(2026, 9, 7), date(2026, 9, 8))

    mock_get.assert_called_once()
    called_url = mock_get.call_args.args[0]
    assert "20260907-20260908" in called_url
    assert len(records) == 1
    assert records[0].company_name == "Ｇ－テラドローン"
    assert records[0].company_code == "278A0"
    assert records[0].pubdate == datetime(2026, 9, 7, 15, 30, tzinfo=records[0].pubdate.tzinfo)


def test_fetch_disclosures_parses_wrapped_tdnet_response():
    payload = {
        "items": [
            {
                "Tdnet": {
                    "id": "1",
                    "pubdate": "2026-09-08 09:00:00",
                    "company_code": "12340",
                    "company_name": "テスト株式会社",
                    "title": "業務提携に関するお知らせ",
                    "document_url": None,
                }
            }
        ]
    }
    with patch("masa_trade.logic.weekly.tdnet.requests.get", return_value=_mock_response(payload)):
        records = fetch_disclosures(date(2026, 9, 8), date(2026, 9, 8))

    assert len(records) == 1
    assert records[0].company_name == "テスト株式会社"
    assert records[0].title == "業務提携に関するお知らせ"


def test_filter_by_company_name_matches_prefix_variants():
    from masa_trade.logic.weekly.schema import DisclosureRecord

    records = [
        DisclosureRecord(
            company_name="Ｇ－テラドローン", title="A", pubdate=datetime(2026, 9, 7, 15, 30, tzinfo=UTC)
        ),
        DisclosureRecord(
            company_name="キャンドゥ", title="B", pubdate=datetime(2026, 9, 7, 14, 0, tzinfo=UTC)
        ),
    ]
    matched = filter_by_company_name(records, "テラドローン")
    assert [r.title for r in matched] == ["A"]


def test_filter_up_to_excludes_future_disclosures():
    from masa_trade.logic.weekly.schema import DisclosureRecord

    early = DisclosureRecord(company_name="X", title="早い開示", pubdate=datetime(2026, 9, 7, 10, 0, tzinfo=UTC))
    late = DisclosureRecord(company_name="X", title="遅い開示", pubdate=datetime(2026, 9, 7, 16, 0, tzinfo=UTC))
    cutoff = datetime(2026, 9, 7, 11, 30, tzinfo=UTC)  # 前引け時点

    result = filter_up_to([early, late], cutoff)
    assert [r.title for r in result] == ["早い開示"]
