import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import json
import os

# —————————————————————————————————————————————
# 1. Autenticación a Google Sheets
# —————————————————————————————————————————————
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Para producción: usar variable de entorno, para desarrollo: archivo local
if os.getenv("GOOGLE_CREDENTIALS"):
    # Producción - DigitalOcean
    creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
else:
    # Desarrollo local
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

gc = gspread.authorize(creds)

# Obtener configuración de secrets o variables de entorno
if "SHEET_ID" in st.secrets:
    SHEET_ID = st.secrets["SHEET_ID"]
    N8N_WEBHOOK = st.secrets["N8N_WEBHOOK"]
    N8N_API_KEY = st.secrets["N8N_API_KEY"]
else:
    SHEET_ID = os.getenv("SHEET_ID")
    N8N_WEBHOOK = os.getenv("N8N_WEBHOOK")
    N8N_API_KEY = os.getenv("N8N_API_KEY")

# —————————————————————————————————————————————
# 2. Funciones auxiliares
# —————————————————————————————————————————————
@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_sheet_data():
    """Obtiene datos de Google Sheets con cache"""
    try:
        sheet = gc.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al obtener datos: {e}")
        return pd.DataFrame()

def send_to_n8n(username):
    """Envía username a n8n webhook"""
    try:
        payload = {
            "username": username,
            "api_key": N8N_API_KEY
        }
        response = requests.post(N8N_WEBHOOK, json=payload, timeout=30)
        return response.status_code == 200, response.text
    except requests.exceptions.Timeout:
        return False, "Timeout - El scraping puede estar en proceso"
    except Exception as e:
        return False, f"Error: {str(e)}"

# —————————————————————————————————————————————
# 3. Interfaz Streamlit
# —————————————————————————————————————————————
st.set_page_config(
    page_title="Instagram Scraper",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Instagram Profile Scraper")
st.markdown("### Scraping automatizado de perfiles de Instagram")

# —————————————————————————————————————————————
# 4. Sección de input
# —————————————————————————————————————————————
col1, col2 = st.columns([2, 1])

with col1:
    username = st.text_input(
        "Username de Instagram",
        placeholder="Ejemplo: cristiano",
        help="Ingresa solo el username, sin @ ni URL completa"
    )

with col2:
    st.markdown("<br>", unsafe_allow_html=True)  # Espaciado
    scrape_button = st.button("🚀 Iniciar Scraping", type="primary")

# —————————————————————————————————————————————
# 5. Procesamiento del scraping
# —————————————————————————————————————————————
if scrape_button and username:
    username = username.strip().replace('@', '').replace('instagram.com/', '')
    
    with st.spinner(f'Scrapeando perfil de @{username}...'):
        success, message = send_to_n8n(username)
        
        if success:
            st.success(f"✅ Scraping iniciado para @{username}")
            st.info("⏳ Los datos aparecerán en la tabla en unos momentos...")
            time.sleep(2)
            st.cache_data.clear()  # Limpiar cache para mostrar datos nuevos
        else:
            st.error(f"❌ Error en el scraping: {message}")

elif scrape_button and not username:
    st.warning("⚠️ Por favor ingresa un username")

# —————————————————————————————————————————————
# 6. Mostrar datos existentes
# —————————————————————————————————————————————
st.markdown("---")
st.subheader("📊 Datos Scrapeados")

# Botón de refresh
if st.button("🔄 Actualizar datos"):
    st.cache_data.clear()

# Cargar y mostrar datos
df = get_sheet_data()

if not df.empty:
    # Métricas rápidas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Perfiles", len(df))
    
    with col2:
        if 'followers' in df.columns:
            avg_followers = df['followers'].astype(str).str.replace(',', '').astype(float).mean()
            st.metric("Promedio Followers", f"{avg_followers:,.0f}")
    
    with col3:
        if 'following' in df.columns:
            avg_following = df['following'].astype(str).str.replace(',', '').astype(float).mean()
            st.metric("Promedio Following", f"{avg_following:,.0f}")
    
    with col4:
        if 'posts' in df.columns:
            avg_posts = df['posts'].astype(str).str.replace(',', '').astype(float).mean()
            st.metric("Promedio Posts", f"{avg_posts:,.0f}")
    
    # Tabla de datos
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )
    
    # Opción de descarga
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"instagram_data_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
else:
    st.info("📝 No hay datos disponibles. ¡Realiza tu primer scraping!")

# —————————————————————————————————————————————
# 7. Footer
# —————————————————————————————————————————————
st.markdown("---")
st.markdown("**🔧 Instagram Scraper** - Automatización con n8n + Google Sheets")