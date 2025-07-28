# scripts/scrape_prices.py

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

def scrape_books():
    url = "http://books.toscrape.com/catalogue/page-1.html"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    books = soup.select(".product_pod")

    data = []
    for book in books:
        title = book.h3.a["title"]
        price = book.select_one(".price_color").text.replace("£", "")
        availability = book.select_one(".availability").text.strip()
        data.append({
            "title": title,
            "price": float(price),
            "availability": availability,
            "timestamp": datetime.now().isoformat()
        })
    
    return pd.DataFrame(data)

def save_to_csv(df, file_path="data/prices_log.csv"):
    os.makedirs("data", exist_ok=True)
    if os.path.exists(file_path):
        df.to_csv(file_path, mode="a", index=False, header=False)
    else:
        df.to_csv(file_path, index=False)

if __name__ == "__main__":
    df = scrape_books()
    save_to_csv(df)
