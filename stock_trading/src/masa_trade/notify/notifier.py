"""判定結果(CIO決裁書)の通知。今はログ出力のみ。Slack/LINE/Emailは設定が有効な場合に追加実装する。"""

from __future__ import annotations

import logging

from masa_trade.config import Settings
from masa_trade.logic.schema import CIODecisionMemo

logger = logging.getLogger(__name__)


def notify(results: list[CIODecisionMemo], settings: Settings) -> None:
    if not settings.notify["enabled"]:
        return

    for result in results:
        logger.info("\n%s", result.to_memo_text())

    channels = settings.notify["channels"]
    if channels.get("slack"):
        _notify_slack(results)
    if channels.get("line"):
        _notify_line(results)
    if channels.get("email"):
        _notify_email(results)


def _notify_slack(results: list[CIODecisionMemo]) -> None:
    # TODO: SLACK_WEBHOOK_URL を使って通知する
    raise NotImplementedError("Slack通知は未実装です")


def _notify_line(results: list[CIODecisionMemo]) -> None:
    # TODO: LINE_NOTIFY_TOKEN を使って通知する
    raise NotImplementedError("LINE通知は未実装です")


def _notify_email(results: list[CIODecisionMemo]) -> None:
    # TODO: EMAIL_SMTP_* を使って通知する
    raise NotImplementedError("メール通知は未実装です")
