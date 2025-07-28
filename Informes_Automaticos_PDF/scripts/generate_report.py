# scripts/generate_report.py

from weasyprint import HTML
import os

def create_html():
    tickers = ["AAPL", "MSFT", "AMZN"]
    content = "<h1>Informe Semanal de Acciones</h1>"
    for ticker in tickers:
        content += f"<h2>{ticker}</h2>"
        content += f'<img src="data/{ticker}_price.png" width="600"><br>'
        content += f'<img src="data/{ticker}_return.png" width="600"><br><hr>'
    return content

def generate_pdf():
    html_content = create_html()
    with open("reports/report.html", "w") as f:
        f.write(html_content)
    HTML("reports/report.html").write_pdf("reports/weekly_report.pdf")

if __name__ == "__main__":
    os.makedirs("reports", exist_ok=True)
    generate_pdf()
