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
X_API_KEY = os.getenv("X_API_KEY") or st.secrets.get("X_API_KEY")

# Verificar que las variables estén configuradas
if not all([SHEET_ID, N8N_WEBHOOK, X_API_KEY]):
    st.error("❌ Variables de entorno no configuradas. Verifica SHEET_ID, N8N_WEBHOOK y X_API_KEY")
    st.info("💡 En desarrollo local, usa el archivo .streamlit/secrets.toml")
    st.stop()

# —————————————————————————————————————————————
# 2. Funciones auxiliares
# —————————————————————————————————————————————
@st.cache_data(ttl=60)  # Cache por 1 minuto para detectar cambios más rápido
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
    try:
        headers = {
            'Content-Type': 'application/json',
            'X-API-KEY': X_API_KEY
        }
        
        payload = {
            "username": username,
            "posts": posts
        }
        
        response = requests.post(
            N8N_WEBHOOK, 
            json=payload, 
            headers=headers,
            timeout=300
        )
        
        return response.status_code == 200, response.text
        
    except requests.exceptions.Timeout:
        return False, "Timeout - El scraping puede estar en proceso"
    except Exception as e:
        return False, f"Error: {str(e)}"

def wait_for_new_data(initial_count, usernames_count, max_wait_time=300):
    """Espera hasta que aparezcan nuevos datos en el sheet o se agote el tiempo"""
    start_time = time.time()
    
    # Crear un placeholder para mostrar el progreso
    progress_placeholder = st.empty()
    
    while time.time() - start_time < max_wait_time:
        # Limpiar cache para obtener datos frescos
        get_sheet_data.clear()
        current_df = get_sheet_data()
        current_count = len(current_df)
        
        elapsed_time = int(time.time() - start_time)
        progress_placeholder.info(f"⏳ Esperando nuevos datos... ({elapsed_time}s / {max_wait_time}s)")
        
        # Si hay nuevos datos (aproximadamente)
        if current_count > initial_count:
            progress_placeholder.empty()
            return True, current_df
            
        time.sleep(5)  # Esperar 5 segundos antes de verificar nuevamente
    
    progress_placeholder.empty()
    return False, get_sheet_data()

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

# Inicializar estado de la sesión
if 'scraping_completed' not in st.session_state:
    st.session_state.scraping_completed = False
if 'last_scraped_data' not in st.session_state:
    st.session_state.last_scraped_data = None

# —————————————————————————————————————————————
# 4. Sección de inputs
# —————————————————————————————————————————————
col1, col2 = st.columns([3, 1])

with col1:
    # Campo para múltiples usernames (uno por línea)
    raw_usernames = st.text_area(
        "Usernames de Instagram (hasta 5, uno por línea)",
        placeholder="cristiano\nnatgeo\nnasa",
        help="Ingresa hasta 5 usernames, uno por línea, sin @ ni URL completa",
        height=120
    )

    # Campo para cantidad de posts a scrapear (máx. 10)
    num_posts = st.number_input(
        "Cantidad de posts a scrapear (máx. 10)",
        min_value=1,
        max_value=10,
        value=5,
        help="Ingresa un número entre 1 y 10"
    )

with col2:
    st.markdown("<br><br>", unsafe_allow_html=True)  # Un poco de espacio vertical
    
    # Botón de scraping
    scrape_button = st.button("🚀 Iniciar Scraping", type="primary", disabled=st.session_state.get('scraping_in_progress', False))
    
    # Botón de refresh
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Refrescar", help="Limpiar datos y empezar de nuevo"):
        st.session_state.scraping_completed = False
        st.session_state.last_scraped_data = None
        st.session_state.scraping_in_progress = False
        get_sheet_data.clear()
        st.rerun()

# —————————————————————————————————————————————
# 5. Procesamiento del scraping
# —————————————————————————————————————————————
if scrape_button:
    # Parsear y limpiar lista de usernames (separados por líneas)
    usernames_list = [
        u.strip().replace('@', '').replace('instagram.com/', '')
        for u in raw_usernames.split("\n") if u.strip()
    ]
    
    # Validaciones
    if not usernames_list:
        st.warning("⚠️ Por favor ingresa al menos un username.")
    elif len(usernames_list) > 5:
        st.warning("⚠️ Has ingresado más de 5 usernames. Reduce la lista a un máximo de 5.")
    else:
        # Marcar que el scraping está en progreso
        st.session_state.scraping_in_progress = True
        st.session_state.scraping_completed = False
        
        # Obtener conteo inicial de datos
        initial_df = get_sheet_data()
        initial_count = len(initial_df)
        
        # Ejecutar scraping
        errores = []
        with st.spinner("⏳ Enviando solicitudes a N8N..."):
            for user in usernames_list:
                success, message = send_to_n8n(user, int(num_posts))
                if not success:
                    errores.append(f"@{user}: {message}")

        # Si hubo errores en el envío
        if errores:
            st.error("❌ Ocurrieron errores durante el envío:")
            for err in errores:
                st.write(f"- {err}")
            st.session_state.scraping_in_progress = False
        else:
            st.success("✅ Solicitudes enviadas correctamente. Esperando resultados...")
            
            # Esperar a que aparezcan nuevos datos
            success, final_df = wait_for_new_data(initial_count, len(usernames_list))
            
            if success:
                st.success("🎉 ¡Scraping realizado con éxito para todos los usernames!")
                st.session_state.scraping_completed = True
                st.session_state.last_scraped_data = final_df
            else:
                st.warning("⚠️ El scraping puede estar tomando más tiempo del esperado. Los datos aparecerán cuando esté listo.")
                st.info("💡 Puedes usar el botón 'Refrescar' para verificar si llegaron nuevos datos.")
            
            st.session_state.scraping_in_progress = False

# —————————————————————————————————————————————
# 6. Mostrar datos scrapeados solo si el scraping fue exitoso
# —————————————————————————————————————————————
st.markdown("---")
st.subheader("📊 Datos Scrapeados")

# Mostrar datos y botón de descarga solo si el scraping fue completado exitosamente
if st.session_state.scraping_completed and st.session_state.last_scraped_data is not None:
    df = st.session_state.last_scraped_data
    
    if not df.empty:
        # Mostrar información sobre los datos
        st.info(f"📈 Se encontraron {len(df)} registros en total")
        
        # Botón de descarga
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"instagram_data_{time.strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        # Opcionalmente, mostrar preview de los datos
        with st.expander("👁️ Ver preview de los datos"):
            st.dataframe(df.head(10), use_container_width=True)
    else:
        st.error("❌ No se pudieron obtener los datos scrapeados")
else:
    st.info("📝 Los datos aparecerán aquí una vez que el scraping esté completo y exitoso.")

# —————————————————————————————————————————————
# 7. Footer
# —————————————————————————————————————————————
st.markdown("---")
st.markdown("**🔧 Demo Instagram Scraper** - Automatización con n8n + Google Sheets")
