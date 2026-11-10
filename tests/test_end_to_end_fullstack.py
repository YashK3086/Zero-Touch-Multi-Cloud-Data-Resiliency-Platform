from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from sf_dr_controller.api.state import state
from sf_dr_controller.api.workloads import get_live_workloads, run_synthetic_probe
from sf_dr_controller.workloads.cataloger import WorkloadCataloger, WorkloadSpec
from sf_dr_controller.workloads.hydrator import WorkloadHydrator
from sf_dr_controller.workloads.translator import CrossCloudTranslator


def test_end_to_end_fullstack_simulation(tmp_path: Path):
    """Simulates complete failover drill: Data promotion + container hydration + health probe."""
    spec = WorkloadSpec(
        name="paysecure-api",
        image="ghcr.io/yashk3086/paysecure-api:1.0.0",
        port=8080,
    )
    mock_cataloger = MagicMock(spec=WorkloadCataloger)
    mock_cataloger.discover_specs.return_value = [spec]

    hydrator = WorkloadHydrator(
        subscription_id="1fbaecf5-392d-4648-9f2e-4d694cfc0b83",
        cataloger=mock_cataloger,
        translator=CrossCloudTranslator(),
    )

    # 1. Trigger container hydration
    hydration_summary = hydrator.hydrate_all(target_replicas=1)
    assert hydration_summary["status"] == "COMPLETED"
    assert hydration_summary["workloads_count"] == 1
    assert hydration_summary["hydration_rto_seconds"] < 12.0  # Plan SLA Target: < 12s

    # 2. Test Workloads API Endpoints when UI is connected
    prev_connected = state.ui_connected
    prev_disc = state.last_discovery
    try:
        state.ui_connected = True
        state.last_discovery = {"aws": {"instances": []}, "azure": {}}
        with patch("sf_dr_controller.api.workloads.cataloger", mock_cataloger):
            data_empty = get_live_workloads()
            assert len(data_empty["workloads"]) == 0

            state.last_discovery = {
                "aws": {"instances": [{"instance_id": "i-0123456789abcdef0", "state": "running", "public_ip": "54.1.2.3", "vpc_id": "vpc-123"}]},
                "azure": {},
            }
            data = get_live_workloads()
            assert data["standby_mode"] == "PILOT_LIGHT_ZERO_IDLE_COST"
            assert len(data["workloads"]) == 1
            assert data["workloads"][0]["name"] == "paysecure-api"

            probe_data = run_synthetic_probe()
            assert probe_data["status"] == "PASS"
            assert probe_data["latency_ms"] > 0.0
    finally:
        state.ui_connected = prev_connected
        state.last_discovery = prev_disc
