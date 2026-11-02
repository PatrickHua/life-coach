"""Print scores per agent version and write data/scores.csv: python -m tools.score"""
from harness.config import Settings
from harness.scorer import write_csv
from harness.store import Store

if __name__ == "__main__":
    rows = write_csv(Store(Settings.from_env().data_dir))
    if not rows:
        print("No goals yet.")
    for r in rows:
        print(f"{r['agent']}: {r['achieved']}/{r['closed']} achieved of {r['contracts']} goals, "
              f"median {r['median_days'] or '-'} days, {r['bad_flags']} /bad, {r['pauses']} pauses")
