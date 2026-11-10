from __future__ import annotations

import json
from pathlib import Path

from sf_dr_controller.workloads.cataloger import (
    WorkloadCataloger,
    WorkloadSpec,
)
from sf_dr_controller.workloads.translator import CrossCloudTranslator


def test_workload_spec_validation(tmp_path: Path):
    manifest = {
        "name": "paysecure-api",
        "version": "1.0.0",
        "image": "ghcr.io/yashk3086/paysecure-api:1.0.0",
        "port": 8080,
        "resources": {"cpu": 0.25, "memory": "0.5Gi"},
        "scale": {"min_replicas_standby": 0, "min_replicas_active": 1, "max_replicas": 5},
        "health_probe": {"path": "/health", "port": 8080},
        "env": {"CURRENT_CLOUD": "AWS", "SNOWFLAKE_DATABASE": "SF_DR_DEMO_DB"},
    }
    spec_file = tmp_path / "workload_spec.json"
    spec_file.write_text(json.dumps(manifest), encoding="utf-8")

    spec = WorkloadSpec.from_json_file(spec_file)
    assert spec.name == "paysecure-api"
    assert spec.port == 8080
    assert spec.resources.cpu == 0.25
    assert spec.scale.min_replicas_standby == 0
    assert spec.scale.min_replicas_active == 1
    assert spec.health_probe.path == "/health"
    assert spec.env["CURRENT_CLOUD"] == "AWS"


def test_workload_cataloger_discovery(tmp_path: Path):
    svc_dir = tmp_path / "services" / "test-svc"
    svc_dir.mkdir(parents=True)
    manifest = {
        "name": "test-svc",
        "version": "2.1.0",
        "image": "docker.io/repo/test-svc:2.1.0",
        "port": 9000,
    }
    (svc_dir / "workload_spec.json").write_text(json.dumps(manifest), encoding="utf-8")

    cataloger = WorkloadCataloger(services_dir=tmp_path / "services")
    specs = cataloger.discover_specs()
    assert len(specs) == 1
    assert specs[0].name == "test-svc"
    assert specs[0].port == 9000

    catalog_data = cataloger.export_catalog_json()
    assert len(catalog_data) == 1
    assert catalog_data[0]["name"] == "test-svc"


def test_cross_cloud_translator():
    spec = WorkloadSpec(
        name="paysecure-api",
        image="ghcr.io/yashk3086/paysecure-api:1.0.0",
        port=8080,
        env={
            "CURRENT_CLOUD": "AWS",
            "AWS_STAGE_BUCKET": "sf-dr-primary-stage-bucket",
            "SNOWFLAKE_DATABASE": "SF_DR_DEMO_DB",
        },
    )
    translator = CrossCloudTranslator(
        azure_storage_account="teststorage",
        azure_stage_container="teststage",
        azure_location="eastus2",
    )
    manifest = translator.translate_for_azure(spec)

    assert manifest["name"] == "paysecure-api-dr"
    assert manifest["location"] == "eastus2"
    container = manifest["properties"]["template"]["containers"][0]
    assert container["name"] == "paysecure-api"
    assert container["image"] == "ghcr.io/yashk3086/paysecure-api:1.0.0"

    env_map = {item["name"]: item["value"] for item in container["env"]}
    assert env_map["CURRENT_CLOUD"] == "Azure"
    assert env_map["STAGE_STORAGE_TYPE"] == "AZURE_BLOB"
    assert env_map["STAGE_STORAGE_ENDPOINT"] == "https://teststorage.blob.core.windows.net/teststage"
    assert manifest["properties"]["template"]["scale"]["minReplicas"] == 0

