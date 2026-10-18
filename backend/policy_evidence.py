"""Versioned, locally archived S2 evidence; no automatic subject association."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.policy_capital_contract import EvidencePackage

DATA_DIR = Path(__file__).with_name("policy_evidence_data")


class EvidenceRepository:
    def __init__(self, root: Path = DATA_DIR) -> None:
        self.root = root

    def get(self, package_id: str) -> EvidencePackage:
        # Whitelist lookup also prevents arbitrary filesystem access.
        packages = json.loads((self.root / "packages.json").read_text())
        if package_id not in packages:
            raise KeyError(package_id)
        package = EvidencePackage.model_validate(packages[package_id])
        manifest = json.loads((self.root / "manifest.json").read_text())
        for item in package.evidence:
            record = manifest[item.id]
            path = self.root / record["snapshot_file"]
            if path.parent != self.root or not path.is_file():
                raise OSError("Evidence archive unavailable")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != item.snapshot_sha256 or digest != record["snapshot_sha256"]:
                raise OSError("Evidence archive checksum mismatch")
            if (
                str(item.url) != record["url"]
                or item.retrieved_at.isoformat() != record["retrieved_at"]
            ):
                raise OSError("Evidence provenance mismatch")
        return package
