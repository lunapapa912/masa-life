"""判定結果の通知。今はログ出力のみ。Slack/LINE/Emailは設定が有効な場合に追加実装する。"""

from __future__ import annotations

import logging

from masa_trade.config import Settings
from masa_trade.logic.masa import JudgeResult

logger = logging.getLogger(__name__)


def notify(results: list[JudgeResult], settings: Settings) -> None:
    if not settings.notify["enabled"]:
        return

    for result in results:
        logger.info(
            "%s: %s (score=%.2f)", result.symbol, result.signal.value, result.score
        )

    channels = settings.notify["channels"]
    if channels.get("slack"):
        _notify_slack(results)
    if channels.get("line"):
        _notify_line(results)
    if channels.get("email"):
        _notify_email(results)


def _notify_slack(results: list[JudgeResult]) -> None:
    # TODO: SLACK_WEBHOOK_URL を使って通知する
    raise NotImplementedError("Slack通知は未実装です")


def _notify_line(results: list[JudgeResult]) -> None:
    # TODO: LINE_NOTIFY_TOKEN を使って通知する
    raise NotImplementedError("LINE通知は未実装です")


def _notify_email(results: list[JudgeResult]) -> None:
    # TODO: EMAIL_SMTP_* を使って通知する
    raise NotImplementedError("メール通知は未実装です")
