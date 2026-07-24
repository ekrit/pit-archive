"""Evaluate whether signals actually predict forward returns.

Given labeled examples (each with `features`, optional `score`, and a
realized `fwd_ret`), this computes, per signal and for the composite score:

  - cross-sectional Information Coefficient (mean, std, t-stat) computed
    date-by-date and then averaged (the correct, leakage-free way — never
    pool all dates into one correlation);
  - top-minus-bottom decile forward-return spread;
  - hit rate of the top quintile.

The output ranks signals by evidence of edge, so you can see which scrapers
are worth keeping and which are noise.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from . import metrics

# Signals where a *higher* raw value is hypothesized to predict higher return.
# (For distance-from-high etc. the sign is ambiguous; IC will reveal it.)
PRICE_SIGNALS = [
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "volume_spike_ratio",
    "rsi_14",
    "pct_off_52w_high",
    "pct_above_52w_low",
    "annualized_vol",
]
ATTENTION_SIGNALS = [
    "news_count",
    "news_sentiment",
    "reddit_mentions",
    "reddit_sentiment",
    "sec_form4_recent",
    "sec_8k_recent",
]


def _group_by_date(examples: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in examples:
        groups[e.get("date", "?")].append(e)
    return groups


def _signal_values(bucket: list[dict], key: str) -> np.ndarray:
    vals = []
    for e in bucket:
        if key == "__score__":
            vals.append(e.get("score"))
        else:
            vals.append((e.get("features") or {}).get(key))
    return np.array([v if isinstance(v, (int, float)) else np.nan for v in vals], dtype=float)


def evaluate_signal(examples: list[dict], key: str, min_names_per_date: int = 5) -> dict:
    """Per-date IC then summarize; plus pooled decile spread and hit rate."""
    per_date_ic: list[float] = []
    for _, bucket in _group_by_date(examples).items():
        if len(bucket) < min_names_per_date:
            continue
        sig = _signal_values(bucket, key)
        fwd = np.array([e["fwd_ret"] for e in bucket], dtype=float)
        ic = metrics.spearman(sig, fwd)
        if ic is not None:
            per_date_ic.append(ic)

    summ = metrics.ic_summary(per_date_ic)

    # Pooled economic metrics (across all examples).
    all_sig = _signal_values(examples, key)
    all_fwd = np.array([e["fwd_ret"] for e in examples], dtype=float)
    spread = metrics.decile_spread(all_sig, all_fwd)
    hr = metrics.hit_rate(all_sig, all_fwd)

    return {
        "signal": key if key != "__score__" else "composite_score",
        **summ,
        "decile_spread": spread["spread"],
        "top_decile_ret": spread["top"],
        "bottom_decile_ret": spread["bottom"],
        "top_quintile_hit_rate": round(hr, 3) if hr is not None else None,
    }


def run(examples: list[dict], signals: list[str] | None = None) -> list[dict]:
    """Evaluate the composite score plus every requested signal, ranked by |mean IC|."""
    if not examples:
        return []
    if signals is None:
        present = set()
        for e in examples:
            present.update((e.get("features") or {}).keys())
        signals = [s for s in (PRICE_SIGNALS + ATTENTION_SIGNALS) if s in present]

    rows = []
    if any(e.get("score") is not None for e in examples):
        rows.append(evaluate_signal(examples, "__score__"))
    for key in signals:
        rows.append(evaluate_signal(examples, key))

    def sort_key(r):
        return abs(r["mean_ic"]) if r["mean_ic"] is not None else -1.0

    rows.sort(key=sort_key, reverse=True)
    return rows


def to_markdown(rows: list[dict], title: str = "Signal Evaluation") -> str:
    lines = [
        f"## {title}",
        "",
        "IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. "
        "A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.",
        "",
        "| Signal | mean IC | IC t-stat | dates | decile spread | top-quintile hit |",
        "|--------|--------:|----------:|------:|--------------:|-----------------:|",
    ]
    for r in rows:
        def f(x, pct=False):
            if x is None:
                return "—"
            return f"{x*100:.1f}%" if pct else f"{x:.4f}"
        lines.append(
            f"| {r['signal']} | {f(r['mean_ic'])} | "
            f"{r['t_stat'] if r['t_stat'] is not None else '—'} | "
            f"{r['n']} | {f(r['decile_spread'], pct=True)} | "
            f"{f(r['top_quintile_hit_rate'])} |"
        )
    lines.append("")
    return "\n".join(lines)
