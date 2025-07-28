# scripts/prefect_pipeline.py

from prefect import flow, task
import pandas as pd
import numpy as np
import os
from datetime import datetime

@task
def generate_mock_data():
    os.makedirs("data", exist_ok=True)
    n = 100
    data = {
        "order_id": range(1, n + 1),
        "delivery_time_min": np.random.normal(loc=45, scale=10, size=n).round(0),
        "delayed": np.random.choice([0, 1], size=n, p=[0.8, 0.2])
    }
    df = pd.DataFrame(data)
    df.to_csv("data/delivery_data.csv", index=False)
    return "data/delivery_data.csv"

@task
def analyze_data(path):
    df = pd.read_csv(path)
    avg_time = df["delivery_time_min"].mean()
    delay_rate = df["delayed"].mean()
    results = pd.DataFrame([{
        "date": datetime.now().strftime("%Y-%m-%d"),
        "avg_delivery_time": round(avg_time, 2),
        "delay_rate": round(delay_rate, 2)
    }])
    os.makedirs("outputs", exist_ok=True)
    results.to_csv("outputs/kpi_report.csv", index=False)
    return results

@task
def notify(results):
    print("✅ Report generado:")
    print(results)

@flow(name="Delivery KPI Pipeline")
def logistics_pipeline():
    path = generate_mock_data()
    results = analyze_data(path)
    notify(results)

if __name__ == "__main__":
    logistics_pipeline()
