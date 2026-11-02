"""Scores per agent version, computed only from harness-owned logs."""
import csv
from statistics import median

from .store import Store


def scores(store: Store) -> list[dict]:
    outcomes = store.read_jsonl(store.outcomes_path)
    events = store.read_jsonl(store.events_path)
    frozen = {e["contract"]["id"]: e["agent"] for e in events if e["kind"] == "contract_frozen"}
    rows = {}
    for agent in sorted(set(frozen.values())):
        rows[agent] = {"agent": agent, "contracts": 0, "closed": 0, "achieved": 0,
                       "success_rate": "", "median_days": "", "bad_flags": 0, "pauses": 0}
    for agent in frozen.values():
        rows[agent]["contracts"] += 1
    days = {a: [] for a in rows}
    for o in outcomes:
        r = rows.setdefault(o["agent"], {"agent": o["agent"], "contracts": 0, "closed": 0, "achieved": 0,
                                         "success_rate": "", "median_days": "", "bad_flags": 0, "pauses": 0})
        r["closed"] += 1
        if o["achieved"]:
            r["achieved"] += 1
            days.setdefault(o["agent"], []).append(o["days"])
    current = None
    for e in events:  # guardrails: attribute to whichever agent was running at the time
        if e["kind"] == "agent_started":
            current = e["agent"]
        elif current in rows and e["kind"] == "user_feedback":
            rows[current]["bad_flags"] += 1
        elif current in rows and e["kind"] == "command" and e["command"] == "pause":
            rows[current]["pauses"] += 1
    for agent, r in rows.items():
        if r["closed"]:
            r["success_rate"] = round(r["achieved"] / r["closed"], 3)
        if days.get(agent):
            r["median_days"] = median(days[agent])
    return list(rows.values())


def write_csv(store: Store) -> list[dict]:
    rows = scores(store)
    with open(store.dir / "scores.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["agent", "contracts", "closed", "achieved", "success_rate",
                                               "median_days", "bad_flags", "pauses"])
        writer.writeheader()
        writer.writerows(rows)
    return rows
