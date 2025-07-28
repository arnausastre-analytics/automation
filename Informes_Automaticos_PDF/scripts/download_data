# scripts/download_data.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def download_stock_data(tickers, period="3mo", interval="1d"):
    data = {}
    for ticker in tickers:
        df = yf.download(ticker, period=period, interval=interval)
        df.to_csv(f"data/{ticker}.csv")
        data[ticker] = df
    return data

if __name__ == "__main__":
    tickers = ["AAPL", "MSFT", "AMZN"]
    download_stock_data(tickers)
