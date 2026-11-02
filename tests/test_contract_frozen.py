import json
import os
from datetime import datetime, timezone

import pytest

from harness import contract
from harness.store import Store

NOW = datetime(2026, 11, 4, 10, tzinfo=timezone.utc)


def test_freeze_and_load(tmp_path):
    store = Store(tmp_path)
    c = contract.freeze(store, "Run 3x a week", "12 runs", "2026-11-18", "self_report", NOW)
    assert contract.load(store, c["id"]) == c
    path = store.contracts_dir / f"{c['id']}.json"
    assert not os.access(path, os.W_OK) or os.geteuid() == 0  # read-only (root ignores modes)
    assert oct(path.stat().st_mode)[-3:] == "444"


def test_cannot_overwrite(tmp_path):
    store = Store(tmp_path)
    contract.freeze(store, "Run", "12 runs", "2026-11-18", "self_report", NOW)
    with pytest.raises(FileExistsError):
        contract.freeze(store, "Run", "12 runs", "2026-11-18", "self_report", NOW)


def test_tampering_is_detected(tmp_path):
    store = Store(tmp_path)
    c = contract.freeze(store, "Run 3x a week", "12 runs", "2026-11-18", "self_report", NOW)
    path = store.contracts_dir / f"{c['id']}.json"
    path.chmod(0o644)
    edited = dict(c, goal="Run once")
    path.write_text(json.dumps(edited))
    with pytest.raises(contract.TamperedContract):
        contract.load(store, c["id"])


def test_unknown_evidence_type(tmp_path):
    with pytest.raises(ValueError):
        contract.freeze(Store(tmp_path), "Run", "x", "2026-11-18", "trust_me", NOW)
