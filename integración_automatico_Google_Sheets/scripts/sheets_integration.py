# scripts/sheets_integration.py

import gspread
import pandas as pd
import requests
from oauth2client.service_account import ServiceAccountCredentials

# 1. Autenticación con Google Sheets
def connect_to_sheet(sheet_name, worksheet_index=0):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).get_worksheet(worksheet_index)
    return sheet

# 2. Simular API externa para scoring
def get_scoring(email):
    # Simulamos una respuesta de API externa
    response = {
        "email": email,
        "score": hash(email) % 100  # Score entre 0 y 99
    }
    return response

# 3. Leer, enriquecer y actualizar
def enrich_leads(sheet):
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    if "Score" not in df.columns:
        df["Score"] = None

    for i, row in df.iterrows():
        if pd.isna(row["Score"]) or row["Score"] == "":
            result = get_scoring(row["Email"])
            df.at[i, "Score"] = result["score"]

    # Actualizar hoja
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

if __name__ == "__main__":
    sheet = connect_to_sheet("Leads Automation Example")  # Nombre de tu hoja
    enrich_leads(sheet)
