#!/usr/bin/env python3
"""Validates Kubernetes YAML manifest syntax and structure."""
import glob
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

def validate() -> None:
    manifest_files = sorted(glob.glob("k8s/*.yaml"))
    if not manifest_files:
        print("[ERROR] No manifest files found in k8s/")
        sys.exit(1)

    print(f"[INFO] Validating {len(manifest_files)} Kubernetes manifests...")
    total_docs = 0
    for file_path in manifest_files:
        with open(file_path, "r", encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
            for doc in docs:
                if not doc:
                    continue
                total_docs += 1
                kind = doc.get("kind", "<unknown>")
                name = doc.get("metadata", {}).get("name", "<unnamed>")
                assert "apiVersion" in doc, f"Missing apiVersion in {file_path}"
                assert "kind" in doc, f"Missing kind in {file_path}"
                assert "metadata" in doc, f"Missing metadata in {file_path}"
                print(f"  [OK] {file_path} -> {kind} [{name}]")

    print(f"\n[SUCCESS] All {total_docs} Kubernetes resources in k8s/ are structurally valid!")

if __name__ == "__main__":
    validate()
