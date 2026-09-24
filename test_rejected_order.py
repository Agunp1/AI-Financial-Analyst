
from paper_orders import execute_paper_order, OrderError


def main():
    print("Testing Day 35 risk controls...")
    print("Attempting to sell 1,000,000 AAPL shares.")

    try:
        execute_paper_order(
            ticker="AAPL",
            side="SELL",
            quantity=1_000_000,
            price=338.98,
        )

    except OrderError as error:
        print("PASS: Oversized sell order rejected.")
        print("Reason:", error)

    else:
        print("FAIL: Oversized sell order was accepted!")


if __name__ == "__main__":
    main()