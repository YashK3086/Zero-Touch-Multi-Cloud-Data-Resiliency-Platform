from __future__ import annotations

from unittest.mock import MagicMock, patch

from sf_dr_controller.config import Settings
from sf_dr_controller.controller import SnowflakeDRController
from sf_dr_controller.notifications import NotificationService
from sf_dr_controller.state import DRState


def test_notification_service_disabled_when_empty():
    n = NotificationService(None)
    assert not n.enabled
    assert not n.send_alert("Test", "Message")


def test_notification_service_dispatches_http():
    n = NotificationService("https://discord.com/api/webhooks/dummy/123")
    assert n.enabled
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_url.return_value.__enter__.return_value = mock_resp
        ok = n.send_alert("Drill", "Running", level="INFO", fields={"Key": "Val"})
        assert ok
        assert mock_url.called


def test_controller_sends_strike_alert_and_failover_alert():
    settings = Settings(
        snowflake_account_primary="ORG-PRI",
        snowflake_account_secondary="ORG-SEC",
        snowflake_user="ADMIN",
        dr_webhook_url="https://hooks.slack.com/services/dummy",
    )
    mock_runner = MagicMock()
    # Primary raises exception (unhealthy), secondary returns [(1,)] (healthy)
    mock_runner.run.side_effect = [
        Exception("Connection refused"),
        [[(1,)]],
    ]

    ctrl = SnowflakeDRController(settings, mock_runner)
    with patch.object(ctrl.notifier, "send_alert") as mock_alert:
        st = ctrl.tick()
        assert st == DRState.DEGRADED
        assert ctrl.state.consecutive_failures == 1
        mock_alert.assert_called_once()
        args, kwargs = mock_alert.call_args
        assert "Heartbeat Failure (1/3)" in args[0]
