# scripts/visualize.py

import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_price(ticker):
    df = pd.read_csv(f"data/{ticker}_analyzed.csv", parse_dates=["Date"], index_col="Date")
    plt.figure(figsize=(10, 4))
    plt.plot(df["Adj Close"], label="Adj Close")
    plt.plot(df["SMA_10"], label="SMA 10 días")
    plt.title(f"{ticker} - Precio y Media Móvil")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"data/{ticker}_price.png")
    plt.close()

def plot_return(ticker):
    df = pd.read_csv(f"data/{ticker}_analyzed.csv", parse_dates=["Date"], index_col="Date")
    plt.figure(figsize=(10, 4))
    plt.plot(df["Cumulative Return"], label="Retorno acumulado", color="green")
    plt.title(f"{ticker} - Retorno acumulado")
    plt.legend()
    plt.tight_layout()
    plt.savefig(f"data/{ticker}_return.png")
    plt.close()

if __name__ == "__main__":
    for ticker in ["AAPL", "MSFT", "AMZN"]:
        plot_price(ticker)
        plot_return(ticker)
