import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import json
import os

# —————————————————————————————————————————————
# 0. Health check
# —————————————————————————————————————————————
if st.query_params.get("health") == "check":
    st.write("OK")
    st.stop()

# —————————————————————————————————————————————
# 1. Autenticación a Google Sheets
# —————————————————————————————————————————————
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

try:
    if os.getenv("GOOGLE_CREDENTIALS"):
        # Producción - DigitalOcean
        creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        # Desarrollo local
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"Error de autenticación: {e}")
    st.stop()

# —————————————————————————————————————————————
# 2. Variables de entorno / secrets
# —————————————————————————————————————————————
SHEET_ID   = os.getenv("SHEET_ID")   or st.secrets.get("SHEET_ID")
N8N_WEBHOOK= os.getenv("N8N_WEBHOOK")or st.secrets.get("N8N_WEBHOOK")
X_API_KEY  = os.getenv("X_API_KEY")  or st.secrets.get("X_API_KEY")

if not all([SHEET_ID, N8N_WEBHOOK, X_API_KEY]):
    st.error("❌ Variables de entorno no configuradas. Verifica SHEET_ID, N8N_WEBHOOK y X_API_KEY")
    st.info("💡 En desarrollo local, usa el archivo .streamlit/secrets.toml")
    st.stop()

# —————————————————————————————————————————————
# 3. Funciones auxiliares
# —————————————————————————————————————————————
@st.cache_data(ttl=60)
def get_sheet_data():
    try:
        sheet = gc.open_by_key(SHEET_ID).sheet1
        return pd.DataFrame(sheet.get_all_records())
    except Exception as e:
        st.error(f"Error al obtener datos: {e}")
        return pd.DataFrame()

def send_to_n8n(username, posts):
    try:
        headers = {'Content-Type': 'application/json', 'X-API-KEY': X_API_KEY}
        payload = {"username": username, "posts": posts}
        resp = requests.post(N8N_WEBHOOK, json=payload, headers=headers, timeout=300)
        return resp.status_code == 200, resp.text
    except requests.exceptions.Timeout:
        return False, "Timeout - El scraping puede estar en proceso"
    except Exception as e:
        return False, f"Error: {e}"

def wait_for_new_data(initial_count, max_wait_time=300):
    start = time.time()
    placeholder = st.empty()
    while time.time() - start < max_wait_time:
        get_sheet_data.clear()
        df = get_sheet_data()
        elapsed = int(time.time() - start)
        placeholder.info(f"⏳ Esperando nuevos datos... ({elapsed}s / {max_wait_time}s)")
        if len(df) > initial_count:
            placeholder.empty()
            return True, df
        time.sleep(5)
    placeholder.empty()
    return False, get_sheet_data()

# —————————————————————————————————————————————
# 4. Configuración de la página
# —————————————————————————————————————————————
st.set_page_config(
    page_title="Demo Instagram Profile Scraper",
    page_icon="📸",
    layout="wide"
)

# —————————————————————————————————————————————
# 5. UI: incrusta tu frontend HTML/CSS/JS desde templates/index.html
# —————————————————————————————————————————————
tpl_file = os.path.join(os.getcwd(), "templates", "index.html")
with open(tpl_file, "r", encoding="utf-8") as f:
    html = f.read()

components.html(
    html,
    height=800,
    scrolling=True
)

# —————————————————————————————————————————————
# 6. Lógica de scraping y presentación de resultados
# —————————————————————————————————————————————
# Nota: como tu HTML está en un iframe, las llamadas JS no llegarán automáticamente a Python.
# Aquí usamos un simple botón de Streamlit para disparar el scraping con los mismos inputs de siempre.
# Si tu HTML sobreescribe st.session_state o query_params, podrías leerlos aquí en lugar de inputs de Streamlit.

st.markdown("----")
st.subheader("📊 Resultado desde Streamlit")

# Botón manual por si el iframe no comunica:
if st.button("🚀 Iniciar Scraping (Streamlit)"):
    # Los valores por defecto — ajústalos o extraelos de st.session_state si tu HTML los guarda ahí
    usernames = ["cristiano", "natgeo"]  # reemplaza o haz st.session_state.get("usernames")
    num_posts = 5                         # reemplaza o haz st.session_state.get("num_posts")
    initial_df = get_sheet_data()
    errores = []
    for u in usernames:
        ok, msg = send_to_n8n(u, num_posts)
        if not ok:
            errores.append(f"@{u}: {msg}")
    if errores:
        st.error("❌ Errores durante el envío:")
        for e in errores:
            st.write(f"- {e}")
    else:
        st.success("✅ Solicitudes enviadas. Esperando resultados…")
        done, df_final = wait_for_new_data(len(initial_df))
        if done:
            st.success("🎉 Scraping completado")
            csv = df_final.to_csv(index=False)
            st.download_button("📥 Descargar CSV", csv, "data.csv", "text/csv")
            st.dataframe(df_final.head(10), use_container_width=True)
        else:
            st.warning("⚠️ Tarda más de lo esperado. Usa Refrescar para reintentar.")

# —————————————————————————————————————————————
# 7. Footer
# —————————————————————————————————————————————
st.markdown("----")
st.markdown("**🔧 Demo Instagram Scraper** – n8n + Google Sheets")
