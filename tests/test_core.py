import pytest

from sf_dr_controller import sql
from sf_dr_controller.config import Settings
from sf_dr_controller.state import Decision, DRState, FailoverStateMachine


@pytest.mark.parametrize("name", ["SF_DR_FAILOVER_GROUP", "a", "_x$1"])
def test_valid_identifiers(name):
    assert sql.validate_identifier(name) == name


@pytest.mark.parametrize("name", ["", "1abc", "x; DROP DATABASE y", "a b", "a'--", 'g"q'])
def test_rejects_injection(name):
    with pytest.raises(ValueError):
        sql.validate_identifier(name)


def test_statements():
    assert sql.promote_failover_group("G") == "ALTER FAILOVER GROUP G PRIMARY"
    assert sql.promote_connection("C") == "ALTER CONNECTION C PRIMARY"
    assert "REPLICATION_GROUP_REFRESH_HISTORY('G')" in sql.replication_lag("DB", "G")


def test_settings_reject_bad_group(settings):
    with pytest.raises(ValueError):
        Settings(**{**settings.model_dump(), "snowflake_failover_group_name": "x;drop", "_env_file": None})


def test_settings_reject_placeholder_account(settings):
    with pytest.raises(ValueError):
        Settings(**{**settings.model_dump(), "snowflake_account_primary": "<org>-<acct>", "_env_file": None})


def test_secret_not_in_repr(settings):
    assert "not-a-real-secret" not in repr(settings)
    assert "not-a-real-secret" not in repr(settings.primary)


def test_secondary_falls_back_to_shared_creds(settings):
    assert settings.secondary.user == "TEST_USER"
    assert settings.secondary.password == "not-a-real-secret"


class TestStateMachine:
    def test_threshold(self):
        sm = FailoverStateMachine(3)
        assert sm.observe(False) is Decision.NONE and sm.state is DRState.DEGRADED
        assert sm.observe(False) is Decision.NONE
        assert sm.observe(False) is Decision.FAILOVER and sm.state is DRState.FAILING_OVER

    def test_recovery_resets_counter(self):
        sm = FailoverStateMachine(2)
        sm.observe(False)
        sm.observe(True)
        assert sm.state is DRState.HEALTHY and sm.consecutive_failures == 0
        assert sm.observe(False) is Decision.NONE

    def test_no_failover_when_secondary_down(self):
        sm = FailoverStateMachine(1)
        assert sm.observe(False, secondary_healthy=False) is Decision.NONE
        assert sm.state is DRState.DEGRADED

    def test_latches_after_failover(self):
        sm = FailoverStateMachine(1)
        sm.observe(False)
        sm.mark_failover_result(True)
        assert sm.observe(True) is Decision.NONE and sm.state is DRState.FAILED_OVER

    def test_invalid_threshold(self):
        with pytest.raises(ValueError):
            FailoverStateMachine(0)
