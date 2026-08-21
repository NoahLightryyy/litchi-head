"""Canonical serialization and content identities for E0 artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence

from pydantic import BaseModel
from pydantic_core import to_jsonable_python


def canonical_json(
    value: BaseModel | Mapping[str, object] | Sequence[object],
) -> str:
    """Serialize an E0 value into deterministic, strict JSON."""

    jsonable = (
        value.model_dump(mode="json")
        if isinstance(value, BaseModel)
        else to_jsonable_python(value)
    )
    try:
        return json.dumps(
            jsonable,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except ValueError as exc:
        raise ValueError("canonical JSON rejects non-finite numbers") from exc


def sha256_identity(prefix: str, value: object) -> str:
    """Return a namespaced SHA-256 identity for a JSON-compatible value."""

    if not prefix.strip():
        raise ValueError("identity prefix must not be empty")
    if isinstance(value, BaseModel | Mapping | Sequence) and not isinstance(
        value, str | bytes | bytearray
    ):
        payload = canonical_json(value)
    else:
        payload = canonical_json({"value": value})
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"
