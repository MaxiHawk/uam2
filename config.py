import streamlit as st
import os

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_HABILIDADES_ID = st.secrets["DB_HABILIDADES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    
    # Opcionales
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

# --- HEADERS GLOBALES ---
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- CONFIGURACIÓN DE JUEGO ---
SESSION_TIMEOUT = 900   # 15 minutos de inactividad
API_TIMEOUT = 10        # 10 Segundos máx para esperar a Notion (NUEVO)

NOMBRES_NIVELES = { 
    1: "🧪 Aprendiz", 
    2: "🚀 Navegante", 
    3: "🎯 Caza Arterias", 
    4: "🔍 Clarividente", 
    5: "👑 AngioMaster" 
}

# --- RECURSOS (ASSETS) ---
ASSETS_LOTTIE = {
    "success_hack": "assets/animaciones/hack.json",
    "error_hack": "assets/animaciones/error.json",
    "loot_epic": "assets/animaciones/loot_epic.json",
    "loot_legendary": "assets/animaciones/loot_legendary.json"
}

SYSTEM_MESSAGES = [
    "Conectando con satélites...", "Desencriptando transmisiones...",
    "Recalibrando sensores...", "Analizando firmas biológicas...",
    "Estableciendo enlace neuronal...", "Purgando caché de memoria...",
    "Sincronizando con la Flota..."
]

# --- PALETA DE COLORES Y TEMAS ---
THEME_DEFAULT = {
    "primary": "#00e5ff", "secondary": "#7000ff", "bg_dark": "#0a0a12",
    "success": "#00e676", "warning": "#ffea00", "error": "#ff1744", "text": "#e0e0e0",
    "glow": "rgba(0, 229, 255, 0.5)", "gradient_start": "#006064", "gradient_end": "#00bcd4", "text_highlight": "#80deea"
}

# Mapa de Insignias
BADGE_MAP = {}
for i in range(1, 10): BADGE_MAP[f"Misión {i}"] = f"assets/insignias/mision_{i}.png"
for i in range(1, 8): BADGE_MAP[f"Hazaña {i}"] = f"assets/insignias/hazana_{i}.png"
for i in range(1, 4): BADGE_MAP[f"Expedición {i}"] = f"assets/insignias/expedicion_{i}.png"
DEFAULT_BADGE = "assets/insignias/default.png"

# Temas de Escuadrones (Movido desde app.py para limpiar)
SQUAD_THEMES = {
    "Default": THEME_DEFAULT,
    "Legión de los Egipcios": { "primary": "#d32f2f", "glow": "rgba(255, 215, 0, 0.5)", "gradient_start": "#8b0000", "gradient_end": "#ff5252", "text_highlight": "#ffc107" },
    "Vanguardia de Hales": { "primary": "#bf360c", "glow": "rgba(255, 87, 34, 0.5)", "gradient_start": "#3e2723", "gradient_end": "#d84315", "text_highlight": "#ffab91" },
    "Herederos de Favaloro": { "primary": "#b71c1c", "glow": "rgba(255, 82, 82, 0.5)", "gradient_start": "#7f0000", "gradient_end": "#e53935", "text_highlight": "#ff8a80" },
    "Sombra de Serbinenko": { "primary": "#ff3d00", "glow": "rgba(255, 61, 0, 0.6)", "gradient_start": "#212121", "gradient_end": "#dd2c00", "text_highlight": "#ff9e80" },
    "Forjadores de Forssmann": { "primary": "#c62828", "glow": "rgba(100, 100, 100, 0.5)", "gradient_start": "#263238", "gradient_end": "#b71c1c", "text_highlight": "#eceff1" },
    "Vanguardia de Sigwart": { "primary": "#8d6e63", "glow": "rgba(141, 110, 99, 0.5)", "gradient_start": "#3e2723", "gradient_end": "#a1887f", "text_highlight": "#d7ccc8" },
    "Guardián de Röntgen": { "primary": "#2979ff", "glow": "rgba(41, 121, 255, 0.6)", "gradient_start": "#0d47a1", "gradient_end": "#448aff", "text_highlight": "#82b1ff" },
    "Forjadores de Palmaz": { "primary": "#00b0ff", "glow": "rgba(0, 176, 255, 0.6)", "gradient_start": "#01579b", "gradient_end": "#4fc3f7", "text_highlight": "#80d8ff" },
    "Legión de Cournand": { "primary": "#1565c0", "glow": "rgba(21, 101, 192, 0.5)", "gradient_start": "#0d47a1", "gradient_end": "#42a5f5", "text_highlight": "#90caf9" },
    "Catalizadores de Bernard": { "primary": "#ffab00", "glow": "rgba(255, 171, 0, 0.5)", "gradient_start": "#ff6f00", "gradient_end": "#ffca28", "text_highlight": "#ffe082" },
    "Vanguardia de Seldinger": { "primary": "#fbc02d", "glow": "rgba(251, 192, 45, 0.5)", "gradient_start": "#f57f17", "gradient_end": "#fff176", "text_highlight": "#fff59d" },
    "Escuadra de Gruentzig": { "primary": "#ffa000", "glow": "rgba(255, 160, 0, 0.5)", "gradient_start": "#ef6c00", "gradient_end": "#ffca28", "text_highlight": "#ffe0b2" },
    "Clan de Judkins": { "primary": "#43a047", "glow": "rgba(255, 215, 0, 0.4)", "gradient_start": "#1b5e20", "gradient_end": "#66bb6a", "text_highlight": "#ffd54f" },
    "Clan de Cesalpino": { "primary": "#9c27b0", "glow": "rgba(156, 39, 176, 0.5)", "gradient_start": "#4a148c", "gradient_end": "#ba68c8", "text_highlight": "#e1bee7" },
    "Compañía de Sones": { "primary": "#7b1fa2", "glow": "rgba(255, 193, 7, 0.4)", "gradient_start": "#4a148c", "gradient_end": "#8e24aa", "text_highlight": "#ffecb3" },
    "Forjadores de Dotter": { "primary": "#f06292", "glow": "rgba(240, 98, 146, 0.6)", "gradient_start": "#880e4f", "gradient_end": "#ff80ab", "text_highlight": "#f8bbd0" },
    "Legión de Guglielmi": { "primary": "#e040fb", "glow": "rgba(224, 64, 251, 0.5)", "gradient_start": "#aa00ff", "gradient_end": "#ea80fc", "text_highlight": "#f3e5f5" },
    "Hijos de Harvey": { "primary": "#e0e0e0", "glow": "rgba(255, 255, 255, 0.4)", "gradient_start": "#424242", "gradient_end": "#bdbdbd", "text_highlight": "#f5f5f5" },
    "Vanguardia de Cribier": { "primary": "#bdbdbd", "glow": "rgba(233, 30, 99, 0.3)", "gradient_start": "#616161", "gradient_end": "#efefef", "text_highlight": "#f48fb1" },
    "Remodeladores de Moret": { "primary": "#cfd8dc", "glow": "rgba(255, 215, 0, 0.3)", "gradient_start": "#000000", "gradient_end": "#546e7a", "text_highlight": "#ffca28" }
}
