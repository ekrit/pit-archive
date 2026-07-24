"""CLI: measure what actually works, and write EVALUATION.md.

Modes:
  --from-store   evaluate the accumulated multi-source history (grows over
                 the months as the daily job logs snapshots). This is the
                 real prize: it can tell you whether news/Reddit/SEC signals
                 add edge, which nothing historical can.
  --from-prices  immediate price-signal backtest from a single yfinance pull;
                 usable today, before the store has accumulated. Price signals
                 only.

Both write a ranked signal table + walk-forward model result to EVALUATION.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os

from . import backtest, dataset, labels, model, store, universe

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_MD = os.path.join(ROOT, "EVALUATION.md")

PRICE_ONLY_FEATURES = ["ret_5d", "ret_21d", "ret_63d", "volume_spike_ratio", "rsi_14"]
ALL_FEATURES = dataset.FEATURE_KEYS  # base signals + the Alpha-factor battery


def from_store(horizon: int) -> tuple[list[dict], str]:
    records = store.load_features()
    if not records:
        return [], "No history yet. Run the daily screener for a while first."
    # Compile against the dense price archive: robust labels even for names that
    # have left the momentum screen, plus a written data-quality report.
    examples = dataset.compile_labeled(horizon=horizon, write=True)
    q = dataset.quality_report(examples, horizon)
    note = (
        f"{len(records)} feature snapshots across {len(store.distinct_dates(records))} dates → "
        f"{len(examples)} labeled examples at {horizon}d horizon "
        f"(pos rate {q['label_positive_rate']}, {q['distinct_tickers']} tickers)."
    )
    return examples, note


def from_prices(horizon: int, limit: int | None) -> tuple[list[dict], str]:
    from .sources import prices as price_src
    import yfinance as yf

    tickers = universe.discover()
    if limit:
        tickers = tickers[:limit]
    examples: list[dict] = []
    for tk in tickers:
        try:
            df = yf.download(tk, period="2y", interval="1d", auto_adjust=True,
                             progress=False)
        except Exception:
            continue
        if df is None or df.empty:
            continue
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df.columns = df.columns.get_level_values(0)
        ex = labels.price_history_examples(df, horizon=horizon)
        for e in ex:
            e["ticker"] = tk
        examples.extend(ex)
    note = f"{len(tickers)} tickers → {len(examples)} price-history examples at {horizon}d horizon."
    return examples, note


def write_report(rows, model_res, note, mode, horizon, decay_lines=None):
    lines = [
        "# Signal Evaluation — what actually works",
        "",
        f"_Generated: {dt.datetime.now(dt.timezone.utc).isoformat()} · mode: {mode} · "
        f"horizon: {horizon}d_",
        "",
        f"> {note}",
        "",
        "> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only "
        "when the mean IC is **consistent across many dates** (|t-stat| ≥ 2) AND the "
        "walk-forward out-of-sample numbers below hold up. Everything here is "
        "research, not advice.",
        "",
        backtest.to_markdown(rows, title=f"Per-signal edge ({horizon}d forward return)"),
        *(decay_lines or []),
        "## Walk-forward model (out-of-sample)",
        "",
        "A model that learns the weights, evaluated strictly on future data it "
        "never trained on:",
        "",
        "```",
    ]
    for k, v in model_res.items():
        lines.append(f"{k}: {v}")
    lines += ["```", ""]
    with open(EVAL_MD, "w") as fh:
        fh.write("\n".join(lines))
    print(f"[write] {EVAL_MD}")


def main():
    ap = argparse.ArgumentParser(description="Evaluate signal predictive power")
    ap.add_argument("--from-store", action="store_true", help="use accumulated history")
    ap.add_argument("--from-prices", action="store_true", help="immediate price-only backtest")
    ap.add_argument("--horizon", type=int, default=63, help="forward-return horizon in days")
    ap.add_argument("--horizons", type=str, default="21,63,126",
                    help="comma-separated horizons for the IC-decay table (store mode)")
    ap.add_argument("--limit", type=int, default=None, help="cap tickers (price mode)")
    args = ap.parse_args()

    if not (args.from_store or args.from_prices):
        args.from_store = True  # default

    if args.from_prices:
        examples, note = from_prices(args.horizon, args.limit)
        feats = PRICE_ONLY_FEATURES
        mode = "from-prices"
    else:
        examples, note = from_store(args.horizon)
        feats = ALL_FEATURES
        mode = "from-store"

    print(f"[eval] {note}")
    rows = backtest.run(examples)
    model_res = model.walk_forward(examples, [f for f in feats]) if examples else {
        "error": "no examples"}

    # Alphalens-style IC decay across horizons (store mode only — it can
    # recompile labels per horizon from the dense price archive).
    decay_lines: list[str] = []
    if mode == "from-store" and examples:
        horizons = [int(h) for h in args.horizons.split(",") if h.strip()]
        decay_lines, _ = backtest.ic_decay(
            lambda h: dataset.compile_labeled(horizon=h, write=False), horizons
        )

    write_report(rows, model_res, note, mode, args.horizon, decay_lines)

    print("\nTop signals by |mean IC|:")
    for r in rows[:8]:
        print(f"  {r['signal']:22s} IC={r['mean_ic']} t={r['t_stat']} spread={r['decile_spread']}")
    print(f"\nWalk-forward: {model_res}")


if __name__ == "__main__":
    main()
