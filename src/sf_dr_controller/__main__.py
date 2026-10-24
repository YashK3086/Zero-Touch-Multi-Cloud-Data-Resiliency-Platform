"""CLI entry point:  python -m sf_dr_controller <command>

Commands:
  check              Probe both accounts once (+ replication lag with --lag)
  run                Continuous monitoring loop with automatic failover
  failover           Manually fail over to the secondary (use --dry-run first!)
  failback           Manually fail back to the original primary
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import Settings
from .connection import SnowflakeSqlRunner
from .controller import SnowflakeDRController
from .failover import FailoverExecutor
from .health import HealthProber
from .logging_setup import configure_logging


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sf_dr_controller", description="Snowflake multi-cloud DR controller")
    p.add_argument("--log-level", default="INFO")
    p.add_argument("--plain-logs", action="store_true", help="human-readable logs instead of JSON")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="probe both accounts once")
    c.add_argument("--lag", action="store_true", help="also measure replication lag (uses warehouse credits)")

    r = sub.add_parser("run", help="continuous monitoring loop")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--max-ticks", type=int, default=None)

    d = sub.add_parser("daemon", help="autonomous watchdog sentry daemon mode")
    d.add_argument("--interval", type=float, default=10.0, help="heartbeat probe interval in seconds (default: 10)")
    d.add_argument("--strikes", type=int, default=3, help="consecutive failures before failover (default: 3)")
    d.add_argument("--dry-run", action="store_true")
    d.add_argument("--max-ticks", type=int, default=None)

    for name in ("failover", "failback"):
        f = sub.add_parser(name)
        f.add_argument("--dry-run", action="store_true")
        f.add_argument("--yes", action="store_true", help="skip confirmation prompt")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configure_logging(args.log_level, json_output=not args.plain_logs)
    settings = Settings()  # type: ignore[call-arg]
    if getattr(args, "dry_run", False):
        settings.dr_dry_run = True
    runner = SnowflakeSqlRunner(settings.dr_probe_timeout_seconds)

    if args.command == "check":
        prober = HealthProber(runner)
        p, s = prober.probe_both(settings.primary, settings.secondary)
        out = {"primary": p.to_dict(), "secondary": s.to_dict()}
        if args.lag:
            out["replication_lag_seconds"] = prober.replication_lag_seconds(
                settings.secondary, settings.snowflake_database, settings.snowflake_failover_group_name
            )
        print(json.dumps(out, indent=2))
        return 0 if p.healthy and s.healthy else 1

    if args.command in ("run", "daemon"):
        if args.command == "daemon":
            if getattr(args, "interval", None) is not None:
                settings.dr_probe_interval_seconds = args.interval
            if getattr(args, "strikes", None) is not None:
                settings.dr_failure_threshold = args.strikes
        SnowflakeDRController(settings, runner).run_forever(max_ticks=args.max_ticks)
        return 0

    failover_runner = SnowflakeSqlRunner(120)
    executor = FailoverExecutor(
        failover_runner,
        settings.snowflake_failover_group_name,
        settings.snowflake_redirect_connection_name,
        dry_run=settings.dr_dry_run,
    )
    target = settings.secondary if args.command == "failover" else settings.primary
    if not (args.yes or settings.dr_dry_run):
        answer = input(f"Promote {target.identifier} to PRIMARY ({args.command})? Type 'yes': ")
        if answer.strip().lower() != "yes":
            print("aborted")
            return 2
    report = executor.failover(target) if args.command == "failover" else executor.failback(target)
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
