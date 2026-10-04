"""
My Portfolio: anyone can build their own portfolio from Vittantra's investable
universe and see its value, mix, risk, limits and stress tests.

Risk uses the Day 81 risk model (whatif_engine): shrinkage covariance, VaR/ES,
beta and Euler risk shares, on daily prices. As advisers do in an investment
policy statement, the portfolio is judged against the owner's chosen risk level
(the advisory risk profiles' target volatility), plus diversification checks.
Nothing is traded — this is a model portfolio for learning.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
PORTFOLIO_DIR = BASE_DIR / "portfolios"
ANALYTICS = "day76c_asset_analytics.csv"
PRICE_HISTORY = "day76c_price_history.csv"
RATINGS = "day77_current_ratings.csv"

# Diversification guardrails professionals use for personal portfolios.
MAX_SINGLE_STOCK = 0.20          # one company above 20% of the portfolio is concentrated
MAX_CRYPTO = 0.10                # speculative assets kept small
MAX_RISK_SHARE = 0.50            # one holding driving more than half the risk

TEMPLATES: Dict[str, dict] = {
    "Classic 60/40": {"about": "60% US stocks, 40% bonds — the traditional balanced portfolio.",
                      "weights": {"SPY": 0.60, "AGG": 0.40}},
    "Global diversified": {"about": "Stocks at home and abroad, bonds, real estate and gold.",
                           "weights": {"SPY": 0.35, "EFA": 0.15, "AGG": 0.25, "VNQ": 0.10, "GLD": 0.15}},
    "Growth": {"about": "Mostly equities, with a little gold and bitcoin for diversification.",
               "weights": {"SPY": 0.45, "QQQ": 0.30, "EFA": 0.10, "GLD": 0.10, "BTC-USD": 0.05}},
    "Income": {"about": "Bonds, credit, dividend-heavy real estate and infrastructure.",
               "weights": {"AGG": 0.35, "LQD": 0.20, "HYG": 0.10, "VNQ": 0.15, "AMLP": 0.10, "SPY": 0.10}},
}


# ==============================================================
# UNIVERSE AND PRICES
# ==============================================================

def universe(base: Path = BASE_DIR) -> pd.DataFrame:
    """Investable instruments with a price: the multi-asset universe plus the research-universe stocks."""
    rows = []
    analytics, history = base / ANALYTICS, base / PRICE_HISTORY
    if analytics.exists():
        tradable = set(pd.read_csv(history, nrows=0).columns[1:]) if history.exists() else None
        a = pd.read_csv(analytics)
        a = a[a["price"].notna() & ~a["symbol"].astype(str).str.startswith("^")]
        if tradable is not None:
            a = a[a["symbol"].isin(tradable)]
        rows.append(a[["symbol", "name", "asset_class", "sub_class", "price"]])
    ratings = base / RATINGS
    if ratings.exists():
        r = pd.read_csv(ratings)
        if "price" in r.columns:
            r = r[r["price"].notna()].rename(columns={"ticker": "symbol", "sector": "sub_class"})
            r["asset_class"] = "Stock"
            rows.append(r[["symbol", "name", "asset_class", "sub_class", "price"]])
    if not rows:
        return pd.DataFrame(columns=["symbol", "name", "asset_class", "sub_class", "price"])
    out = pd.concat(rows, ignore_index=True).drop_duplicates("symbol")
    return out.sort_values(["asset_class", "symbol"]).reset_index(drop=True)


def from_weights(weights: Dict[str, float], amount: float, table: pd.DataFrame) -> List[dict]:
    """Turn target weights and an amount into quantities at today's prices (skips symbols without a price)."""
    prices = table.set_index("symbol")["price"]
    return [{"symbol": s, "quantity": round(amount * w / float(prices[s]), 6)}
            for s, w in weights.items() if s in prices.index and prices[s] > 0]


# ==============================================================
# VALUE, MIX AND RISK
# ==============================================================

def valuation(holdings: List[dict], table: pd.DataFrame) -> pd.DataFrame:
    info = table.set_index("symbol")
    rows = []
    for h in holdings:
        symbol, qty = str(h.get("symbol", "")).strip().upper(), float(h.get("quantity") or 0)
        if not symbol or qty <= 0 or symbol not in info.index:
            continue
        price = float(info.at[symbol, "price"])
        rows.append({"symbol": symbol, "name": info.at[symbol, "name"], "asset_class": info.at[symbol, "asset_class"],
                     "quantity": qty, "price": price, "market_value": qty * price})
    frame = pd.DataFrame(rows, columns=["symbol", "name", "asset_class", "quantity", "price", "market_value"])
    if not frame.empty:
        frame = frame.groupby(["symbol", "name", "asset_class", "price"], as_index=False)[["quantity", "market_value"]].sum()
        frame["weight"] = frame["market_value"] / frame["market_value"].sum()
    return frame


def build_model(base: Path = BASE_DIR):
    """Daily risk model: the multi-asset history, plus research stocks when their history is daily too."""
    import whatif_engine as we
    frames = []
    history = base / PRICE_HISTORY
    if history.exists():
        frames.append(pd.read_csv(history, index_col=0, parse_dates=True))
    try:
        import multi_factor_rating as mfr
        stocks, _ = mfr.load_prices()
        spacing = pd.Series(stocks.index).diff().dt.days.median()
        if len(stocks) and spacing <= 1.5:
            frames.append(stocks)
    except Exception:
        pass
    prices = we.align_prices(frames) if frames else pd.DataFrame()
    return we.RiskModel(prices, we.load_fred(base))


def profiles() -> Dict[int, dict]:
    from advisory_engine import PROFILES
    return PROFILES


def risk_level_status(volatility: float, target: float) -> str:
    ratio = volatility / target if target else float("inf")
    if ratio <= 1.0:
        return "ON TARGET"
    if ratio <= 1.2:
        return "SLIGHTLY ABOVE"
    return "ABOVE RISK LEVEL"


def analyse(holdings: List[dict], model, table: pd.DataFrame, profile: int = 3) -> Dict[str, object]:
    """Value, mix, risk vs the chosen risk level, diversification checks and stress tests."""
    import whatif_engine as we

    positions = valuation(holdings, table)
    if positions.empty:
        return {"positions": positions, "error": "Add at least one holding with a price."}
    value = float(positions["market_value"].sum())
    weights = dict(zip(positions["symbol"], positions["weight"]))
    risk = we.portfolio_risk(model, weights, value)
    if risk.get("error"):
        return {"positions": positions, "value": value, "missing": risk.get("missing"),
                "error": "None of these holdings has enough daily price history for a risk estimate yet."}
    positions["risk_share"] = positions["symbol"].map(risk["risk_shares"])
    mix = positions.groupby("asset_class")["weight"].sum().sort_values(ascending=False)
    level = profiles()[profile]
    vol = float(risk["volatility_annual"])
    checks = []
    stocks = positions[positions["asset_class"] == "Stock"]
    big = stocks[stocks["weight"] > MAX_SINGLE_STOCK]
    checks.append(("No single company above 20% of the portfolio", big.empty,
                   "Concentrated in " + ", ".join(big["symbol"]) if len(big) else "Company risk is spread out"))
    crypto = float(positions.loc[positions["asset_class"] == "Digital Asset", "weight"].sum())
    checks.append(("Crypto at most 10% of the portfolio", crypto <= MAX_CRYPTO, f"Crypto weight {crypto:.0%}"))
    top = positions.sort_values("risk_share", ascending=False).iloc[0]
    checks.append(("No holding drives more than half the risk", bool(top["risk_share"] <= MAX_RISK_SHARE),
                   f"Largest: {top['symbol']} with {top['risk_share']:.0%} of the risk"))
    checks.append(("Spread across at least 3 asset classes", len(mix) >= 3, f"{len(mix)} asset class(es)"))
    scenarios = {}
    for name, shocks in we.SCENARIOS.items():
        pnl = we.scenario_pnl(model, weights, shocks, value)["pnl"]
        scenarios[name] = float(pnl.sum(min_count=1)) if pnl.notna().any() else float("nan")
    tips = []
    if vol > level["target_vol"]:
        tips.append(f"Volatility {vol:.1%} is above the {level['name']} level ({level['target_vol']:.0%}): add "
                    "bonds or cash, or trim the riskiest holdings shown in 'What drives your risk'.")
    tips += [f"{name}: {detail}." for name, ok, detail in checks if not ok]
    return {"positions": positions, "value": value, "mix": mix, "risk": risk, "volatility": vol,
            "profile": level, "status": risk_level_status(vol, level["target_vol"]), "checks": checks,
            "scenarios": scenarios, "tips": tips, "missing": risk.get("missing", [])}


# ==============================================================
# SAVING (one file per user, committed by the app when online)
# ==============================================================

def portfolio_file(user: str) -> Path:
    return PORTFOLIO_DIR / f"{user.strip().lower()}.json"


def load(user: Optional[str]) -> dict:
    if not user:
        return {"holdings": []}
    try:
        data = json.loads(portfolio_file(user).read_text())
        return data if isinstance(data, dict) else {"holdings": []}
    except Exception:
        return {"holdings": []}


def save(user: str, holdings: List[dict], profile: int = 3, name: str = "My portfolio") -> Path:
    path = portfolio_file(user)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = [{"symbol": str(h["symbol"]).strip().upper(), "quantity": float(h["quantity"])}
             for h in holdings if str(h.get("symbol", "")).strip() and float(h.get("quantity") or 0) > 0]
    path.write_text(json.dumps({"name": name, "profile": int(profile), "holdings": clean, "updated_utc":
                                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                "note": "Hypothetical model portfolio for learning; nothing is traded."}, indent=2))
    return path
