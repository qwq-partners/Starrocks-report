"""Slack notification for daily reports."""

import aiohttp
import structlog

logger = structlog.get_logger()


class SlackNotifier:
    def __init__(self, webhook_url: str, channel: str = "#data-platform-news"):
        self.webhook_url = webhook_url
        self.channel = channel

    async def send_report_summary(self, report_date: str, stats: dict, highlights: list[dict]):
        """Send a summary of the daily report to Slack."""
        if not self.webhook_url:
            logger.warning("slack_webhook_not_configured")
            return

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Daily Data Platform Report - {report_date}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*수집:* {stats.get('total', 0)}건 | "
                        f"*신규:* {stats.get('new', 0)}건 | "
                        f"*중복제거:* {stats.get('dedup', 0)}건"
                    ),
                },
            },
            {"type": "divider"},
        ]

        for i, h in enumerate(highlights[:5], 1):
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{i}. <{h['url']}|{h['title']}>\n>{h.get('summary', '')}",
                    },
                }
            )

        payload = {"channel": self.channel, "blocks": blocks}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status != 200:
                        logger.error("slack_send_failed", status=resp.status)
                    else:
                        logger.info("slack_notification_sent")
        except Exception as e:
            logger.error("slack_error", error=str(e))
