# scripts/price_monitor.py
# Monitoreo de precios y alertas de competencia
# - Lee config/targets.csv
# - Hace scraping (requests + BeautifulSoup) con backoff
# - Guarda histórico en outputs/price_history.csv
# - Genera alerts_YYYYMMDD.csv y summary_YYYYMMDD.md
# - Envía alerta a Slack y/o Email si hay cambios relevantes

import os
import re
import smtplib
import argparse
import random
import time
from email.mime.text import MIMEText
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

USER_AGENTS = [
    # algunos UAs comunes para reducir bloqueos
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36",
]

PRICE_PATTERN = re.compile(r"(\d+[.,]?\d*)")

@dataclass
class Target:
    sku: str
    name: str
    our_price: float
    url: str
    price_selector: str
    stock_selector: Optional[str] = None

def _headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
    }

class FetchError(Exception):
    pass

@retry(
    reraise=True,
    retry=retry_if_exception_type(FetchError),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    stop=stop_after_attempt(4),
)
def fetch_html(url: str, timeout: int = 20) -> str:
    try:
        resp = requests.get(url, headers=_headers(), timeout=timeout)
        if resp.status_code >= 400:
            raise FetchError(f"HTTP {resp.status_code} on {url}")
        return resp.text
    except requests.RequestException as e:
        raise FetchError(str(e))

def parse_price(text: str) -> Optional[float]:
    # extrae primer número tipo 1.234,56 o 1234.56
    m = PRICE_PATTERN.search(text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(1)
    # normaliza: primero quitamos separadores de miles
    if raw.count(",") > 0 and raw.count(".") > 0:
        # asume formato europeo: 1.234,56
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None

def extract_price_and_stock(html: str, price_selector: str, stock_selector: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    price_el = soup.select_one(price_selector)
    price = parse_price(price_el.get_text(strip=True)) if price_el else None

    stock_text = None
    if stock_selector:
        st_el = soup.select_one(stock_selector)
        if st_el:
            stock_text = st_el.get_text(" ", strip=True).lower()
    return price, stock_text

def post_to_slack(webhook_url: str, text: str):
    try:
        requests.post(webhook_url, json={"text": text}, timeout=10)
    except Exception:
        pass

def send_email(host: str, port: int, user: str, password: str, to_addr: str, subject: str, body: str):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    with smtplib.SMTP(host, int(port)) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)

def load_targets(path: str) -> List[Target]:
    df = pd.read_csv(path)
    df = df.fillna("")
    targets = []
    for _, r in df.iterrows():
        targets.append(Target(
            sku=str(r["sku"]).strip(),
            name=str(r.get("name", "")).strip(),
            our_price=float(r["our_price"]),
            url=str(r["url"]).strip(),
            price_selector=str(r["price_selector"]).strip(),
            stock_selector=str(r.get("stock_selector", "")).strip() or None
        ))
    return targets

def ensure_dirs(outdir: str):
    os.makedirs(outdir, exist_ok=True)

def monitor(config_path: str, outdir: str, delta_pct: float):
    ensure_dirs(outdir)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    history_path = os.path.join(outdir, "price_history.csv")
    alerts_path  = os.path.join(outdir, f"alerts_{today.replace('-','')}.csv")
    summary_path = os.path.join(outdir, f"summary_{today.replace('-','')}.md")

    targets = load_targets(config_path)
    rows = []
    alerts = []

    for t in targets:
        try:
            html = fetch_html(t.url)
            price, stock_text = extract_price_and_stock(html, t.price_selector, t.stock_selector)
            comp_price = price if price is not None else float("nan")
            in_stock = None
            if stock_text is not None:
                # heurística simple
                in_stock = not any(k in stock_text for k in ["out of stock", "agotado", "sin stock", "no disponible"])

            diff_abs = comp_price - t.our_price if pd.notna(comp_price) else float("nan")
            diff_pct = (diff_abs / t.our_price * 100.0) if pd.notna(comp_price) else float("nan")

            rows.append({
                "date": today,
                "sku": t.sku,
                "name": t.name,
                "our_price": t.our_price,
                "competitor_price": comp_price,
                "diff_abs": diff_abs,
                "diff_pct": diff_pct,
                "in_stock": in_stock,
                "url": t.url,
            })

            # criterio de alerta: competidor más barato que nosotros por más del delta_pct
            if pd.notna(comp_price) and diff_pct < -abs(delta_pct):
                alerts.append({
                    "date": today,
                    "sku": t.sku,
                    "name": t.name,
                    "our_price": t.our_price,
                    "competitor_price": comp_price,
                    "delta_pct": round(diff_pct, 2),
                    "reason": f"Competidor más barato {abs(round(diff_pct,2))}%"
                })

            # criterio de oportunidad: competidor sin stock y nosotros sí vendemos
            if in_stock is False:
                alerts.append({
                    "date": today,
                    "sku": t.sku,
                    "name": t.name,
                    "our_price": t.our_price,
                    "competitor_price": comp_price,
                    "delta_pct": round(diff_pct, 2) if pd.notna(diff_pct) else "",
                    "reason": "Competidor sin stock (o no disponible)"
                })

            # pausas pequeñas para no saturar
            time.sleep(random.uniform(0.8, 1.8))

        except Exception as e:
            rows.append({
                "date": today, "sku": t.sku, "name": t.name, "our_price": t.our_price,
                "competitor_price": float("nan"), "diff_abs": float("nan"), "diff_pct": float("nan"),
                "in_stock": None, "url": t.url, "error": str(e)[:200]
            })

    df_today = pd.DataFrame(rows)

    # Actualiza histórico
    if os.path.exists(history_path):
        hist = pd.read_csv(history_path)
        hist = pd.concat([hist, df_today], ignore_index=True)
    else:
        hist = df_today.copy()
    hist.to_csv(history_path, index=False)

    # Guarda alertas y resumen
    if alerts:
        alerts_df = pd.DataFrame(alerts)
        alerts_df.to_csv(alerts_path, index=False)

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Price Monitor – {today}\n\n")
        f.write(f"- Targets: **{len(targets)}**\n")
        f.write(f"- Cambios relevantes: **{len(alerts)}**\n\n")
        if alerts:
            f.write("## Alertas\n")
            for a in alerts:
                f.write(f"- **{a['sku']} – {a['name']}**: {a['reason']} · "
                        f"Nuestro: {a['our_price']} · Comp: {a['competitor_price']} · {a['delta_pct']}%  \n")

    # Notificaciones (Slack / Email)
    slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if slack_url and alerts:
        lines = [f":rotating_light: *{len(alerts)} alertas de pricing* – {today}"]
        for a in alerts[:10]:
            lines.append(f"- *{a['sku']}* {a['name']}: {a['reason']} (Comp: {a['competitor_price']}, Nuestro: {a['our_price']})")
        post_to_slack(slack_url, "\n".join(lines))

    # Email opcional
    if alerts and os.getenv("SMTP_HOST") and os.getenv("EMAIL_TO"):
        body = f"Se detectaron {len(alerts)} alertas de pricing ({today}).\n\n" + \
               "\n".join([f"{a['sku']} {a['name']}: {a['reason']} (Comp: {a['competitor_price']}, Nuestro: {a['our_price']})"
                          for a in alerts])
        try:
            send_email(
                host=os.getenv("SMTP_HOST"),
                port=int(os.getenv("SMTP_PORT", "587")),
                user=os.getenv("SMTP_USER"),
                password=os.getenv("SMTP_PASS"),
                to_addr=os.getenv("EMAIL_TO"),
                subject=f"[Price Monitor] {len(alerts)} alertas – {today}",
                body=body
            )
        except Exception:
            pass

    print(f"[OK] Monitor finalizado. Rows: {len(df_today)} | Alerts: {len(alerts)}")
    print(f"Histórico: {history_path}")
    if alerts:
        print(f"Alertas:   {alerts_path}")
    print(f"Resumen:   {summary_path}")

def main():
    parser = argparse.ArgumentParser(description="Competitor price monitoring")
    parser.add_argument("--config", required=True, help="Ruta a config/targets.csv")
    parser.add_argument("--outdir", default="outputs", help="Directorio de salida")
    args = parser.parse_args()

    delta_pct = float(os.getenv("PRICE_DELTA_PCT", "10"))
    monitor(args.config, args.outdir, delta_pct)

if __name__ == "__main__":
    main()
