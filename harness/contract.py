"""Goal contracts: written by the user in a fixed form, then frozen. No edits after freezing."""
import hashlib
import json
import os
from datetime import datetime

from .store import Store

EVIDENCE_TYPES = ("self_report", "link")
FIELDS = ("goal", "done_means", "deadline", "evidence", "created")


class TamperedContract(Exception):
    pass


def _digest(body: dict) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def freeze(store: Store, goal: str, done_means: str, deadline: str, evidence: str, now: datetime) -> dict:
    if evidence not in EVIDENCE_TYPES:
        raise ValueError(f"unknown evidence type {evidence!r}")
    body = {"goal": goal, "done_means": done_means, "deadline": deadline,
            "evidence": evidence, "created": now.isoformat()}
    digest = _digest(body)
    contract = {"id": "c_" + digest[:12], **body, "hash": digest}
    path = store.contracts_dir / f"{contract['id']}.json"
    with open(path, "x", encoding="utf-8") as f:  # "x": never overwrite
        json.dump(contract, f, ensure_ascii=False, indent=1)
    os.chmod(path, 0o444)
    return contract


def load(store: Store, contract_id: str) -> dict:
    path = store.contracts_dir / f"{contract_id}.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    body = {k: contract[k] for k in FIELDS}
    if _digest(body) != contract["hash"] or contract["id"] != "c_" + contract["hash"][:12]:
        raise TamperedContract(contract_id)
    return contract


def load_all(store: Store) -> list[dict]:
    contracts = [load(store, p.stem) for p in store.contracts_dir.glob("c_*.json")]
    return sorted(contracts, key=lambda c: c["created"])
