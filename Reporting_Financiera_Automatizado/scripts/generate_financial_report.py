# scripts/generate_financial_report.py

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from weasyprint import HTML
import os
from datetime import datetime

def generate_financial_data():
    months = pd.date_range(start="2024-01", periods=6, freq="M")
    data = {
        "month": months.strftime("%Y-%m"),
        "revenue": np.random.randint(8000, 15000, len(months)),
        "expenses": np.random.randint(4000, 10000, len(months))
    }
    df = pd.DataFrame(data)
    df["profit"] = df["revenue"] - df["expenses"]
    df["margin"] = (df["profit"] / df["revenue"]).round(2)
    return df

def plot_financials(df):
    os.makedirs("reports", exist_ok=True)
    df.plot(x="month", y=["revenue", "expenses", "profit"], kind="bar", figsize=(10, 5))
    plt.title("Resumen financiero por mes")
    plt.ylabel("€")
    plt.tight_layout()
    plt.savefig("reports/financial_chart.png")
    plt.close()

def create_html(df):
    table_html = df.to_html(index=False)
    html = f"""
    <html>
    <head><style>
        body {{ font-family: Arial; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; }}
        th {{ background-color: #f2f2f2; }}
    </style></head>
    <body>
        <h1>Informe Financiero - {datetime.now().strftime("%B %Y")}</h1>
        <h2>KPIs Financieros</h2>
        {table_html}
        <h2>Gráfico de Resultados</h2>
        <img src="financial_chart.png" width="700">
    </body>
    </html>
    """
    with open("reports/financial_report.html", "w") as f:
        f.write(html)

def generate_pdf():
    HTML("reports/financial_report.html").write_pdf("reports/financial_report.pdf")

if __name__ == "__main__":
    df = generate_financial_data()
    plot_financials(df)
    create_html(df)
    generate_pdf()
    print("Informe generado en reports/financial_report.pdf")
