"""One-command health report for the collection phase.

    python -m pipeline.status

Answers the daily question — "did yesterday's scrape actually work?" — from
committed data alone, no API access required: how many dates collected, how
the archive is growing, which signal families are alive, and what the current
top names are. Designed for the daily check during the collection/testing
phase, where the failure that matters is silent: a run that "succeeds" while
a source quietly returns nothing.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from . import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_json(path):
    try:
        with open(os.path.join(ROOT, path)) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _business_days_between(a: str, b: str) -> int:
    d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
    n = 0
    while d0 < d1:
        d0 += dt.timedelta(days=1)
        if d0.weekday() < 5:
            n += 1
    return n


def main():
    print("=" * 62)
    print("  PIT-ARCHIVE — COLLECTION STATUS")
    print("=" * 62)

    man = _read_json("data/history/manifest.json")
    if not man:
        print("\n  No manifest — nothing collected yet.")
        return
    f, p = man["features"], man["prices"]

    print(f"\nARCHIVE (as of {man['updated_at'][:16]}Z)")
    print(f"  feature snapshots : {f['rows']:>8,} rows | {f['dates']:>3} dates "
          f"| {f['distinct_tickers']:>6,} tickers")
    print(f"  price archive     : {p['rows']:>8,} rows | {p['dates']:>3} dates "
          f"| {p['distinct_tickers']:>6,} tickers")
    print(f"  feature window    : {f['first_date']} -> {f['last_date']}")

    # Freshness: on a weekday the last snapshot should be today or yesterday.
    today = dt.date.today().isoformat()
    if f["last_date"] == today:
        fresh = "current (collected today)"
    else:
        gap = _business_days_between(f["last_date"], today)
        fresh = (f"{gap} business day(s) behind"
                 + ("  <-- CHECK THE WORKFLOW" if gap >= 2 else ""))
    print(f"  freshness         : {fresh}")

    # Progress toward the milestones that unlock evaluation and predictions.
    need_pred = max(0, 8 - f["dates"])
    print(f"\nPROGRESS")
    print(f"  dates collected   : {f['dates']}")
    print(f"  learned predictions unlock in ~{need_pred} more collection day(s)"
          if need_pred else "  learned predictions: ACTIVE")
    print("  first meaningful IC evaluation needs ~63d of labels "
          "(snapshots mature into examples)")

    gate = _read_json("data/quality_gate.json")
    if gate and gate.get("families"):
        print(f"\nSIGNAL HEALTH ({gate.get('date')}, {gate.get('n_tickers')} tickers)"
              f" — gate: {gate.get('status')}")
        for fam, r in gate["families"].items():
            mark = {"OK": "  ok  ", "DEAD": " DEAD ", "COLLAPSED": "COLLAPS",
                    "EXPECTED-DOWN": " n/a  "}.get(r["status"], r["status"])
            print(f"  [{mark}] {fam:<14} alive={r['alive_fraction']:.0%} "
                  f"(floor {r['floor']:.0%})")

    pre = _read_json("data/preflight.json")
    if pre and pre.get("sources"):
        down = [k for k, v in pre["sources"].items() if not v.get("ok")]
        print(f"\nENDPOINTS (last probe {pre['checked_at'][:16]}Z): "
              f"{len(pre['sources']) - len(down)}/{len(pre['sources'])} up"
              + (f" | down: {', '.join(down)}" if down else ""))

    q = _read_json("data/dataset/quality_63d.json")
    if q:
        print(f"\nLABELED DATASET (63d): {q.get('labeled_rows', 0):,} examples, "
              f"{q.get('distinct_dates', 0)} dates")

    # Current top names from the committed rankings.
    rank_path = os.path.join(ROOT, "data/daily_output.md")
    if os.path.exists(rank_path):
        rows = [ln for ln in open(rank_path).read().splitlines()
                if ln.startswith("| ") and not ln.startswith("| #")
                and "---" not in ln]
        if rows:
            print("\nTOP 5 (heuristic screen)")
            for ln in rows[:5]:
                cells = [c.strip() for c in ln.strip("|").split("|")]
                if len(cells) >= 3:
                    print(f"  {cells[0]:>2}. {cells[1]:<8} score {cells[2]}")
    print()


if __name__ == "__main__":
    main()
