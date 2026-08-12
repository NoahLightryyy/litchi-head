from __future__ import annotations

import hashlib
import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SnapshotStatus(StrEnum):
    MATCH = "MATCH"
    REPO_AHEAD = "REPO_AHEAD"
    HEAD_DIVERGED = "HEAD_DIVERGED"
    BRANCH_MISMATCH = "BRANCH_MISMATCH"
    DIRTY_MISMATCH = "DIRTY_MISMATCH"
    EVIDENCE_CHANGED = "EVIDENCE_CHANGED"
    PROJECT_MISMATCH = "PROJECT_MISMATCH"
    LEGACY_UNVERIFIABLE = "LEGACY_UNVERIFIABLE"
    MALFORMED = "MALFORMED"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class EvidenceRef(FrozenModel):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class HandoffPayload(FrozenModel):
    current_state: tuple[str, ...] = ()
    failed_approaches: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    exact_next_step: str = Field(min_length=1)


class RepositoryState(FrozenModel):
    project_root: str
    worktree_path: str
    branch: str
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dirty: bool
    dirty_paths: tuple[str, ...]
    handover: EvidenceRef | None
    latest_work_log: EvidenceRef | None
    sdd_progress: EvidenceRef | None

    @model_validator(mode="after")
    def dirty_flag_matches_paths(self) -> RepositoryState:
        if self.git_dirty != bool(self.dirty_paths):
            raise ValueError("git_dirty must match dirty_paths")
        return self


class SessionSnapshotV2(FrozenModel):
    schema_version: int = Field(default=2, ge=2, le=2)
    snapshot_id: str = Field(pattern=r"^[A-Za-z0-9+_-]{1,96}$")
    saved_at: datetime
    project_root: str
    worktree_path: str
    branch: str
    git_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    git_dirty: bool
    dirty_paths: tuple[str, ...]
    handover: EvidenceRef | None
    latest_work_log: EvidenceRef | None
    sdd_progress: EvidenceRef | None
    topic: str = Field(min_length=1)
    handoff: HandoffPayload

    @field_validator("saved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("saved_at must include a timezone")
        return value

    @model_validator(mode="after")
    def dirty_flag_matches_paths(self) -> SessionSnapshotV2:
        if self.git_dirty != bool(self.dirty_paths):
            raise ValueError("git_dirty must match dirty_paths")
        return self


class ValidationResult(FrozenModel):
    status: SnapshotStatus
    snapshot_path: str | None
    diagnostics: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    requires_user_confirmation: bool = False
    handoff: HandoffPayload | None = None


def normalize_identity_path(path: Path) -> str:
    resolved = str(path.resolve(strict=True))
    normalized = os.path.normcase(os.path.normpath(resolved))
    return normalized.casefold() if os.name == "nt" else normalized


def path_key(path: Path) -> str:
    identity = normalize_identity_path(path).encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:24]
