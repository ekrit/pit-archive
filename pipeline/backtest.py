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
    "st_trending",
    "st_msg_count",
    "st_sentiment",
    "wiki_views_7d",
    "wiki_spike_ratio",
    "short_vol_ratio",
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


def _residualize(sig: np.ndarray, base: np.ndarray) -> np.ndarray:
    """Residual of sig after removing its linear dependence on base (per date).

    The neutralized IC answers the question that separates a genuinely new
    signal from repackaged momentum: does it still rank winners after the
    momentum everyone already has is stripped out?
    """
    mask = np.isfinite(sig) & np.isfinite(base)
    out = np.full_like(sig, np.nan)
    if mask.sum() < 3:
        return out
    s, b = sig[mask], base[mask]
    bv = b - b.mean()
    denom = (bv ** 2).sum()
    beta = ((s - s.mean()) * bv).sum() / denom if denom > 0 else 0.0
    out[mask] = s - beta * b
    return out


NEUTRALIZE_AGAINST = "ret_21d"  # the baseline everyone already has


def evaluate_signal(examples: list[dict], key: str, min_names_per_date: int = 5) -> dict:
    """Per-date IC (raw + momentum-neutralized); pooled decile spread, hit rate."""
    per_date_ic: list[float] = []
    per_date_neut: list[float] = []
    for _, bucket in _group_by_date(examples).items():
        if len(bucket) < min_names_per_date:
            continue
        sig = _signal_values(bucket, key)
        fwd = np.array([e["fwd_ret"] for e in bucket], dtype=float)
        ic = metrics.spearman(sig, fwd)
        if ic is not None:
            per_date_ic.append(ic)
        if key not in ("__score__", NEUTRALIZE_AGAINST):
            base = _signal_values(bucket, NEUTRALIZE_AGAINST)
            nic = metrics.spearman(_residualize(sig, base), fwd)
            if nic is not None:
                per_date_neut.append(nic)

    summ = metrics.ic_summary(per_date_ic)
    neut = metrics.ic_summary(per_date_neut) if per_date_neut else None

    # Pooled economic metrics (across all examples).
    all_sig = _signal_values(examples, key)
    all_fwd = np.array([e["fwd_ret"] for e in examples], dtype=float)
    spread = metrics.decile_spread(all_sig, all_fwd)
    hr = metrics.hit_rate(all_sig, all_fwd)

    return {
        "signal": key if key != "__score__" else "composite_score",
        **summ,
        "neut_ic": neut["mean_ic"] if neut else None,
        "neut_t_stat": neut["t_stat"] if neut else None,
        "decile_spread": spread["spread"],
        "top_decile_ret": spread["top"],
        "bottom_decile_ret": spread["bottom"],
        "top_quintile_hit_rate": round(hr, 3) if hr is not None else None,
    }


def signal_turnover(examples: list[dict], key: str, top_frac: float = 0.2) -> float | None:
    """Mean day-over-day turnover of the signal's top quantile (Alphalens-style).

    1.0 = the top bucket is completely remade every date (expensive to trade,
    likely noise); 0.0 = perfectly persistent. Needs >= 2 dates.
    """
    dates = sorted(_group_by_date(examples).items())
    prev: set | None = None
    turns: list[float] = []
    for _, bucket in dates:
        sig = _signal_values(bucket, key)
        tickers = [e.get("ticker", f"?{i}") for i, e in enumerate(bucket)]
        mask = np.isfinite(sig)
        if mask.sum() < 5:
            continue
        order = np.argsort(sig)
        k = max(1, int(round(mask.sum() * top_frac)))
        top = {tickers[i] for i in order[-k:]}
        if prev is not None and prev:
            turns.append(1.0 - len(top & prev) / max(len(top), 1))
        prev = top
    return round(float(np.mean(turns)), 3) if turns else None


def run(examples: list[dict], signals: list[str] | None = None) -> list[dict]:
    """Evaluate the composite score plus every requested signal, ranked by |mean IC|."""
    if not examples:
        return []
    if signals is None:
        # Evaluate EVERY numeric feature present (known names first, then the
        # rest — e.g. the Alpha-factor battery — in stable order).
        present: list[str] = []
        seen = set()
        for e in examples:
            for k, v in (e.get("features") or {}).items():
                if k not in seen and isinstance(v, (int, float)):
                    seen.add(k)
                    present.append(k)
        known = [s for s in (PRICE_SIGNALS + ATTENTION_SIGNALS) if s in seen]
        signals = known + [s for s in present if s not in known and s != "last_price"]

    rows = []
    if any(e.get("score") is not None for e in examples):
        rows.append(evaluate_signal(examples, "__score__"))
    for key in signals:
        rows.append(evaluate_signal(examples, key))
    for r in rows:
        key = "__score__" if r["signal"] == "composite_score" else r["signal"]
        r["turnover"] = signal_turnover(examples, key)

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
        "| Signal | mean IC | IC t-stat | neut IC | dates | decile spread | top-quintile hit | turnover |",
        "|--------|--------:|----------:|--------:|------:|--------------:|-----------------:|---------:|",
    ]
    for r in rows:
        def f(x, pct=False):
            if x is None:
                return "—"
            return f"{x*100:.1f}%" if pct else f"{x:.4f}"
        lines.append(
            f"| {r['signal']} | {f(r['mean_ic'])} | "
            f"{r['t_stat'] if r['t_stat'] is not None else '—'} | "
            f"{f(r.get('neut_ic'))} | "
            f"{r['n']} | {f(r['decile_spread'], pct=True)} | "
            f"{f(r['top_quintile_hit_rate'])} | "
            f"{f(r.get('turnover'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def ic_decay(compile_fn, horizons: list[int], top_k: int = 12) -> tuple[list[str], dict]:
    """Alphalens-style IC decay: mean IC of each signal across horizons.

    `compile_fn(horizon)` must return labeled examples for that horizon.
    Returns (markdown lines, {signal: {horizon: mean_ic}}).
    """
    table: dict[str, dict[int, float | None]] = {}
    for h in horizons:
        examples = compile_fn(h)
        if not examples:
            continue
        for r in run(examples):
            table.setdefault(r["signal"], {})[h] = r["mean_ic"]
    if not table:
        return [], {}

    # Rank signals by their best |IC| across horizons; keep the top_k.
    def best(sig):
        vals = [abs(v) for v in table[sig].values() if v is not None]
        return max(vals) if vals else -1

    ranked = sorted(table, key=best, reverse=True)[:top_k]
    header = "| Signal | " + " | ".join(f"{h}d IC" for h in horizons) + " |"
    sep = "|--------|" + "|".join("-------:" for _ in horizons) + "|"
    lines = ["## IC decay across horizons", "",
             "How each signal's predictive power changes with holding period — "
             "a real signal usually decays smoothly; a leak or fluke jumps around.",
             "", header, sep]
    for sig in ranked:
        cells = []
        for h in horizons:
            v = table[sig].get(h)
            cells.append(f"{v:.4f}" if v is not None else "—")
        lines.append(f"| {sig} | " + " | ".join(cells) + " |")
    lines.append("")
    return lines, table
