"""End-to-end screener run: discover -> gather signals -> score -> write.

Usage:
    python -m scraper.main               # full run
    python -m scraper.main --limit 15    # cap universe (fast smoke test)
    python -m scraper.main --no-reddit --no-sec   # skip slow/blockable sources
"""
import argparse
import datetime as dt
import json
import os

from . import config, universe, store
from .sources import prices, sec_filings, news, reddit, stocktwits, wikipedia, short_interest
from .scoring import score

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANKINGS_DIR = os.path.join(ROOT, "data", "rankings")
RANKINGS_MD = os.path.join(ROOT, "RANKINGS.md")

DISCLAIMER = (
    "This is an automated, experimental momentum/attention **screener**, not "
    "financial advice and not a prediction. Scores are heuristic and have not "
    "been validated against any backtest. Markets are largely efficient; no "
    "tool can reliably predict which stock will multiply. Do your own research "
    "and never risk money you can't afford to lose."
)


def _merge(*source_outputs: dict[str, dict], tickers: list[str]) -> dict[str, dict]:
    merged = {tk: {} for tk in tickers}
    for out in source_outputs:
        for tk, feats in out.items():
            if tk in merged:
                merged[tk].update(feats)
    return merged


def run(limit: int | None, use_reddit: bool, use_sec: bool, use_news: bool) -> dict:
    tickers = universe.discover()
    if limit:
        tickers = tickers[:limit]
    print(f"[universe] {len(tickers)} tickers")

    print("[prices] fetching...")
    price_out = prices.fetch(tickers)
    print(f"[prices] {len(price_out)} with data")

    # Only score tickers we actually got price data for (the quantitative core).
    tickers = [t for t in tickers if t in price_out]

    # Build the dense price panel for label durability: today's universe plus
    # every previously-tracked ticker — and, when FULL_MARKET_ARCHIVE=1, the
    # entire US listing (~10k names) so movers are captured *before* they
    # ever hit a screener. Capped to bound API load.
    panel_tickers = list(dict.fromkeys(tickers + store.tracked_tickers()))
    if config.FULL_MARKET_ARCHIVE:
        try:
            panel_tickers = list(dict.fromkeys(panel_tickers + universe.full_market()))
        except Exception as e:  # full-market fetch is best-effort
            print(f"[universe] full-market fetch failed: {e}")
    if config.INTERNATIONAL_ARCHIVE:
        intl = universe.international()
        panel_tickers = list(dict.fromkeys(panel_tickers + intl))
        print(f"[universe] +{len(intl)} international tickers in price archive")
    if limit is None:
        panel_tickers = panel_tickers[: config.MAX_PRICE_ARCHIVE_TICKERS]
    price_panel = prices.fetch_price_panel(panel_tickers)
    print(f"[prices] price panel for {len(price_panel)} tickers")

    news_out = news.fetch(tickers) if use_news else {}
    if use_news:
        print(f"[news] {len(news_out)} fetched")
    sec_out = sec_filings.fetch(tickers) if use_sec else {}
    if use_sec:
        print(f"[sec] {len(sec_out)} fetched")
    reddit_out = reddit.fetch(tickers) if use_reddit else {}
    if use_reddit:
        total = sum(v.get("reddit_mentions", 0) for v in reddit_out.values())
        print(f"[reddit] {total} total mentions")

    # Additional attention/positioning sources (all free, best-effort).
    st_out = stocktwits.fetch(tickers)
    print(f"[stocktwits] {sum(1 for v in st_out.values() if v.get('st_msg_count'))} with messages")
    wiki_out = wikipedia.fetch(tickers)
    print(f"[wikipedia] {sum(1 for v in wiki_out.values() if v.get('wiki_views_7d'))} with views")
    short_out = short_interest.fetch(tickers)
    print(f"[finra] {sum(1 for v in short_out.values() if v.get('short_vol_ratio') is not None)} with short ratio")

    merged = _merge(price_out, news_out, sec_out, reddit_out, st_out, wiki_out,
                    short_out, tickers=tickers)
    ranked = score(merged)

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "universe_size": len(tickers),
        "disclaimer": DISCLAIMER,
        "results": ranked,
        "price_panel": price_panel,
    }


def write_outputs(payload: dict) -> None:
    os.makedirs(RANKINGS_DIR, exist_ok=True)
    date_str = dt.date.today().isoformat()
    json_path = os.path.join(RANKINGS_DIR, f"{date_str}.json")
    with open(json_path, "w") as fh:
        json.dump(payload, fh, indent=2)
    print(f"[write] {json_path}")

    # Append a point-in-time snapshot so a labeled dataset accumulates over
    # time. This is what makes real evaluation/training possible in a few
    # months (see scraper/evaluate.py and STRATEGY.md).
    n_rows = store.append_snapshot(payload["results"], date=date_str)
    print(f"[store] appended {n_rows} feature rows")

    # Archive a dense price panel for EVERY ticker ever tracked (not just
    # today's hot list), so forward-return labels survive universe churn -- the
    # winners usually leave the momentum screen right around their big move.
    if payload.get("price_panel"):
        n_px = store.append_prices(payload["price_panel"])
        print(f"[store] archived {n_px} price rows")

    top = payload["results"][: config.TOP_N_RESULTS]
    lines = [
        "# Daily Screener Rankings",
        "",
        f"_Generated: {payload['generated_at']} · Universe: {payload['universe_size']} tickers_",
        "",
        f"> {payload['disclaimer']}",
        "",
        "| # | Ticker | Score | 21d ret | 63d ret | Vol spike | News | Reddit |",
        "|--:|:------:|------:|--------:|--------:|----------:|-----:|-------:|",
    ]
    for i, r in enumerate(top, 1):
        f = r["features"]
        def pct(x):
            return f"{x*100:.1f}%" if isinstance(x, (int, float)) else "—"
        def num(x):
            return f"{x:.2f}" if isinstance(x, (int, float)) else "—"
        lines.append(
            f"| {i} | {r['ticker']} | {r['score']:.1f} | "
            f"{pct(f.get('ret_21d'))} | {pct(f.get('ret_63d'))} | "
            f"{num(f.get('volume_spike_ratio'))} | "
            f"{f.get('news_count', '—')} | {f.get('reddit_mentions', '—')} |"
        )
    lines.append("")
    with open(RANKINGS_MD, "w") as fh:
        fh.write("\n".join(lines))
    print(f"[write] {RANKINGS_MD}")


def main():
    ap = argparse.ArgumentParser(description="Momentum/attention stock screener")
    ap.add_argument("--limit", type=int, default=None, help="cap universe size")
    ap.add_argument("--no-reddit", action="store_true")
    ap.add_argument("--no-sec", action="store_true")
    ap.add_argument("--no-news", action="store_true")
    args = ap.parse_args()

    payload = run(
        limit=args.limit,
        use_reddit=not args.no_reddit,
        use_sec=not args.no_sec,
        use_news=not args.no_news,
    )
    write_outputs(payload)

    top5 = payload["results"][:5]
    print("\nTop 5 by composite score:")
    for r in top5:
        print(f"  {r['ticker']:6s} {r['score']:.1f}")


if __name__ == "__main__":
    main()
