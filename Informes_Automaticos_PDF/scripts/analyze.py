# scripts/analyze.py

import pandas as pd
import os

def analyze_stock(ticker):
    df = pd.read_csv(f"data/{ticker}.csv", parse_dates=["Date"], index_col="Date")
    df["Return"] = df["Adj Close"].pct_change()
    df["Cumulative Return"] = (1 + df["Return"]).cumprod()
    df["SMA_10"] = df["Adj Close"].rolling(window=10).mean()
    df.to_csv(f"data/{ticker}_analyzed.csv")
    return df

if __name__ == "__main__":
    for ticker in ["AAPL", "MSFT", "AMZN"]:
        analyze_stock(ticker)
