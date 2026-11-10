from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from sf_dr_controller.workloads.cataloger import WorkloadCataloger, WorkloadSpec
from sf_dr_controller.workloads.hydrator import WorkloadHydrator
from sf_dr_controller.workloads.translator import CrossCloudTranslator


def test_workload_hydrator_local_fallback(tmp_path: Path):
    spec = WorkloadSpec(
        name="paysecure-api",
        image="ghcr.io/yashk3086/paysecure-api:1.0.0",
        port=8080,
    )
    mock_cataloger = MagicMock(spec=WorkloadCataloger)
    mock_cataloger.discover_specs.return_value = [spec]

    hydrator = WorkloadHydrator(
        subscription_id="dummy-sub-id",
        resource_group="sf-dr-rg",
        cataloger=mock_cataloger,
        translator=CrossCloudTranslator(),
    )

    # Test single workload hydration
    res = hydrator.hydrate_workload(spec, target_replicas=1)
    assert res["status"] == "HYDRATED"
    assert res["active_replicas"] == 1
    assert res["workload"] == "paysecure-api"
    assert "duration_seconds" in res

    # Test hydrate all
    all_res = hydrator.hydrate_all(target_replicas=1)
    assert all_res["status"] == "COMPLETED"
    assert all_res["workloads_count"] == 1
    assert all_res["hydration_rto_seconds"] >= 0.0


def test_workload_hydrator_azure_arm_rest_mock():
    spec = WorkloadSpec(
        name="paysecure-api",
        image="ghcr.io/yashk3086/paysecure-api:1.0.0",
        port=8080,
    )
    hydrator = WorkloadHydrator(
        subscription_id="1fbaecf5-392d-4648-9f2e-4d694cfc0b83",
        resource_group="sf-dr-rg",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("os.getenv", side_effect=lambda k, default=None: "mock-bearer-token" if "BEARER" in k else default):
        with patch("requests.patch", return_value=mock_resp) as mock_patch:
            res = hydrator.hydrate_workload(spec, target_replicas=1)
            assert res["status"] == "HYDRATED"
            assert res["mode"] == "AZURE_ARM_REST"
            mock_patch.assert_called_once()

