from sf_dr_controller.api import download_audit_pdf_report, get_onboarding_status
from sf_dr_controller.config import Settings
from sf_dr_controller.reports import generate_audit_pdf


def test_onboarding_status_endpoint():
    status = get_onboarding_status()
    assert "is_configured" in status
    assert "primary_account" in status
    assert "secondary_account" in status


def test_pdf_report_generation_binary():
    pdf_bytes = generate_audit_pdf(migrations=[
        {
            "id": "MIG-TEST-001",
            "event": "Emergency Failover Drill",
            "direction": "AWS -> Azure",
            "timestamp": "2026-11-04 18:00",
            "duration": "1.42s",
            "rpo": "0s",
            "status": "PASS",
        }
    ])
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes
    assert len(pdf_bytes) > 1000


def test_pdf_report_endpoint():
    res = download_audit_pdf_report()
    assert res.status_code == 200
    assert res.media_type == "application/pdf"
    assert "Auto_Failover_DR_Audit_Report.pdf" in res.headers["content-disposition"]
    assert res.body.startswith(b"%PDF-1.4")


def test_settings_is_configured_property(settings):
    # Valid configured settings
    assert settings.is_configured is True

    # Empty settings
    empty_settings = Settings(
        snowflake_account_primary="",
        snowflake_user_primary="",
        snowflake_password_primary="",
        snowflake_account_secondary="",
        snowflake_user_secondary="",
        snowflake_password_secondary="",
        _env_file=None,
    )
    assert empty_settings.is_configured is False
