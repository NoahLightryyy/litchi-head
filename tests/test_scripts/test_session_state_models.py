"""Contract tests for Git-verified session recovery snapshots."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from scripts.session_state_models import (
    HandoffPayload,
    RepositoryState,
    SessionSnapshotV2,
    normalize_identity_path,
    path_key,
)
from tests.test_scripts.session_state_helpers import (
    valid_repository_payload,
    valid_snapshot_payload,
)


@pytest.mark.skipif(os.name != "nt", reason="Windows path identity contract")
def test_normalize_identity_path_is_case_insensitive_on_windows(tmp_path: Path) -> None:
    alternate_case_path = Path(str(tmp_path).swapcase())

    assert normalize_identity_path(tmp_path) == normalize_identity_path(alternate_case_path)


def test_path_key_is_stable_private_and_fixed_width(tmp_path: Path) -> None:
    first_key = path_key(tmp_path)

    assert first_key == path_key(tmp_path)
    assert len(first_key) == 24
    assert all(character in "0123456789abcdef" for character in first_key)
    assert tmp_path.name not in first_key


def test_snapshot_rejects_timezone_naive_saved_at(tmp_path: Path) -> None:
    payload = valid_snapshot_payload(tmp_path)
    payload["saved_at"] = datetime(2026, 8, 11, 12, 0)

    with pytest.raises(ValidationError, match="saved_at must include a timezone"):
        SessionSnapshotV2.model_validate(payload)


def test_models_are_frozen_and_reject_unknown_fields(tmp_path: Path) -> None:
    snapshot = SessionSnapshotV2.model_validate(valid_snapshot_payload(tmp_path))

    with pytest.raises(ValidationError):
        snapshot.topic = "A different topic"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        HandoffPayload(exact_next_step="Continue", unexpected="value")  # type: ignore[call-arg]


def test_snapshot_rejects_path_traversal_snapshot_id(tmp_path: Path) -> None:
    payload = valid_snapshot_payload(tmp_path)
    payload["snapshot_id"] = "../escape"

    with pytest.raises(ValidationError):
        SessionSnapshotV2.model_validate(payload)


def test_repository_state_rejects_dirty_flag_path_disagreement(tmp_path: Path) -> None:
    payload = valid_repository_payload(tmp_path)
    payload["git_dirty"] = True

    with pytest.raises(ValidationError, match="git_dirty must match dirty_paths"):
        RepositoryState.model_validate(payload)


def test_snapshot_rejects_dirty_flag_path_disagreement(tmp_path: Path) -> None:
    payload = valid_snapshot_payload(tmp_path)
    payload["git_dirty"] = True

    with pytest.raises(ValidationError, match="git_dirty must match dirty_paths"):
        SessionSnapshotV2.model_validate(payload)
