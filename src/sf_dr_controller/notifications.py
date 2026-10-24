"""Webhook notifier for Slack and Discord alerts."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("sf_dr_controller.notifications")


class NotificationService:
    """Dispatches formatted rich embed/card alerts to Slack or Discord webhooks."""

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url.strip() if webhook_url else None

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    def send_alert(self, title: str, message: str, level: str = "INFO", fields: dict[str, Any] | None = None) -> bool:
        """Sends an alert formatted appropriately for Discord or Slack."""
        if not self.enabled or not self.webhook_url:
            logger.debug("Notifications disabled or no webhook URL configured: %s - %s", title, message)
            return False

        fields = fields or {}
        color_map = {
            "INFO": 0x3498DB,      # Blue
            "WARNING": 0xF39C12,   # Amber/Orange
            "CRITICAL": 0xE74C3C,  # Crimson Red
            "SUCCESS": 0x2ECC71,   # Emerald Green
        }
        color = color_map.get(level.upper(), 0x3498DB)

        is_discord = "discord.com" in self.webhook_url or "discordapp.com" in self.webhook_url

        if is_discord:
            payload = {
                "embeds": [
                    {
                        "title": f"🛡️ {title}",
                        "description": message,
                        "color": color,
                        "fields": [{"name": k, "value": str(v), "inline": True} for k, v in fields.items()],
                        "footer": {"text": "Snowflake Cross-Cloud DR Controller • Enterprise Edition"},
                    }
                ]
            }
        else:
            # Slack / generic incoming webhook compatible
            attachment_fields = [{"title": k, "value": str(v), "short": True} for k, v in fields.items()]
            hex_color = f"#{color:06x}"
            payload = {
                "text": f"*{title}*\n{message}",
                "attachments": [
                    {
                        "color": hex_color,
                        "fields": attachment_fields,
                        "footer": "Snowflake Cross-Cloud DR Controller",
                    }
                ],
            }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Snowflake-DR-Controller/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("Notification sent successfully: %s (status %s)", title, resp.status)
                return True
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning("Failed to send webhook notification: %s", e)
            return False
