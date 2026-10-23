from sf_dr_controller.controller import SnowflakeDRController
from sf_dr_controller.failover import FailoverExecutor
from sf_dr_controller.health import HealthProber
from sf_dr_controller.state import DRState


def test_probe_healthy_and_unhealthy(runner, settings):
    prober = HealthProber(runner)
    runner.healthy["primary"] = False
    p, s = prober.probe_both(settings.primary, settings.secondary)
    assert not p.healthy and "ConnectionError" in p.error
    assert s.healthy and s.error is None


def test_replication_lag(runner, settings):
    assert HealthProber(runner).replication_lag_seconds(settings.secondary, "DB", "G") == 42


def test_failover_order_runs_on_secondary(runner, settings):
    rep = FailoverExecutor(runner, "G", "C").failover(settings.secondary)
    assert rep.success
    assert runner.calls == [
        ("secondary", "ALTER FAILOVER GROUP G PRIMARY"),
        ("secondary", "ALTER CONNECTION C PRIMARY"),
    ]


def test_failover_stops_on_first_error(runner, settings):
    runner.fail_statements.add("ALTER FAILOVER GROUP G PRIMARY")
    rep = FailoverExecutor(runner, "G", "C").failover(settings.secondary)
    assert not rep.success and len(rep.steps) == 1 and rep.steps[0].error


def test_failback_sequence(runner, settings):
    rep = FailoverExecutor(runner, "G", "C").failback(settings.primary)
    assert rep.success and [c[1].split()[-1] for c in runner.calls] == ["REFRESH", "PRIMARY", "PRIMARY"]


def test_dry_run_executes_nothing(runner, settings):
    rep = FailoverExecutor(runner, "G", "C", dry_run=True).failover(settings.secondary)
    assert rep.success and rep.dry_run and runner.calls == []


def test_controller_end_to_end_failover(runner, settings):
    ctl = SnowflakeDRController(settings, runner)
    assert ctl.tick() is DRState.HEALTHY
    runner.healthy["primary"] = False
    states = []
    ctl.run_forever(max_ticks=10, on_tick=states.append)
    assert states == [DRState.DEGRADED, DRState.DEGRADED, DRState.FAILED_OVER]
    assert ctl.last_report and ctl.last_report.success
    assert ("secondary", "ALTER CONNECTION SF_DR_GLOBAL_REDIRECT PRIMARY") in runner.calls


def test_controller_auto_failover_disabled(runner, settings):
    settings.dr_auto_failover = False
    ctl = SnowflakeDRController(settings, runner)
    runner.healthy["primary"] = False
    for _ in range(3):
        ctl.tick()
    assert ctl.state.state is DRState.FAILING_OVER and ctl.last_report is None
    assert not any("ALTER" in c[1] for c in runner.calls)


def test_dual_outage_no_failover(runner, settings):
    ctl = SnowflakeDRController(settings, runner)
    runner.healthy.update(primary=False, secondary=False)
    for _ in range(5):
        ctl.tick()
    assert ctl.state.state is DRState.DEGRADED and ctl.last_report is None
