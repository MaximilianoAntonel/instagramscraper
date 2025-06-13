import streamlit as st
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
        creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
except Exception as e:
    st.error(f"Error de autenticación: {e}")
    st.stop()

# —————————————————————————————————————————————
# 2. Variables de entorno / secrets
# —————————————————————————————————————————————
SHEET_ID    = os.getenv("SHEET_ID")    or st.secrets.get("SHEET_ID")
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK") or st.secrets.get("N8N_WEBHOOK")
X_API_KEY   = os.getenv("X_API_KEY")   or st.secrets.get("X_API_KEY")

if not all([SHEET_ID, N8N_WEBHOOK, X_API_KEY]):
    st.error("❌ Variables de entorno no configuradas. Verifica SHEET_ID, N8N_WEBHOOK y X_API_KEY")
    st.info("💡 En desarrollo local, usa .streamlit/secrets.toml")
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
        headers = {'Content-Type':'application/json','X-API-KEY':X_API_KEY}
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
# 4. Configuración de Streamlit
# —————————————————————————————————————————————
st.set_page_config(
    page_title="Demo Instagram Profile Scraper",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Demo Instagram Profile Scraper")
st.markdown("### Cliente: Tomas de la Serna")

# Inicializar estado
if 'scraping_in_progress' not in st.session_state:
    st.session_state.scraping_in_progress = False
if 'scraping_completed' not in st.session_state:
    st.session_state.scraping_completed = False

# —————————————————————————————————————————————
# 5. UI: Inputs y botones alineados
# —————————————————————————————————————————————
col1, col2 = st.columns([3, 1])

with col1:
    raw_usernames = st.text_area(
        "Usernames de Instagram (hasta 5, uno por línea)",
        placeholder="cristiano\nnatgeo\nnasa",
        height=120,
        key="raw_usernames"
    )
    num_posts = st.number_input(
        "Cantidad de posts a scrapear (máx. 10)",
        min_value=1, max_value=10, value=5
    )

with col2:
    # ——— Aquí inserto un spacer para que los botones bajen y queden al nivel del textarea ———
    st.markdown("<div style='height:2.5rem'></div>", unsafe_allow_html=True)

    scrape_button = st.button(
        "🚀 Iniciar Scraping",
        type="primary",
        disabled=st.session_state.scraping_in_progress
    )

    # refrescar limpia el textarea y el estado de scraping
    refresh = st.button("🔄 Refrescar")
    if refresh:
        st.session_state.raw_usernames = ""
        st.session_state.scraping_in_progress = False
        st.session_state.scraping_completed = False
        get_sheet_data.clear()
        st.experimental_rerun()

# —————————————————————————————————————————————
# 6. Procesamiento del scraping
# —————————————————————————————————————————————
if scrape_button:
    usernames_list = [
        u.strip().replace('@','').replace('instagram.com/','')
        for u in raw_usernames.split("\n") if u.strip()
    ]
    if not usernames_list:
        st.warning("⚠️ Ingresa al menos un username.")
    elif len(usernames_list) > 5:
        st.warning("⚠️ Máximo 5 usernames.")
    else:
        st.session_state.scraping_in_progress = True
        initial_count = len(get_sheet_data())
        errores = []
        with st.spinner("⏳ Enviando solicitudes a N8N..."):
            for u in usernames_list:
                ok, msg = send_to_n8n(u, int(num_posts))
                if not ok:
                    errores.append(f"@{u}: {msg}")
        if errores:
            st.error("❌ Errores en el envío:")
            for e in errores:
                st.write(f"- {e}")
        else:
            st.success("✅ Solicitudes enviadas. Esperando resultados…")
            done, _ = wait_for_new_data(initial_count)
            if done:
                st.session_state.scraping_completed = True
            else:
                st.warning("⚠️ Toma más tiempo de lo esperado. Refresca para reintentar.")
        st.session_state.scraping_in_progress = False

# —————————————————————————————————————————————
# 7. Confirmación final
# —————————————————————————————————————————————
if st.session_state.scraping_completed:
    st.success("🎉 ¡Scraping completado! Revisa tus datos en Google Sheets.")

# —————————————————————————————————————————————
# 8. Footer
# —————————————————————————————————————————————
st.markdown("---")
st.markdown("**🔧 Demo Instagram Scraper** – n8n + Google Sheets")
