import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import json
import os

# Health check endpoint
if st.query_params.get("health") == "check":
    st.write("OK")
    st.stop()

# —————————————————————————————————————————————
# 1. Autenticación a Google Sheets
# —————————————————————————————————————————————
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# Configuración de credenciales
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

# Obtener configuración - Variables de entorno o secrets locales
SHEET_ID = os.getenv("SHEET_ID") or st.secrets.get("SHEET_ID")
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK") or st.secrets.get("N8N_WEBHOOK")
N8N_API_KEY = os.getenv("N8N_API_KEY") or st.secrets.get("N8N_API_KEY")

# Verificar que las variables estén configuradas
if not all([SHEET_ID, N8N_WEBHOOK, N8N_API_KEY]):
    st.error("❌ Variables de entorno no configuradas. Verifica SHEET_ID, N8N_WEBHOOK y N8N_API_KEY")
    st.info("💡 En desarrollo local, usa el archivo .streamlit/secrets.toml")
    st.stop()

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

def send_to_n8n(username, posts):
    """Envía username y cantidad de posts a n8n webhook y retorna cuando termine."""
    
    # Intentar diferentes formatos de header
    header_formats = [
        {'X-API-KEY': N8N_API_KEY},  # Formato 1
        {'X-Api-Key': N8N_API_KEY},  # Formato 2  
        {'x-api-key': N8N_API_KEY},  # Formato 3 (lowercase)
        {'Authorization': f'Bearer {N8N_API_KEY}'},  # Formato 4
        {'Authorization': N8N_API_KEY},  # Formato 5
    ]
    
    payload = {
        "username": username,
        "posts": posts
    }
    
    for i, auth_header in enumerate(header_formats, 1):
        try:
            headers = {
                'Content-Type': 'application/json',
                **auth_header  # Agregar el header de autenticación
            }
            
            st.write(f"🔧 Intento {i} - Header: {list(auth_header.keys())[0]}")
            
            response = requests.post(
                N8N_WEBHOOK, 
                json=payload, 
                headers=headers,
                timeout=60  # Timeout más corto para pruebas
            )
            
            st.write(f"🔧 Status: {response.status_code}")
            st.write(f"🔧 Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                st.success(f"✅ ¡Éxito con formato {i}!")
                return True, response.text
            elif response.status_code != 403:
                # Si no es 403, puede ser otro tipo de error
                st.warning(f"⚠️ Código inesperado: {response.status_code}")
                
        except Exception as e:
            st.error(f"❌ Error en intento {i}: {str(e)}")
    
    return False, "Ningún formato de autenticación funcionó"

# —————————————————————————————————————————————
# 3. Configuración de la aplicación Streamlit
# —————————————————————————————————————————————
st.set_page_config(
    page_title="Demo Instagram Profile Scraper",
    page_icon="📸",
    layout="wide"
)

st.title("📸 Demo Instagram Profile Scraper")
st.markdown("### Cliente: Tomas de la Serna")

# —————————————————————————————————————————————
# 4. Sección de inputs
# —————————————————————————————————————————————
col1, col2 = st.columns([3, 1])

with col1:
    # Campo para múltiples usernames (hasta 5, separados por comas)
    raw_usernames = st.text_area(
        "Usernames de Instagram (hasta 5, separados por comas)",
        placeholder="ej: cristiano, natgeo, nasa",
        help="Ingresa hasta 5 usernames separados por coma, sin @ ni URL completa"
    )

    # Campo para cantidad de posts a scrapear (máximo 10)
    num_posts = st.number_input(
        "Cantidad de posts a scrapear (máx. 10)",
        min_value=1,
        max_value=10,
        value=5,
        help="Ingresa un número entre 1 y 10"
    )

with col2:
    st.markdown("<br><br>", unsafe_allow_html=True)  # Un poco de espacio vertical
    scrape_button = st.button("🚀 Iniciar Scraping", type="primary")

# —————————————————————————————————————————————
# 5. Procesamiento del scraping
# —————————————————————————————————————————————
if scrape_button:
    # Parsear y limpiar lista de usernames
    usernames_list = [
        u.strip().replace('@', '').replace('instagram.com/', '')
        for u in raw_usernames.split(",") if u.strip()
    ]
    # Validaciones
    if not usernames_list:
        st.warning("⚠️ Por favor ingresa al menos un username.")
    elif len(usernames_list) > 5:
        st.warning("⚠️ Has ingresado más de 5 usernames. Reduce la lista a un máximo de 5.")
    else:
        # Ejecutar scraping dentro de un spinner que durará el tiempo que tarde n8n
        errores = []
        with st.spinner("⏳ Ejecutando scraping en N8N..."):
            for user in usernames_list:
                success, message = send_to_n8n(user, int(num_posts))
                if not success:
                    errores.append(f"@{user}: {message}")

        # Mostrar resultado final
        if errores:
            st.error("❌ Ocurrieron errores durante el scraping:")
            for err in errores:
                st.write(f"- {err}")
        else:
            st.success("✅ Scraping realizado con éxito para todos los usernames.")

# —————————————————————————————————————————————
# 6. Mostrar sólo botón de descarga de CSV (sin previsualización ni refresh)
# —————————————————————————————————————————————
st.markdown("---")
st.subheader("📊 Datos Scrapeados")

df = get_sheet_data()
if not df.empty:
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name=f"instagram_data_{time.strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
else:
    st.info("📝 No hay datos disponibles para descargar todavía.")

# —————————————————————————————————————————————
# 7. Footer
# —————————————————————————————————————————————
st.markdown("---")
st.markdown("**🔧 Demo Instagram Scraper** - Automatización con n8n + Google Sheets")