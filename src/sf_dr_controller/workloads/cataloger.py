"""Workload Specification & Registry Data Models.

Defines the structure for containerized application blueprints replicating
across AWS (Active) and Azure (Standby Pilot Light).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class WorkloadResourceConfig(BaseModel):
    cpu: float = Field(default=0.25, description="CPU cores allocated")
    memory: str = Field(default="0.5Gi", description="Memory allocation (e.g. 0.5Gi, 1Gi)")


class WorkloadScaleConfig(BaseModel):
    min_replicas_standby: int = Field(default=0, description="Replica count during standby ($0 idle compute)")
    min_replicas_active: int = Field(default=1, description="Replica count during active state")
    max_replicas: int = Field(default=5, description="Maximum scale-out limit")


class WorkloadHealthProbe(BaseModel):
    path: str = Field(default="/health")
    port: int = Field(default=8080)
    initial_delay_seconds: int = Field(default=3)
    period_seconds: int = Field(default=5)


class WorkloadSpec(BaseModel):
    name: str = Field(..., description="Service identifier")
    version: str = Field(default="1.0.0")
    description: str = Field(default="")
    image: str = Field(..., description="OCI Container Image URI")
    port: int = Field(default=8080)
    resources: WorkloadResourceConfig = Field(default_factory=WorkloadResourceConfig)
    scale: WorkloadScaleConfig = Field(default_factory=WorkloadScaleConfig)
    health_probe: WorkloadHealthProbe = Field(default_factory=WorkloadHealthProbe)
    env: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: str | Path) -> WorkloadSpec:
        """Loads and parses a workload specification from a JSON manifest."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)

    def to_json(self, indent: int = 2) -> str:
        """Serializes workload specification to formatted JSON."""
        return self.model_dump_json(indent=indent)


class WorkloadCataloger:
    """Discovers local service blueprints and produces standardized workload catalogs."""

    def __init__(self, services_dir: str | Path | None = None) -> None:
        if services_dir is None:
            # Default to repo root /services
            self.services_dir = Path(__file__).resolve().parent.parent.parent.parent / "services"
        else:
            self.services_dir = Path(services_dir)

    def discover_specs(self) -> list[WorkloadSpec]:
        """Scans the services directory for workload_spec.json definitions."""
        specs: list[WorkloadSpec] = []
        if not self.services_dir.exists():
            return specs

        for spec_path in self.services_dir.glob("**/workload_spec.json"):
            try:
                spec = WorkloadSpec.from_json_file(spec_path)
                specs.append(spec)
            except (OSError, ValueError, KeyError):
                continue
        return specs

    def export_catalog_json(self) -> list[dict[str, Any]]:
        """Exports all discovered workload specs as a list of dictionaries."""
        return [spec.model_dump() for spec in self.discover_specs()]

