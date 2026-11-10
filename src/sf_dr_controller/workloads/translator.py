"""Cross-Cloud Workload Specification Translator.

Dynamically translates container runtime blueprints across ANY cloud provider
(AWS <-> Azure <-> GCP), remapping compute manifests, object storage endpoints,
and pilot-light scaling policies ($0 idle compute).
"""

from __future__ import annotations

import copy
from typing import Any

from .cataloger import WorkloadSpec


class CrossCloudTranslator:
    """Universal multi-cloud translator supporting AWS, Azure, and GCP targets."""

    CLOUD_DEFAULTS: dict[str, dict[str, str]] = {
        "AZURE": {
            "provider": "Azure",
            "compute_kind": "Microsoft.App/containerApps",
            "storage_type": "AZURE_BLOB",
            "default_region": "eastus2",
        },
        "AWS": {
            "provider": "AWS",
            "compute_kind": "AWS::ECS::FargateService",
            "storage_type": "AWS_S3",
            "default_region": "us-east-1",
        },
        "GCP": {
            "provider": "GCP",
            "compute_kind": "run.googleapis.com/Service",
            "storage_type": "GCP_GCS",
            "default_region": "us-central1",
        },
    }

    def __init__(
        self,
        azure_storage_account: str = "sfdrsecstagedrdemo",
        azure_stage_container: str = "sf-dr-secondary-stage",
        azure_location: str = "eastus2",
    ) -> None:
        self.azure_storage_account = azure_storage_account
        self.azure_stage_container = azure_stage_container
        self.azure_location = azure_location

    def build_storage_endpoint(self, cloud_key: str, region: str) -> str:
        """Dynamically builds the native object storage URI for the target cloud."""
        if cloud_key == "AZURE":
            return f"https://{self.azure_storage_account}.blob.core.windows.net/{self.azure_stage_container}"
        if cloud_key == "GCP":
            return f"gs://{self.azure_stage_container}-gcs-{region}"
        return f"s3://{self.azure_stage_container}-s3-{region}"

    def build_ingress_url(self, app_name: str, cloud_key: str, region: str) -> str:
        """Dynamically builds the serverless container ingress endpoint for the target cloud."""
        if cloud_key == "AZURE":
            return f"https://{app_name}.gentlewave-{region}.azurecontainerapps.io"
        if cloud_key == "GCP":
            return f"https://{app_name}-{region}.a.run.app"
        return f"https://{app_name}.{region}.awsapprunner.com"

    def translate(
        self,
        spec: WorkloadSpec,
        target_cloud: str = "Azure",
        target_region: str | None = None,
    ) -> dict[str, Any]:
        """Dynamically translates a workload blueprint into the target cloud's native manifest."""
        cloud_key = target_cloud.strip().upper()
        if cloud_key not in self.CLOUD_DEFAULTS:
            cloud_key = "AZURE"

        meta = self.CLOUD_DEFAULTS[cloud_key]
        resolved_region = target_region or (self.azure_location if cloud_key == "AZURE" else meta["default_region"])

        target_env = copy.deepcopy(spec.env)
        target_env["CURRENT_CLOUD"] = meta["provider"]
        target_env["CLOUD_REGION"] = resolved_region
        target_env["STAGE_STORAGE_TYPE"] = meta["storage_type"]
        target_env["STAGE_STORAGE_ENDPOINT"] = self.build_storage_endpoint(cloud_key, resolved_region)

        app_name = f"{spec.name}-dr"
        return {
            "name": app_name,
            "target_cloud": meta["provider"],
            "compute_kind": meta["compute_kind"],
            "location": resolved_region,
            "ingress_url": self.build_ingress_url(app_name, cloud_key, resolved_region),
            "properties": {
                "configuration": {
                    "ingress": {
                        "external": True,
                        "targetPort": spec.port,
                        "transport": "auto",
                        "allowInsecure": False,
                    }
                },
                "template": {
                    "containers": [
                        {
                            "name": spec.name,
                            "image": spec.image,
                            "resources": {
                                "cpu": spec.resources.cpu,
                                "memory": spec.resources.memory,
                            },
                            "env": [{"name": k, "value": str(v)} for k, v in target_env.items()],
                            "probes": [
                                {
                                    "type": "Liveness",
                                    "httpGet": {
                                        "path": spec.health_probe.path,
                                        "port": spec.health_probe.port,
                                    },
                                    "initialDelaySeconds": spec.health_probe.initial_delay_seconds,
                                    "periodSeconds": spec.health_probe.period_seconds,
                                }
                            ],
                        }
                    ],
                    "scale": {
                        "minReplicas": spec.scale.min_replicas_standby,  # 0 on standby ($0 idle)
                        "maxReplicas": spec.scale.max_replicas,
                    },
                },
            },
            "tags": {
                "ManagedBy": "sf-dr-controller",
                "DR_Role": "Secondary_Hydrated_Workload",
                "TargetCloud": meta["provider"],
                "Service": spec.name,
                "Version": spec.version,
            },
        }

    def translate_for_azure(self, spec: WorkloadSpec) -> dict[str, Any]:
        """Backward-compatible helper delegating to universal translate()."""
        target_cloud = "Azure"
        return self.translate(spec, target_cloud=target_cloud, target_region=self.azure_location)
