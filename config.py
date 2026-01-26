import streamlit as st

# --- GESTIÓN DE SECRETOS ---
# Intentamos cargar los secretos. Si falla, avisamos para no romper la app en silencio.
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_HABILIDADES_ID = st.secrets["DB_HABILIDADES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    
    # Bases de datos opcionales (Usamos .get para que no falle si faltan)
    DB_NOTICIAS_ID = st.secrets.get("DB_NOTICIAS_ID", None)
    DB_CODICE_ID = st.secrets.get("DB_CODICE_ID", None)
    DB_MERCADO_ID = st.secrets.get("DB_MERCADO_ID", None)
    DB_ANUNCIOS_ID = st.secrets.get("DB_ANUNCIOS_ID", None)
    DB_TRIVIA_ID = st.secrets.get("DB_TRIVIA_ID", None)
    DB_CONFIG_ID = st.secrets.get("DB_CONFIG_ID", None)
    DB_LOGS_ID = st.secrets.get("DB_LOGS_ID", None)
    DB_CODIGOS_ID = st.secrets.get("DB_CODIGOS_ID", None)
    DB_MISIONES_ID = st.secrets.get("DB_MISIONES_ID", None)
    
except KeyError as e:
    st.error(f"❌ Error Crítico: Falta el secreto {e} en .streamlit/secrets.toml")
    st.stop()

# --- HEADERS GLOBALES PARA NOTION ---
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- PALETA DE COLORES (THEME) ---
THEME = {
    "primary": "#00e5ff",    # Cyan Neon
    "secondary": "#7000ff",  # Purple Neon
    "bg_dark": "#0a0a12",    # Deep Space
    "success": "#00e676",    # Green Signal
    "warning": "#ffea00",    # Yellow Alert
    "error": "#ff1744",      # Red Critical
    "text": "#e0e0e0"        # Standard Text
}

# --- RUTA DE ARCHIVOS LOTTIE ---
ASSETS_LOTTIE = {
    "success_hack": "assets/animaciones/hack.json",
    "error_hack": "assets/animaciones/error.json",
    "loot_epic": "assets/animaciones/loot_epic.json",
    "loot_legendary": "assets/animaciones/loot_legendary.json"
}

# --- MENSAJES DE SISTEMA (Flavor Text) ---
SYSTEM_MESSAGES = [
    "Conectando con satélites...",
    "Desencriptando transmisiones...",
    "Recalibrando sensores...",
    "Analizando firmas biológicas...",
    "Estableciendo enlace neuronal...",
    "Purgando caché de memoria...",
    "Sincronizando con la Flota..."
]
