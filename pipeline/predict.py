"""Daily learned predictions: data/model_output.md.

    python -m pipeline.predict

Replaces the hand-tuned composite score with a calibrated ensemble once the
archive holds enough labeled history. Two targets are produced side by side
because they answer different questions:

  P(top quintile)  — peer-relative ranking. Dense labels, so it becomes
                     trustworthy first and is the better sizing input.
  P(big move)      — P(forward return >= +30%). The literal "next big riser"
                     question. A rare event, so it needs far more history
                     before its probabilities mean anything.

Both are reported with the out-of-sample evidence that says whether to
believe them (AUC, IC, Brier before/after calibration). Until the archive is
big enough, this writes an honest "collecting" status rather than numbers.
"""
from __future__ import annotations

import datetime as dt
import os

from . import dataset, ensemble, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(ROOT, "data/model_output.md")

MIN_DATES = 8
MIN_EXAMPLES = 200
HORIZON = 63
TOP_N = 20
BIG_MOVE_THRESHOLD = 0.30

DISCLAIMER = (
    "Model output, not advice. A probability here is only worth what the "
    "out-of-sample table below says it is: check Brier and the calibration "
    "rows before acting on any number. Markets are largely efficient — expect "
    "a small edge at best, and size positions accordingly."
)


def _not_ready(n_dates: int, n_examples: int) -> str:
    need_d = max(0, MIN_DATES - n_dates)
    return "\n".join([
        "# Model Predictions",
        "",
        f"_Status: **collecting** — {n_dates} snapshot dates, {n_examples} "
        f"labeled examples (need ≥{MIN_DATES} dates and ≥{MIN_EXAMPLES} "
        f"examples; ~{need_d} more collection days, then the {HORIZON}d label "
        f"lag before those days mature into examples)._",
        "",
        "Today's heuristic screen is in data/daily_output.md. Learned predictions "
        "appear here automatically — no action needed — once enough labeled "
        "history exists to train and validate on.",
        "",
    ])


def _evidence_block(res: dict, title: str) -> list[str]:
    lines = [f"### {title}", ""]
    if "error" in res:
        lines += [f"_Not available yet: {res['error']}._", ""]
        return lines
    lines += [
        f"- out-of-sample AUC: **{res.get('oos_auc')}** (0.5 = coin flip)",
        f"- out-of-sample IC: **{res.get('oos_ic')}**",
        f"- Brier: {res.get('brier_uncalibrated')} raw → "
        f"**{res.get('brier_calibrated')}** calibrated (lower is better)",
        f"- base rate: {res.get('positive_rate')} · OOS rows: {res.get('n_oos')}",
        "",
    ]
    cal = res.get("calibration") or []
    if cal:
        lines += ["| bucket | n | predicted | actual |",
                  "|-------:|--:|----------:|-------:|"]
        for r in cal:
            lines.append(f"| {r['bucket']} | {r['n']} | {r['mean_predicted']} "
                         f"| {r['actual_rate']} |")
        lines.append("")
        lines.append("_Predicted and actual should track. Predicted "
                     "consistently above actual means the model is "
                     "overconfident — halve your position sizes._")
        lines.append("")
    return lines


def run() -> str:
    features_all = store.load_features()
    dates = store.distinct_dates(features_all)
    examples = dataset.compile_labeled(horizon=HORIZON, write=False)

    if len(dates) < MIN_DATES or len(examples) < MIN_EXAMPLES:
        return _not_ready(len(dates), len(examples))

    # Exclude reconstructed rows: their universe and signal coverage differ
    # from live captures, so training on them would blur what the model is
    # actually learning from.
    live = [e for e in examples
            if not (e.get("features") or {}).get("__backfilled__")]
    feature_keys = dataset.FEATURE_KEYS

    # Peer-relative target uses rel_ret; the big-move target needs the raw
    # return, since a 30% gain is 30% regardless of what peers did.
    rel = [dict(e, fwd_ret=e.get("rel_ret", e["fwd_ret"])) for e in live]
    res_rank = ensemble.walk_forward_ensemble(rel, feature_keys,
                                              target="top_quintile")
    res_big = ensemble.walk_forward_ensemble(live, feature_keys,
                                             target="big_move",
                                             big_move_threshold=BIG_MOVE_THRESHOLD)

    latest = dates[-1]
    todays = [r for r in features_all if r.get("date") == latest]
    rows = [{"features": r.get("features", {})} for r in todays]

    pred_rank, info = ensemble.fit_full(rel, feature_keys, target="top_quintile")
    p_rank = pred_rank(rows)
    try:
        pred_big, _ = ensemble.fit_full(live, feature_keys, target="big_move",
                                        big_move_threshold=BIG_MOVE_THRESHOLD)
        p_big = pred_big(rows)
    except Exception:  # noqa: BLE001 - rare-event target may be untrainable early
        p_big = [None] * len(rows)

    ranked = sorted(zip(todays, p_rank, p_big), key=lambda t: -t[1])[:TOP_N]

    lines = [
        "# Model Predictions",
        "",
        f"_Snapshot {latest} · trained on {info['n_train']} labeled examples "
        f"across {len({e['date'] for e in rel})} dates · {HORIZON}d horizon · "
        f"generated {dt.datetime.now(dt.timezone.utc).isoformat()}_",
        "",
        f"> {DISCLAIMER}",
        "",
        "| # | Ticker | P(top quintile) | P(≥+30%) | Heuristic |",
        "|--:|:------:|----------------:|---------:|----------:|",
    ]
    for i, (rec, pr, pb) in enumerate(ranked, 1):
        pb_s = f"{pb:.3f}" if isinstance(pb, float) else "—"
        lines.append(f"| {i} | {rec['ticker']} | {pr:.3f} | {pb_s} | "
                     f"{rec.get('score', '—')} |")
    lines += ["", "## Out-of-sample evidence", ""]
    lines += _evidence_block(res_rank, "Target: top-quintile relative return")
    lines += _evidence_block(res_big, f"Target: absolute move ≥ +{int(BIG_MOVE_THRESHOLD*100)}%")
    return "\n".join(lines)


def main():
    md = run()
    with open(OUT_MD, "w") as fh:
        fh.write(md)
    print(f"[predict] wrote {OUT_MD}")
    for line in md.split("\n")[:4]:
        if line.startswith("_"):
            print(line[:150])


if __name__ == "__main__":
    main()
