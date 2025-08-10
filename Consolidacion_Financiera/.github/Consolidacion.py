# scripts/finance_consolidation.py
# Consolidación financiera multi-fuente:
# - Stripe (opcional, si hay STRIPE_API_KEY)
# - Fuente JSON genérica (opcional: GENERIC_JSON_URL)
# - CSV locales (si existen en data/)
# Salidas:
#   - outputs/transactions_consolidated.csv
#   - outputs/kpi_daily.csv
#   - outputs/kpi_by_source.csv
#   - outputs/summary_YYYYMMDD.md
# Requisitos: pandas, requests, pyyaml, python-dateutil, openpyxl

import os
import io
import csv
import json
import math
import time
import argparse
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import pandas as pd
import requests
from dateutil.parser import isoparse

# --------------------
# Utilidades/Helpers
# --------------------

def env(key: str, default: str = "") -> str:
    v = os.getenv(key)
    return v if v not in (None, "") else default

def utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def daterange_default():
    end = env("END_DATE")
    start = env("START_DATE")
    if not end:
        end = utc_today_str()
    if not start:
        start = (isoparse(end).date() - timedelta(days=30)).isoformat()
    return start, end

def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)

def to_float(x):
    try:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return float("nan")
        if isinstance(x, str):
            x = x.strip().replace(",", ".")
        return float(x)
    except Exception:
        return float("nan")

# --------------------
# FX (exchangerate.host)
# --------------------

def fetch_fx_timeseries(base: str, start: str, end: str, symbols: List[str]) -> Dict[str, float]:
    """
    Devuelve dict { 'USD': 1.09, 'GBP': 0.86, ... } para la fecha 'end' (último disponible).
    Usamos exchangerate.host sin API key.
    """
    base = base.upper()
    url = f"{env('FX_API_URL','https://api.exchangerate.host')}/timeseries"
    params = {"base": base, "start_date": start, "end_date": end, "symbols": ",".join(sorted(set([s.upper() for s in symbols if s])))}
    try:
        r = requests.get(url, params=params, timeout=25)
        r.raise_for_status()
        data = r.json()
        if not data.get("rates"):
            return {}
        last_day = sorted(data["rates"].keys())[-1]
        rates = data["rates"][last_day]  # { 'USD': 1.09, ... } -> 1 BASE = rate * CURRENCY
        # OJO: exchangerate.host devuelve tasas como "1 base = X currency"
        # Para convertir MONEDA->BASE necesitamos 1 currency en base:
        inv = {}
        for ccy, rate in rates.items():
            try:
                inv[ccy.upper()] = 1.0 / float(rate) if rate else float("nan")
            except Exception:
                inv[ccy.upper()] = float("nan")
        inv[base] = 1.0
        return inv
    except Exception:
        return {base: 1.0}

# --------------------
# Stripe
# --------------------

def fetch_stripe_charges(api_key: str, start: str, end: str) -> pd.DataFrame:
    """
    Descarga cargos/refunds de Stripe entre fechas (UTC).
    Devuelve DF normalizado con columnas: date, amount, currency, fee, source, type, status, reference
    """
    if not api_key:
        return pd.DataFrame(columns=["date","amount","currency","fee","source","type","status","reference"])

    # Fechas a timestamps
    start_ts = int(datetime.fromisoformat(start).replace(tzinfo=timezone.utc).timestamp())
    end_dt = datetime.fromisoformat(end) + timedelta(days=1)  # inclusive
    end_ts = int(end_dt.replace(tzinfo=timezone.utc).timestamp())

    headers = {"Authorization": f"Bearer {api_key}"}
    rows = []

    # 1) Charges
    starting_after = None
    while True:
        params = {
            "limit": 100,
            "created[gte]": start_ts,
            "created[lte]": end_ts
        }
        if starting_after:
            params["starting_after"] = starting_after
        r = requests.get("https://api.stripe.com/v1/charges", headers=headers, params=params, timeout=25)
        if r.status_code >= 400:
            break
        data = r.json()
        for ch in data.get("data", []):
            amount = ch.get("amount", 0) / 100.0
            fee = 0.0
            # fees (si está balance_transaction)
            bt = ch.get("balance_transaction")
            if bt:
                try:
                    br = requests.get(f"https://api.stripe.com/v1/balance_transactions/{bt}", headers=headers, timeout=20)
                    if br.status_code < 400:
                        fee = br.json().get("fee", 0) / 100.0
                except Exception:
                    pass
            rows.append({
                "date": datetime.fromtimestamp(ch["created"], tz=timezone.utc).date().isoformat(),
                "amount": amount,
                "currency": str(ch.get("currency","")).upper(),
                "fee": fee,
                "source": "stripe",
                "type": "charge",
                "status": ch.get("status",""),
                "reference": ch.get("id","")
            })
        if not data.get("has_more"):
            break
        starting_after = data["data"][-1]["id"]
        time.sleep(0.3)

    # 2) Refunds
    starting_after = None
    while True:
        params = {"limit": 100, "created[gte]": start_ts, "created[lte]": end_ts}
        if starting_after:
            params["starting_after"] = starting_after
        r = requests.get("https://api.stripe.com/v1/refunds", headers=headers, params=params, timeout=25)
        if r.status_code >= 400:
            break
        data = r.json()
        for rf in data.get("data", []):
            rows.append({
                "date": datetime.fromtimestamp(rf["created"], tz=timezone.utc).date().isoformat(),
                "amount": -abs(rf.get("amount", 0)/100.0),  # negativo
                "currency": str(rf.get("currency","")).upper(),
                "fee": 0.0,
                "source": "stripe",
                "type": "refund",
                "status": rf.get("status",""),
                "reference": rf.get("id","")
            })
        if not data.get("has_more"):
            break
        starting_after = data["data"][-1]["id"]
        time.sleep(0.3)

    return pd.DataFrame(rows)

# --------------------
# Fuente JSON genérica
# --------------------

def fetch_generic_json(url: str, bearer: str, start: str, end: str) -> pd.DataFrame:
    """
    Espera una lista de objetos tipo:
      { "date": "2024-07-01", "amount": 123.45, "currency": "USD",
        "fee": 2.1, "source": "shopify", "type": "order", "status":"paid", "reference":"A-1" }
    Se filtra por rango de fechas en el cliente.
    """
    if not url:
        return pd.DataFrame(columns=["date","amount","currency","fee","source","type","status","reference"])

    headers = {"Accept": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        arr = r.json()
        if not isinstance(arr, list):
            return pd.DataFrame()
        norm = []
        for o in arr:
            d = {
                "date": str(o.get("date",""))[:10],
                "amount": to_float(o.get("amount")),
                "currency": str(o.get("currency","")).upper() or "EUR",
                "fee": to_float(o.get("fee")),
                "source": str(o.get("source","generic")),
                "type": str(o.get("type","order")),
                "status": str(o.get("status","")),
                "reference": str(o.get("reference",""))
            }
            # filtrar por fecha:
            if d["date"] and start <= d["date"] <= end:
                norm.append(d)
        return pd.DataFrame(norm)
    except Exception:
        return pd.DataFrame()

# --------------------
# CSV locales
# --------------------

def load_local_csvs(data_dir: str, start: str, end: str) -> pd.DataFrame:
    """
    Admite cualquier CSV que tenga al menos columnas:
      date, amount, currency
    Opcionales: fee, source, type, status, reference
    """
    rows = []
    if not os.path.isdir(data_dir):
        return pd.DataFrame()
    for name in os.listdir(data_dir):
        if not name.lower().endswith(".csv"):
            continue
        path = os.path.join(data_dir, name)
        try:
            df = pd.read_csv(path)
            cols = {c.lower(): c for c in df.columns}
            def pick(k): return cols.get(k, None)
            date_col = pick("date")
            amount_col = pick("amount")
            currency_col = pick("currency")
            if not date_col or not amount_col or not currency_col:
                continue
            df_out = pd.DataFrame({
                "date": pd.to_datetime(df[date_col]).dt.date.astype(str),
                "amount": df[amount_col].apply(to_float),
                "currency": df[currency_col].astype(str).str.upper()
            })
            df_out["fee"] = df[pick("fee")] if pick("fee") else 0.0
            df_out["source"] = df[pick("source")] if pick("source") else name.replace(".csv","")
            df_out["type"] = df[pick("type")] if pick("type") else "order"
            df_out["status"] = df[pick("status")] if pick("status") else ""
            df_out["reference"] = df[pick("reference")] if pick("reference") else ""

            df_out = df_out[(df_out["date"]>=start) & (df_out["date"]<=end)]
            rows.append(df_out)
        except Exception:
            continue
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()

# --------------------
# Consolidación + KPIs
# --------------------

def consolidate(transactions: pd.DataFrame, base_ccy: str, fx_rates: Dict[str,float]) -> pd.DataFrame:
    df = transactions.copy()
    if df.empty:
        return df
    df["fee"] = df.get("fee", 0.0).apply(to_float).fillna(0.0)
    df["amount_base"] = df.apply(lambda r: r["amount"] * fx_rates.get(str(r["currency"]).upper(), float("nan")), axis=1)
    df["fee_base"] = df["fee"] * df.apply(lambda r: fx_rates.get(str(r["currency"]).upper(), float("nan")), axis=1)
    df["base_currency"] = base_ccy
    return df

def compute_kpis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    # Cargos positivos (ventas), negativos = devoluciones
    grp = df.groupby(pd.Grouper(key="date", freq="D"))
    kpi = pd.DataFrame({
        "gross_sales_base": grp["amount_base"].apply(lambda s: s[s>0].sum()),
        "refunds_base": grp["amount_base"].apply(lambda s: -s[s<0].sum()),  # positivo
        "fees_base": grp["fee_base"].sum()
    }).fillna(0.0)
    kpi["net_revenue_base"] = kpi["gross_sales_base"] - kpi["refunds_base"] - kpi["fees_base"]
    kpi = kpi.reset_index().rename(columns={"date":"ds"})

    by_src = df.groupby([pd.Grouper(key="date", freq="D"), "source"]).agg(
        gross_sales_base=("amount_base", lambda s: s[s>0].sum()),
        refunds_base=("amount_base", lambda s: -s[s<0].sum()),
        fees_base=("fee_base","sum"),
    ).fillna(0.0).reset_index().rename(columns={"date":"ds"})

    by_src["net_revenue_base"] = by_src["gross_sales_base"] - by_src["refunds_base"] - by_src["fees_base"]
    return kpi, by_src

def write_summary(path_md: str, start: str, end: str, base: str, kpi: pd.DataFrame, by_src: pd.DataFrame):
    with open(path_md, "w", encoding="utf-8") as f:
        f.write(f"# Consolidación Financiera – {utc_today_str()}\n\n")
        f.write(f"- Ventana: **{start} → {end}**\n")
        f.write(f"- Moneda base: **{base}**\n\n")
        if kpi.empty:
            f.write("> No se encontraron transacciones en el rango indicado.\n")
            return
        last = kpi.tail(7).sum(numeric_only=True)  # semana reciente
        f.write("## Resumen (últimos 7 días)\n")
        f.write(f"- Ventas brutas: **{last['gross_sales_base']:.2f}**\n")
        f.write(f"- Devoluciones: **{last['refunds_base']:.2f}**\n")
        f.write(f"- Fees: **{last['fees_base']:.2f}**\n")
        f.write(f"- Ingreso neto: **{last['net_revenue_base']:.2f}**\n\n")

        top_src = by_src.groupby("source")["net_revenue_base"].sum().sort_values(ascending=False).head(5)
        if not top_src.empty:
            f.write("## Top fuentes por ingreso neto (rango completo)\n")
            for s, val in top_src.items():
                f.write(f"- **{s}**: {val:.2f}\n")

# --------------------
# Main
# --------------------

def main():
    parser = argparse.ArgumentParser(description="Financial Multi-Source Consolidation")
    parser.add_argument("--data-dir", default="data", help="Carpeta con CSV locales")
    parser.add_argument("--outdir", default="outputs", help="Carpeta de salida")
    args = parser.parse_args()

    ensure_dirs(args.outdir)

    start, end = daterange_default()
    base = env("BASE_CURRENCY", "EUR").upper()

    frames = []

    # 1) Stripe
    stripe_key = env("STRIPE_API_KEY")
    df_stripe = fetch_stripe_charges(stripe_key, start, end)
    if not df_stripe.empty:
        frames.append(df_stripe)

    # 2) JSON genérico
    gen_url = env("GENERIC_JSON_URL")
    gen_token = env("GENERIC_BEARER_TOKEN")
    df_generic = fetch_generic_json(gen_url, gen_token, start, end)
    if not df_generic.empty:
        frames.append(df_generic)

    # 3) CSV locales
    df_local = load_local_csvs(args.data_dir, start, end)
    if not df_local.empty:
        frames.append(df_local)

    if frames:
        tx = pd.concat(frames, ignore_index=True)
    else:
        tx = pd.DataFrame(columns=["date","amount","currency","fee","source","type","status","reference"])

    # Monedas a convertir
    currencies = sorted(set([c for c in tx.get("currency",[]).astype(str).str.upper().unique() if c]))
    fx = fetch_fx_timeseries(base, start, end, currencies)
    tx_cons = consolidate(tx, base, fx)

    # KPIs
    kpi_daily, kpi_by_source = compute_kpis(tx_cons)

    # Guardar
    tx_cons.to_csv(os.path.join(args.outdir, "transactions_consolidated.csv"), index=False)
    kpi_daily.to_csv(os.path.join(args.outdir, "kpi_daily.csv"), index=False)
    kpi_by_source.to_csv(os.path.join(args.outdir, "kpi_by_source.csv"), index=False)

    summary_path = os.path.join(args.outdir, f"summary_{utc_today_str().replace('-','')}.md")
    write_summary(summary_path, start, end, base, kpi_daily, kpi_by_source)

    print(f"[OK] Consolidación completada. Registros: {len(tx_cons)} | Moneda base: {base}")
    print(f" - transactions_consolidated.csv -> {os.path.join(args.outdir,'transactions_consolidated.csv')}")
    print(f" - kpi_daily.csv                -> {os.path.join(args.outdir,'kpi_daily.csv')}")
    print(f" - kpi_by_source.csv            -> {os.path.join(args.outdir,'kpi_by_source.csv')}")
    print(f" - summary.md                   -> {summary_path}")

if __name__ == "__main__":
    main()
