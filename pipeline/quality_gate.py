"""Post-collection data-quality gate: protect the DATA, not just the code.

    python -m pipeline.quality_gate

Unit tests catch broken code; nothing else catches a source that returns
HTTP 200 with a changed response shape and silently yields zeros forever —
the failure mode that quietly rots a collection dataset. This gate inspects
the snapshot that was ACTUALLY stored today and asserts, per signal family:

  1. liveness  — enough tickers carry a non-degenerate value today;
  2. no-collapse — today's liveness didn't drop >60% vs the trailing average
     (a live endpoint whose parser broke shows up exactly here).

Exit code 1 only for catastrophic conditions (no snapshot today, or the
price backbone dead) so CI goes red when collection is truly broken;
family-level problems print as WARN lines and are recorded in
data/quality_gate.json (committed daily → the health history is in git).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

from . import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "quality_gate.json")

# family -> (feature key, predicate on value, min alive fraction)
FAMILIES: dict[str, tuple[str, str, float]] = {
    # backbone: catastrophic if dead
    "prices": ("ret_21d", "notnull", 0.80),
    "factors": ("ROC_20", "notnull", 0.80),
    # attention/positioning: warn if dead or collapsed
    "news": ("news_count", "positive", 0.20),
    "stocktwits": ("st_msg_count", "positive", 0.20),
    "finra_short": ("short_vol_ratio", "notnull", 0.50),
    "wikipedia": ("wiki_views_7d", "positive", 0.10),
    "sec_filings": ("sec_form4_recent", "notnull", 0.10),
    "reddit": ("reddit_mentions", "positive", 0.01),
}
CATASTROPHIC = {"prices", "factors"}

# Families known to be unavailable from shared CI runners. They are still
# collected (so they light up the moment access exists) but are reported as
# EXPECTED-DOWN rather than DEAD: a monitor that cries wolf every single day
# trains you to ignore it, which is how a REAL outage gets missed.
#   reddit      — anonymous JSON access refused by design (needs API creds)
#   sec_filings — SEC throttles shared runner IPs
#                 ("Request Rate Threshold Exceeded")
EXPECTED_UNAVAILABLE = {
    f.strip() for f in os.environ.get(
        "EXPECTED_UNAVAILABLE", "reddit,sec_filings").split(",") if f.strip()
}
COLLAPSE_RATIO = 0.4  # today's alive fraction below 40% of trailing avg -> collapse
TRAILING_DATES = 5


def _alive_fraction(rows: list[dict], key: str, mode: str) -> float:
    if not rows:
        return 0.0
    ok = 0
    for r in rows:
        v = (r.get("features") or {}).get(key)
        is_num = isinstance(v, (int, float)) and v == v
        if mode == "notnull":
            ok += 1 if is_num else 0
        else:  # positive
            ok += 1 if (is_num and v > 0) else 0
    return ok / len(rows)


def run_gate() -> tuple[dict, int]:
    records = store.load_features()
    dates = store.distinct_dates(records)
    if not dates:
        return ({"status": "FAIL", "reason": "no snapshots in store"}, 1)
    today = dates[-1]
    todays = [r for r in records if r.get("date") == today]
    trailing_dates = dates[:-1][-TRAILING_DATES:]

    report: dict = {"date": today, "n_tickers": len(todays),
                    "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                    "families": {}}
    exit_code = 0
    if len(todays) < 30:
        report["status"] = "FAIL"
        report["reason"] = f"only {len(todays)} tickers in today's snapshot"
        return report, 1

    for fam, (key, mode, floor) in FAMILIES.items():
        frac = _alive_fraction(todays, key, mode)
        trail = [
            _alive_fraction([r for r in records if r.get("date") == d], key, mode)
            for d in trailing_dates
        ]
        trail_avg = (sum(trail) / len(trail)) if trail else None
        alive = frac >= floor
        collapsed = (trail_avg is not None and trail_avg >= floor
                     and frac < trail_avg * COLLAPSE_RATIO)
        status = "OK" if (alive and not collapsed) else (
            "COLLAPSED" if collapsed else "DEAD")
        if status != "OK" and fam in EXPECTED_UNAVAILABLE:
            status = "EXPECTED-DOWN"
        elif status == "OK" and fam in EXPECTED_UNAVAILABLE:
            # Access was restored — worth shouting about, it means new data.
            print(f"[quality-gate] {fam} is ALIVE again ({frac:.0%}) — "
                  f"consider removing it from EXPECTED_UNAVAILABLE")
        report["families"][fam] = {
            "alive_fraction": round(frac, 3),
            "floor": floor,
            "trailing_avg": round(trail_avg, 3) if trail_avg is not None else None,
            "status": status,
        }
        if status not in ("OK", "EXPECTED-DOWN"):
            print(f"[quality-gate] WARN {fam}: {status} "
                  f"(alive {frac:.0%}, floor {floor:.0%}, "
                  f"trailing {trail_avg if trail_avg is None else round(trail_avg, 2)})")
            if fam in CATASTROPHIC:
                exit_code = 1

    report["status"] = "FAIL" if exit_code else "OK"
    return report, exit_code


def main():
    report, code = run_gate()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        json.dump(report, fh, indent=2)
    ok = sum(1 for f in report.get("families", {}).values() if f["status"] == "OK")
    total = len(report.get("families", {}))
    print(f"[quality-gate] {report['status']}: {ok}/{total} families OK "
          f"({report.get('n_tickers', 0)} tickers on {report.get('date')})")
    sys.exit(code)


if __name__ == "__main__":
    main()
