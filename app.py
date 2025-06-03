import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time

# —————————————————————————————————————————————
# 1. Autenticación a Google Sheets
# —————————————————————————————————————————————
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file(
    "credentials.json", scopes=SCOPES
)
gc = gspread.authorize(creds)
SHEET_ID    = st.secrets["SHEET_ID"]
N8N_WEBHOOK = st.secrets["N8N_WEBHOOK"]
N8N_API_KEY = st.secrets["N8N_API_KEY"]

# —————————————————————————————————————————————
# 2. Función para disparar el workflow en n8n
# —————————————————————————————————————————————
def trigger_n8n(accounts, posts):
    payload = {"accounts": accounts, "posts": posts}
    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": N8N_API_KEY
    }
    return requests.post(N8N_WEBHOOK, json=payload, headers=headers)

def check_sheets_updated(initial_count):
    """Verifica si Google Sheets se actualizó con nuevos datos"""
    try:
        ws = gc.open_by_key(SHEET_ID).sheet1
        current_count = len(ws.get_all_records())
        return current_count > initial_count
    except:
        return False

# —————————————————————————————————————————————
# 3. Interfaz Streamlit
# —————————————————————————————————————————————
st.set_page_config(page_title="Scraping inmobiliario - Cliente: De La Serna, Tomas", layout="wide")
st.title("🏠 Scraping inmobiliario - Cliente: De La Serna, Tomas")

st.sidebar.header("Parámetros de Scrapeo")
raw_accounts = st.sidebar.text_area(
    "Cuentas Instagram (una por línea)",
    placeholder="p.ej. inmobiliariaA\npropiedadesXYZ"
)
n_posts = st.sidebar.number_input("Nº de posts a scrapear", 1, 10, 10)

if st.sidebar.button("🚀 Ejecutar Scrapeo"):
    # 1) Validación de inputs
    accounts = [a.strip() for a in raw_accounts.splitlines() if a.strip()]
    if not accounts:
        st.sidebar.error("❗️ Ingresa al menos una cuenta")
    else:
        # 2) Disparo del workflow
        with st.spinner("Ejecutando escenario en n8n…"):
            resp = trigger_n8n(accounts, n_posts)

        if resp.ok:
            st.sidebar.success("✅ Scrapeo disparado con éxito")
            
            # 3) Verificar estado inicial de Google Sheets
            try:
                ws = gc.open_by_key(SHEET_ID).sheet1
                initial_count = len(ws.get_all_records())
            except:
                initial_count = 0
            
            # 4) Esperar hasta que se complete la operación
            with st.spinner("Procesando datos... Por favor espera"):
                max_wait_time = 180  # Máximo 3 minutos
                check_interval = 10  # Verificar cada 10 segundos
                elapsed_time = 0
                
                while elapsed_time < max_wait_time:
                    time.sleep(check_interval)
                    elapsed_time += check_interval
                    
                    # Verificar si se actualizó Google Sheets
                    if check_sheets_updated(initial_count):
                        break
                
            # 5) Mensaje de éxito
            if elapsed_time < max_wait_time:
                st.success("✅ **Extracción de datos exitosa, se puede visualizar en la hoja de sheets.**")
            else:
                st.warning("⚠️ **El proceso está tomando más tiempo del esperado. Verifica la hoja de sheets en unos minutos.**")
        else:
            st.sidebar.error(f"❌ Error {resp.status_code}: {resp.text}")