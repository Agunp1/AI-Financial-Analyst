"""
Diagnose how one company's SEC filings are tagged, to explain missing or
odd fundamental values.

Usage:
    python diagnose_company.py XOM > diag_XOM.txt
"""

import sys

import pandas as pd

import fundamental_engine as fe


def main(ticker: str) -> None:
    as_of = pd.Timestamp.now().normalize()
    cik = fe.fetch_ticker_map().get(ticker.upper())
    print(f"{ticker} CIK={cik} as of {as_of.date()}")
    if cik is None:
        return
    facts = fe.fetch_company_facts(cik)
    for item in ("revenue", "net_income", "operating_income", "operating_cash_flow"):
        print(f"\n=== {item} ===")
        for concept in fe.CONCEPTS[item]:
            df = fe.facts_frame(facts, "us-gaap", concept, as_of)
            if df.empty:
                print(f"  {concept}: not reported")
                continue
            print(f"  {concept}: {len(df)} periods, latest end {df['end'].max().date()}")
            print(df.tail(8)[["start", "end", "days", "val", "form", "filed"]].to_string(index=False))
        chosen = fe.concept_frame(facts, item, as_of)
        print(f"  -> TTM used: {fe.safe_ttm(chosen, None) if not chosen.empty else None}")
    names = sorted(c for c in facts.get("facts", {}).get("us-gaap", {})
                   if "Revenue" in c or "Sales" in c)
    print("\nAll revenue-like tags this company uses:", ", ".join(names))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "XOM")
