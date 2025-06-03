import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import requests
import time
import json
import os

# —————————————————————————————————————————————
# 1. Configuración de página (debe ser lo primero)
# —————————————————————————————————————————————
st.set_page_config(
    page_title="Instagram Scraper",
    page_icon="📸",
    layout="wide"
)

# —————————————————————————————————————————————
# 2. Autenticación a Google Sheets
# —————————————————————————————————————————————
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

@st.cache_resource
def initialize_gsheets():
    """Inicializa la conexión a Google Sheets"""
    try:
        if os.getenv("GOOGLE_CREDENTIALS"):
            # Producción - DigitalOcean
            creds_info = json.loads(os.getenv("GOOGLE_CREDENTIALS"))
            creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        else:
            # Desarrollo local
            if os.path.exists("credentials.json"):
                creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            else:
                return None, "Archivo credentials.json no encontrado"
        
        gc = gspread.authorize(creds)
        return gc, None
    except Exception as e:
        return None, str(e)

# Inicializar Google Sheets
gc, auth_error = initialize_gsheets()

if auth_error:
    st.error(f"❌ Error de autenticación: {auth_error}")
    st.info("💡 Verifica que las credenciales estén configuradas correctamente")
    st.stop()

# Obtener configuración
SHEET_ID = os.getenv("SHEET_ID") or st.secrets.get("SHEET_ID", "")
N8N_WEBHOOK = os.getenv("N8N_WEBHOOK") or st.secrets.get("N8N_WEBHOOK", "")
N8N_API_KEY = os.getenv("N8N_API_KEY") or st.secrets.get("N8N_API_KEY", "")

# Verificar configuración
missing_vars = []
if not SHEET_ID:
    missing_vars.append("SHEET_ID")
if not N8N_WEBHOOK:
    missing_vars.append("N8N_WEBHOOK")
if not N8N_API_KEY:
    missing_vars.append("N8N_API_KEY")

if missing_vars:
    st.error(f"❌ Variables faltantes: {', '.join(missing_vars)}")
    st.info("💡 Configura estas variables en el archivo .streamlit/secrets.toml o como variables de entorno")
    st.stop()

# —————————————————————————————————————————————
# 3. Funciones auxiliares
# —————————————————————————————————————————————
@st.cache_data(ttl=300)
def get_sheet_data():
    """Obtiene datos de Google Sheets con cache"""
    try:
        sheet = gc.open_by_key(SHEET_ID).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        
        # Limpiar datos para evitar errores de Arrow
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str)
        
        return df
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
# 4. Interfaz principal
# —————————————————————————————————————————————
def main():
    st.title("📸 Instagram Profile Scraper")
    st.markdown("### Scraping automatizado de perfiles de Instagram")

    # Sección de input
    col1, col2 = st.columns([2, 1])

    with col1:
        username = st.text_input(
            "Username de Instagram",
            placeholder="Ejemplo: cristiano",
            help="Ingresa solo el username, sin @ ni URL completa"
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        scrape_button = st.button("🚀 Iniciar Scraping", type="primary")

    # Procesamiento del scraping
    if scrape_button and username:
        username = username.strip().replace('@', '').replace('instagram.com/', '')
        
        with st.spinner(f'Scrapeando perfil de @{username}...'):
            success, message = send_to_n8n(username)
            
            if success:
                st.success(f"✅ Scraping iniciado para @{username}")
                st.info("⏳ Los datos aparecerán en la tabla en unos momentos...")
                time.sleep(2)
                st.cache_data.clear()
            else:
                st.error(f"❌ Error en el scraping: {message}")

    elif scrape_button and not username:
        st.warning("⚠️ Por favor ingresa un username")

    # Mostrar datos existentes
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
        
        # Métricas adicionales solo si las columnas existen
        numeric_cols = ['followers', 'following', 'posts']
        available_cols = [col for col in numeric_cols if col in df.columns]
        
        if len(available_cols) >= 1 and 'followers' in available_cols:
            with col2:
                try:
                    followers_data = pd.to_numeric(df['followers'].astype(str).str.replace(',', ''), errors='coerce')
                    avg_followers = followers_data.mean()
                    if not pd.isna(avg_followers):
                        st.metric("Promedio Followers", f"{avg_followers:,.0f}")
                except:
                    pass
        
        if len(available_cols) >= 2 and 'following' in available_cols:
            with col3:
                try:
                    following_data = pd.to_numeric(df['following'].astype(str).str.replace(',', ''), errors='coerce')
                    avg_following = following_data.mean()
                    if not pd.isna(avg_following):
                        st.metric("Promedio Following", f"{avg_following:,.0f}")
                except:
                    pass
        
        if len(available_cols) >= 3 and 'posts' in available_cols:
            with col4:
                try:
                    posts_data = pd.to_numeric(df['posts'].astype(str).str.replace(',', ''), errors='coerce')
                    avg_posts = posts_data.mean()
                    if not pd.isna(avg_posts):
                        st.metric("Promedio Posts", f"{avg_posts:,.0f}")
                except:
                    pass
        
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

    # Footer
    st.markdown("---")
    st.markdown("**🔧 Instagram Scraper** - Automatización con n8n + Google Sheets")

# Ejecutar la aplicación solo si se ejecuta con streamlit run
if __name__ == "__main__":
    main()