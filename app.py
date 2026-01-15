import streamlit as st
import requests
import pandas as pd
import os
import base64
import textwrap
import time 
import random
import unicodedata
import io
from datetime import datetime
import pytz
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_HABILIDADES_ID = st.secrets["DB_HABILIDADES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    DB_NOTICIAS_ID = st.secrets.get("DB_NOTICIAS_ID", None)
    DB_CODICE_ID = st.secrets.get("DB_CODICE_ID", None)
    DB_MERCADO_ID = st.secrets.get("DB_MERCADO_ID", None)
except FileNotFoundError:
    st.error("⚠️ Error: Faltan configurar los secretos en Streamlit Cloud.")
    st.stop()

# --- CONFIGURACIÓN GLOBAL ---
headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# TIEMPO DE INACTIVIDAD (15 mins)
SESSION_TIMEOUT = 900 

st.set_page_config(page_title="Praxis Primoris", page_icon="💠", layout="centered")

# --- DICCIONARIO DE NIVELES ---
NOMBRES_NIVELES = {
    1: "🧪 Aprendiz",
    2: "🚀 Navegante",
    3: "🎯 Caza Arterias",
    4: "🔍 Clarividente",
    5: "👑 AngioMaster"
}

# --- FRASES DEL SISTEMA (EASTER EGG) ---
SYSTEM_MESSAGES = [
    "📡 Enlace neuronal estable. Latencia: 0.04ms",
    "🛡️ Escudos de deflexión al 100%.",
    "👁️ Valerius está observando tu progreso...",
    "⚠️ Anomalía detectada en el Sector 7G. Ignorando...",
    "💉 Niveles de contraste en sangre: Óptimos.",
    "💠 Sincronización con la Matriz completada.",
    "🤖 ¿Sueñan los estudiantes con ovejas eléctricas?",
    "⚡ Energía del núcleo: Estable.",
    "📂 Desencriptando archivos secretos...",
    "🍕 Se recomienda una pausa para reabastecimiento.",
    "🌟 La suerte favorece a los audaces.",
    "🚫 Acceso denegado al Área 51... por ahora.",
    "🎲 Tira los dados, el destino aguarda."
]

# --- 🎨 TEMAS DE ESCUADRÓN (20 EQUIPOS) ---
SQUAD_THEMES = {
    "Default": { "primary": "#00ff9d", "glow": "rgba(0, 255, 157, 0.5)", "gradient_start": "#004d40", "gradient_end": "#00bfa5", "text_highlight": "#69f0ae" },
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

# --- 🖼️ DICCIONARIO DE INSIGNIAS ---
BADGE_MAP = {
    "Misión 1": "assets/insignias/mision_1.png",
    "Misión 2": "assets/insignias/mision_2.png",
    "Misión 3": "assets/insignias/mision_3.png",
    "Primer Sangre": "assets/insignias/primer_sangre.png",
    "Francotirador": "assets/insignias/francotirador.png",
    "Erudito":       "assets/insignias/erudito.png",
    "Veterano":      "assets/insignias/veterano.png",
    "Hacker":        "assets/insignias/hacker.png",
    "Curador":       "assets/insignias/curador.png",
    "Velocista":     "assets/insignias/velocista.png",
    "Imparable":     "assets/insignias/imparable.png",
    "Legendario":    "assets/insignias/legendario.png"
}
DEFAULT_BADGE = "assets/insignias/default.png" 

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "show_intro" not in st.session_state: st.session_state.show_intro = False
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "login_error" not in st.session_state: st.session_state.login_error = None
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None
if "habilidades_data" not in st.session_state: st.session_state.habilidades_data = []
if "codice_data" not in st.session_state: st.session_state.codice_data = [] 
if "market_data" not in st.session_state: st.session_state.market_data = []
if "uni_actual" not in st.session_state: st.session_state.uni_actual = None
if "ano_actual" not in st.session_state: st.session_state.ano_actual = None
if "estado_uam" not in st.session_state: st.session_state.estado_uam = None
if "last_active" not in st.session_state: st.session_state.last_active = time.time()
if "last_easter_egg" not in st.session_state: st.session_state.last_easter_egg = 0

# Logout automático
if st.session_state.get("jugador") is not None:
    if time.time() - st.session_state.last_active > SESSION_TIMEOUT:
        st.session_state.jugador = None
        st.session_state.clear()
        st.rerun()
    else:
        st.session_state.last_active = time.time()

# --- DETERMINAR COLORES DEL TEMA ---
current_squad = st.session_state.squad_name
if current_squad and current_squad in SQUAD_THEMES:
    THEME = SQUAD_THEMES[current_squad]
else:
    found = False
    if current_squad:
        for key in SQUAD_THEMES:
            if key in current_squad:
                THEME = SQUAD_THEMES[key]
                found = True
                break
    if not found:
        THEME = SQUAD_THEMES["Default"]

# --- CSS DINÁMICO ---
st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Roboto:wght@300;400;700&display=swap');
        
        :root {{
            --primary-color: {THEME['primary']};
            --glow-color: {THEME['glow']};
            --grad-start: {THEME['gradient_start']};
            --grad-end: {THEME['gradient_end']};
            --text-highlight: {THEME['text_highlight']};
            --bg-dark: #050810;
            --bg-card: rgba(10, 25, 40, 0.7);
        }}

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {{
            overflow-x: hidden !important; background-color: var(--bg-dark); color: #e0f7fa;
        }}
        h1, h2, h3, h4, h5 {{ 
            font-family: 'Orbitron', sans-serif !important; letter-spacing: 1px; 
            color: #ffffff !important;
            text-shadow: 0 0 5px rgba(0,0,0,0.5) !important;
        }}
        html, body, [class*="css"] {{ font-family: 'Roboto', sans-serif; background-color: var(--bg-dark); }}
        .block-container {{ padding-top: 1rem !important; overflow-x: hidden; }}
        #MainMenu, header, footer, .stAppDeployButton {{ display: none !important; }}
        [data-testid="stDecoration"], [data-testid="stStatusWidget"] {{ display: none !important; }}
        
        [data-testid="stForm"] {{
            max-width: 700px; margin: 0 auto; border: 1px solid #1c2e3e; padding: 20px; border-radius: 15px; background: rgba(10, 20, 30, 0.5);
        }}
        .centered-container, .profile-container, .hud-grid, .badge-grid, 
        .energy-core, .rank-table, .log-card, .skill-card-container, .codex-card, .market-card {{
            max-width: 700px; margin-left: auto !important; margin-right: auto !important;
        }}

        .stButton>button {{ 
            width: 100%; border-radius: 8px; 
            background: linear-gradient(90deg, var(--grad-start), var(--grad-end)); 
            color: white; border: none; font-family: 'Orbitron'; font-weight:bold; text-transform: uppercase; letter-spacing: 1px; transition: 0.3s; 
        }}
        .stButton>button:hover {{ transform: scale(1.02); box-shadow: 0 0 15px var(--primary-color); }}
        
        div[data-testid="column"] .stButton>button {{ 
            background: rgba(0, 0, 0, 0.3); border: 1px solid var(--primary-color); color: var(--primary-color); font-size: 0.8em; 
        }}
        div[data-testid="column"] .stButton>button:hover {{ background: var(--primary-color); color: #000; }}

        .stTabs [aria-selected="true"] {{ 
            background-color: transparent !important; 
            color: var(--primary-color) !important; 
            border-radius: 0 !important;
            border-bottom: 3px solid var(--primary-color) !important; 
            font-weight: bold;
            text-shadow: 0 0 8px var(--glow-color);
        }}
        .stTabs [data-baseweb="tab-list"] {{ gap: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }}
        .stTabs [data-baseweb="tab"] {{ height: 50px; white-space: nowrap; background-color: transparent !important; border: none !important; color: #888 !important; font-family: 'Orbitron', sans-serif; font-size: 0.9em; }}

        .profile-container {{ 
            background: linear-gradient(180deg, rgba(6, 22, 38, 0.95), rgba(4, 12, 20, 0.98)); 
            border: 1px solid rgba(255, 255, 255, 0.1); 
            border-radius: 20px; padding: 20px; margin-top: 70px; margin-bottom: 30px; 
            position: relative; box-shadow: 0 10px 40px -10px var(--glow-color); 
            text-align: center;
        }}
        .profile-avatar-wrapper {{ 
            position: absolute; top: -70px; left: 50%; transform: translateX(-50%); width: 160px; height: 160px; 
            border-radius: 50%; padding: 5px; background: var(--bg-dark); 
            border: 2px solid #e0f7fa; box-shadow: 0 0 25px var(--glow-color); z-index: 10; 
        }}
        .profile-avatar {{ width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }}
        .profile-content {{ margin-top: 90px; }}
        .profile-name {{ font-family: 'Orbitron'; font-size: 2.2em; font-weight: 900; color: #fff; text-transform: uppercase; margin-bottom: 5px; text-shadow: 0 0 10px rgba(0,0,0,0.8); }}
        .profile-role {{ color: #b0bec5; font-size: 1.1em; margin-bottom: 15px; font-weight: 400; letter-spacing: 1px; }}
        .profile-role strong {{ color: var(--text-highlight); font-weight: bold; text-transform: uppercase; }}
        
        .level-badge {{
            display: inline-block; background: rgba(0, 0, 0, 0.4); border: 1px solid var(--primary-color);
            padding: 8px 25px; border-radius: 30px; font-family: 'Orbitron', sans-serif;
            font-size: 1.4em; font-weight: 700; color: var(--text-highlight);
            text-shadow: 0 0 15px var(--glow-color); margin-top: 10px; margin-bottom: 20px;
            box-shadow: 0 0 15px rgba(0,0,0,0.5);
        }}

        .level-progress-wrapper {{ width: 80%; margin: 0 auto 20px auto; }}
        .level-progress-bg {{ background: #1c2e3e; height: 10px; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); }}
        .level-progress-fill {{ height: 100%; background: #FFD700; border-radius: 5px; box-shadow: 0 0 15px #FFD700; transition: width 1s ease-in-out; }}
        .level-progress-text {{ font-size: 0.8em; color: #aaa; margin-top: 5px; letter-spacing: 1px; }}
        .level-progress-text strong {{ color: #FFD700; }}

        .hud-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 30px; }}
        .hud-card {{ background: var(--bg-card); border: 1px solid #1c2e3e; border-radius: 15px; padding: 15px; text-align: center; position: relative; overflow: hidden; }}
        .hud-icon {{ width: 40px; height: 40px; object-fit: contain; margin-bottom: 5px; opacity: 0.9; }}
        .epic-number {{ font-family: 'Orbitron'; font-size: 2.5em; font-weight: 900; line-height: 1; margin: 5px 0; text-shadow: 0 0 20px currentColor; }}
        .hud-label {{ font-size: 0.6em; text-transform: uppercase; letter-spacing: 2px; color: #8899a6; font-weight: bold; }}

        .skill-card-container {{ display: flex; align-items: stretch; min-height: 120px; background: #0a141f; border: 1px solid #1c2e3e; border-radius: 12px; margin-bottom: 15px; overflow: hidden; transition: 0.3s; margin-top: 5px; }}
        .skill-banner-col {{ width: 130px; flex-shrink: 0; background: #050810; display: flex; align-items: center; justify-content: center; border-right: 1px solid #1c2e3e; }}
        .skill-banner-img {{ width: 100%; height: 100%; object-fit: cover; }}
        .skill-content-col {{ flex-grow: 1; padding: 15px; display: flex; flex-direction: column; justify-content: center; }}
        .skill-cost-col {{ width: 100px; flex-shrink: 0; background: rgba(255, 255, 255, 0.03); border-left: 1px solid #1c2e3e; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; }}
        .skill-cost-icon {{ width: 35px; height: 35px; margin-bottom: 5px; }}
        .skill-cost-val {{ font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: #fff; line-height: 1; }}
        
        .codex-card {{ display: flex; align-items: center; justify-content: space-between; background: #0a141f; border: 1px solid #1c2e3e; border-left: 4px solid var(--primary-color); border-radius: 8px; padding: 15px; margin-bottom: 10px; transition: 0.3s; }}
        .codex-card.locked {{ border-left-color: #555; opacity: 0.6; filter: grayscale(1); }}
        .codex-info {{ flex-grow: 1; }}
        .codex-title {{ font-family: 'Orbitron'; font-size: 1.1em; color: #fff; margin-bottom: 4px; }}
        .codex-desc {{ font-size: 0.85em; color: #aaa; }}
        .codex-action {{ margin-left: 15px; }}
        .codex-icon {{ font-size: 1.5em; margin-right: 15px; }}

        .market-card {{
            display: flex; align-items: center; justify-content: space-between;
            background: linear-gradient(90deg, rgba(10,20,30,0.9), rgba(0,0,0,0.8));
            border: 1px solid #333; border-right: 4px solid #FFD700;
            border-radius: 8px; padding: 15px; margin-bottom: 15px;
        }}
        .market-icon {{ font-size: 2em; margin-right: 15px; filter: drop-shadow(0 0 5px var(--glow-color)); }}
        .market-info {{ flex-grow: 1; }}
        .market-title {{ font-family: 'Orbitron'; color: #fff; font-size: 1.1em; margin-bottom: 3px; }}
        .market-desc {{ font-size: 0.85em; color: #aaa; }}
        .market-cost {{ font-family: 'Orbitron'; font-weight: bold; font-size: 1.2em; color: #00e5ff; text-align: center; min-width: 80px; }}
        .market-cost span {{ font-size: 0.6em; color: #aaa; display: block; }}

        .rank-table {{ width: 100%; border-collapse: separate; border-spacing: 0 8px; }}
        .rank-row {{ background: linear-gradient(90deg, rgba(15,30,50,0.8), rgba(10,20,30,0.6)); }}
        .rank-cell {{ padding: 12px 15px; color: #e0f7fa; vertical-align: middle; border-top: 1px solid #1c2e3e; border-bottom: 1px solid #1c2e3e; }}
        .rank-cell-rank {{ border-left: 1px solid #1c2e3e; border-top-left-radius: 8px; border-bottom-left-radius: 8px; font-weight: bold; color: var(--primary-color); font-family: 'Orbitron'; font-size: 1.2em; width: 50px; text-align: center; }}
        .rank-cell-last {{ border-right: 1px solid #1c2e3e; border-top-right-radius: 8px; border-bottom-right-radius: 8px; width: 40%; }}
        .bar-bg {{ background: #0f1520; height: 8px; border-radius: 4px; width: 100%; margin-right: 10px; overflow: hidden; }}
        .bar-fill {{ height: 100%; background-color: #FFD700; border-radius: 4px; box-shadow: 0 0 10px #FFD700; }}
        .log-card {{ background: rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 4px solid #555; }}
        .log-header {{ display: flex; justify-content: space-between; font-size: 0.8em; color: #aaa; margin-bottom: 5px; }}
        .log-body {{ font-size: 0.95em; color: #fff; margin-bottom: 5px; }}
        .log-reply {{ background: rgba(255, 255, 255, 0.05); padding: 8px; border-radius: 4px; font-size: 0.9em; color: var(--text-highlight); margin-top: 8px; border-left: 2px solid var(--primary-color); }}

        .energy-core {{ background: linear-gradient(90deg, rgba(0, 0, 0, 0.6), rgba(255, 255, 255, 0.05)); border: 2px solid var(--primary-color); border-radius: 12px; padding: 15px 25px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; box-shadow: 0 0 20px var(--glow-color); }}
        .energy-left {{ display: flex; align-items: center; gap: 15px; }}
        .energy-icon-large {{ width: 60px; height: 60px; filter: drop-shadow(0 0 8px var(--primary-color)); }}
        .energy-label {{ font-family: 'Orbitron'; color: var(--text-highlight); font-size: 0.9em; letter-spacing: 2px; text-transform: uppercase; }}
        .energy-val {{ font-family: 'Orbitron'; font-size: 2.8em; font-weight: 900; color: #fff; text-shadow: 0 0 15px var(--primary-color); line-height: 1; }}

        .badge-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 15px; margin-top: 15px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 10px; }}
        .badge-wrapper {{ position: relative; }} 
        .badge-toggle {{ display: none; }} 
        .badge-card {{ background: var(--bg-card); border: 1px solid #333; border-radius: 8px; padding: 10px 5px; text-align: center; transition: 0.3s; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; height: 130px; cursor: pointer; user-select: none; }}
        .badge-card:hover {{ border-color: var(--primary-color); transform: translateY(-5px); box-shadow: 0 0 15px var(--glow-color); }}
        .badge-img-container {{ width: 70px; height: 70px; margin-bottom: 8px; display: flex; align-items: center; justify-content: center; }}
        .badge-img {{ width: 100%; height: 100%; object-fit: contain; filter: drop-shadow(0 0 8px rgba(255,255,255,0.3)); }}
        .badge-name {{ font-size: 0.7em; color: #e0f7fa; text-transform: uppercase; letter-spacing: 1px; line-height: 1.2; font-weight: bold; }}

        .badge-hologram-wrapper {{ position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0, 0, 0, 0.9); backdrop-filter: blur(10px); z-index: 999999; opacity: 0; visibility: hidden; transition: opacity 0.3s ease, visibility 0.3s; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
        .badge-toggle:checked ~ .badge-hologram-wrapper {{ opacity: 1; visibility: visible; pointer-events: auto; }}
        .badge-close-backdrop {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: pointer; z-index: 1000000; }}
        .holo-content {{ position: relative; z-index: 1000001; pointer-events: auto; cursor: default; }}
        .holo-img {{ width: 250px; height: 250px; object-fit: contain; filter: drop-shadow(0 0 30px var(--primary-color)); animation: holo-float 3s ease-in-out infinite; margin-bottom: 20px; }}
        .holo-title {{ font-family: 'Orbitron'; font-size: 2em; color: var(--text-highlight); text-transform: uppercase; text-shadow: 0 0 20px var(--primary-color); margin-bottom: 10px; }}
        .holo-desc {{ color: #aaa; font-size: 0.9em; letter-spacing: 2px; margin-bottom: 30px; }}
        .holo-close-btn {{ display: inline-block; padding: 10px 30px; border: 1px solid #555; border-radius: 30px; color: #fff; background: rgba(255,255,255,0.1); font-size: 0.9em; text-transform: uppercase; letter-spacing: 1px; cursor: pointer; transition: 0.3s; }}
        .holo-close-btn:hover {{ background: #ff1744; border-color: #ff1744; box-shadow: 0 0 15px #ff1744; }}
        @keyframes holo-float {{ 0%, 100% {{ transform: translateY(0) scale(1); }} 50% {{ transform: translateY(-10px) scale(1.05); }} }}

        .ticker-wrap {{ width: 100vw; position: relative; left: 50%; right: 50%; margin-left: -50vw; margin-right: -50vw; overflow: hidden; height: 35px; background-color: rgba(0, 0, 0, 0.6); border-top: 1px solid var(--primary-color); border-bottom: 1px solid var(--primary-color); display: flex; align-items: center; margin-bottom: 20px; box-sizing: border-box; }}
        .ticker {{ display: inline-block; white-space: nowrap; padding-right: 100%; box-sizing: content-box; animation: ticker-animation 80s linear infinite; }}
        .ticker-wrap:hover .ticker {{ animation-play-state: paused; }}
        .ticker-item {{ display: inline-block; padding: 0 2rem; font-size: 0.9em; color: var(--text-highlight); font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }}
        @keyframes ticker-animation {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-100%, 0, 0); }} }}

        .footer {{ text-align: center; color: #444; margin-top: 50px; padding-bottom: 20px; font-family: 'Orbitron', sans-serif; font-size: 0.7em; letter-spacing: 3px; border-top: 1px solid #1c2e3e; padding-top: 20px; width: 100%; }}

        @media (max-width: 768px) {{
            .profile-container {{ margin-top: 50px; }}
            .profile-avatar-wrapper {{ width: 130px; height: 130px; top: -65px; }}
            .profile-name {{ font-size: 1.8em; }}
            .hud-grid {{ gap: 5px; }}
            .hud-card {{ padding: 8px 2px; }}
            .hud-icon {{ width: 30px; height: 30px; margin-bottom: 2px; }}
            .epic-number {{ font-size: 1.6em; margin: 2px 0; }}
            .hud-label {{ font-size: 0.55em; letter-spacing: 1px; }}
            .skill-card-container {{ min-height: 100px; }}
            .skill-banner-col {{ width: 60px; }}
            .skill-content-col {{ padding: 10px; }}
            .skill-cost-col {{ width: 70px; padding: 5px; }}
            .skill-cost-icon {{ width: 25px; height: 25px; }}
            .skill-cost-val {{ font-size: 1.4em; }}
            .rank-cell {{ padding: 8px 5px; font-size: 0.9em; }}
            .rank-cell-rank {{ width: 30px; font-size: 1em; }}
            .energy-core {{ padding: 10px 15px; }}
            .energy-icon-large {{ width: 45px; height: 45px; }}
            .energy-val {{ font-size: 2.2em; }}
            .energy-label {{ font-size: 0.7em; }}
            .badge-grid {{ grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 10px; }}
            .badge-card {{ height: 110px; }}
            .badge-img-container {{ width: 50px; height: 50px; }}
            .badge-name {{ font-size: 0.6em; }}
            .holo-img {{ width: 200px; height: 200px; }}
            .holo-title {{ font-size: 1.5em; }}
        }}
    </style>
""", unsafe_allow_html=True)

# --- HELPERS ---
def get_img_as_base64(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def normalize_text(text):
    if not text: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def find_squad_image(squad_name):
    if not squad_name: return None
    clean_name = squad_name.lower().strip().replace(" ", "_")
    parts = squad_name.split(" ")
    keyword = parts[-1].strip()
    norm_full = normalize_text(squad_name).lower().strip().replace(" ", "_")
    norm_keyword = normalize_text(keyword)
    candidates = [
        f"assets/estandartes/{keyword.capitalize()}.png", f"assets/estandartes/{keyword.capitalize()}.jpg",
        f"assets/estandartes/{norm_keyword.capitalize()}.png", f"assets/estandartes/{norm_keyword.capitalize()}.jpg",
        f"assets/estandartes/{clean_name}.png", f"assets/estandartes/{clean_name}.jpg",
        f"assets/estandartes/{norm_full}.png", f"assets/estandartes/{norm_full}.jpg",
        f"assets/{clean_name}_team.png", f"assets/{clean_name}.png"
    ]
    for path in candidates:
        if os.path.exists(path): return path
    return None

# --- GENERADOR DE IMAGEN SOCIAL ÉPICA v6 ---
def generar_tarjeta_social(badge_name, player_name, squad_name, badge_path):
    neon_color = "#00ff9d"
    gold_color = "#FFD700"
    W, H = 1080, 1920
    bg_color = '#010204'
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    grid_color = "#080c14"
    for x in range(0, W, 60): draw.line([(x, 0), (x, H)], fill=grid_color, width=2)
    for y in range(0, H, 60): draw.line([(0, y), (W, y)], fill=grid_color, width=2)

    try:
        font_title_small = ImageFont.truetype("assets/fonts/Orbitron-Bold.ttf", 50)
        font_title_big = ImageFont.truetype("assets/fonts/Orbitron-Black.ttf", 80)
        font_badge_name = ImageFont.truetype("assets/fonts/Orbitron-Black.ttf", 115)
        font_sub = ImageFont.truetype("assets/fonts/Orbitron-Regular.ttf", 35)
        font_name = ImageFont.truetype("assets/fonts/Orbitron-Bold.ttf", 70)
        font_squad = ImageFont.truetype("assets/fonts/Orbitron-Bold.ttf", 55)
        font_footer = ImageFont.truetype("assets/fonts/Orbitron-Regular.ttf", 30)
    except:
        font_title_small = font_title_big = font_badge_name = font_sub = font_name = font_squad = font_footer = ImageFont.load_default()

    offset_frame = 45
    draw.rectangle([offset_frame, offset_frame, W-offset_frame, H-offset_frame], outline=neon_color, width=10)
    draw.rectangle([offset_frame+15, offset_frame+15, W-(offset_frame+15), H-(offset_frame+15)], outline="#0a0f1a", width=6)
    
    node_radius = 20
    corners = [(offset_frame, offset_frame), (W-offset_frame, offset_frame), (offset_frame, H-offset_frame), (W-offset_frame, H-offset_frame)]
    for cx, cy in corners:
        draw.ellipse((cx-node_radius-5, cy-node_radius-5, cx+node_radius+5, cy+node_radius+5), fill=neon_color)
        draw.ellipse((cx-node_radius, cy-node_radius, cx+node_radius, cy+node_radius), fill=bg_color, outline=neon_color, width=4)

    if os.path.exists("assets/logo.png"):
        logo = Image.open("assets/logo.png").convert("RGBA")
        logo = logo.resize((180, 180))
        logo_mask = logo.split()[-1]
        logo_glow = ImageOps.colorize(logo_mask.convert("L"), black="black", white=neon_color)
        img.paste(logo_glow, (W//2 - 90, 130), logo_mask)
        img.paste(logo, (W//2 - 90, 130), logo)

    draw.text((W//2, 340), "INSIGNIA", font=font_title_small, fill=gold_color, anchor="mm")
    draw.text((W//2, 415), "DESBLOQUEADA", font=font_title_big, fill=gold_color, anchor="mm")

    glow_size = 1000
    glow_img_wide = Image.new('RGBA', (glow_size, glow_size), (0,0,0,0))
    glow_draw_wide = ImageDraw.Draw(glow_img_wide)
    nc_rgb = tuple(int(neon_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    glow_draw_wide.ellipse((50, 50, glow_size-50, glow_size-50), fill=nc_rgb + (50,))
    glow_img_wide = glow_img_wide.filter(ImageFilter.GaussianBlur(radius=90))
    
    core_size = 600
    glow_img_core = Image.new('RGBA', (core_size, core_size), (0,0,0,0))
    glow_draw_core = ImageDraw.Draw(glow_img_core)
    glow_draw_core.ellipse((20, 20, core_size-20, core_size-20), fill=nc_rgb + (120,))
    glow_img_core = glow_img_core.filter(ImageFilter.GaussianBlur(radius=40))

    img.paste(glow_img_wide, (W//2 - glow_size//2, H//2 - glow_size//2 - 50), glow_img_wide)
    img.paste(glow_img_core, (W//2 - core_size//2, H//2 - core_size//2 - 50), glow_img_core)

    badge_y_center = H//2 - 50
    if os.path.exists(badge_path):
        badge = Image.open(badge_path).convert("RGBA")
        badge = badge.resize((700, 700))
        img.paste(badge, (W//2 - 350, badge_y_center - 350), badge)
    else:
        draw.text((W//2, badge_y_center), "🏅", font=font_badge_name, fill="white", anchor="mm")

    draw.text((W//2, badge_y_center + 450), badge_name.upper(), font=font_badge_name, fill=gold_color, anchor="mm")
    
    base_y_info = badge_y_center + 600
    draw.text((W//2, base_y_info), "ASPIRANTE:", font=font_sub, fill="#888888", anchor="mm")
    draw.text((W//2, base_y_info + 70), player_name.upper(), font=font_name, fill="white", anchor="mm")
    draw.text((W//2, base_y_info + 150), squad_name.upper(), font=font_squad, fill=gold_color, anchor="mm")
    draw.text((W//2, H - 100), "PRAXIS PRIMORIS SYSTEM // FINAL TRANSMISSION", font=font_footer, fill="#444", anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

# --- FUNCIONES LÓGICAS ---
def calcular_nivel_usuario(mp):
    if mp <= 50: return 1
    elif mp <= 150: return 2
    elif mp <= 300: return 3
    elif mp <= 500: return 4
    else: return 5

def calcular_progreso_nivel(mp):
    thresholds = {1: 50, 2: 150, 3: 300, 4: 500}
    nivel_actual = calcular_nivel_usuario(mp)
    if nivel_actual >= 5: return 1, 1, 100, 0, True
    techo = thresholds[nivel_actual]
    base = thresholds[nivel_actual - 1] + 1 if nivel_actual > 1 else 0
    progreso_actual = mp - base
    if progreso_actual < 0: progreso_actual = 0
    total_nivel = techo - base + 1
    if nivel_actual == 1: total_nivel = 51
    pct = (progreso_actual / total_nivel) * 100
    if pct > 100: pct = 100
    faltantes = (techo + 1) - mp
    return progreso_actual, total_nivel, pct, faltantes, False

def cargar_habilidades_rol(rol_jugador):
    if not rol_jugador: return []
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    payload = {"filter": {"property": "Rol", "select": {"equals": rol_jugador}}, "sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]}
    try:
        res = requests.post(url, headers=headers, json=payload)
        habilidades = []
        if res.status_code == 200:
            for item in res.json()["results"]:
                props = item["properties"]
                try:
                    nombre_list = props.get("Habilidad", {}).get("title", [])
                    nombre = "".join([t.get("plain_text", "") for t in nombre_list]) if nombre_list else "Habilidad Sin Nombre"
                    costo = 0
                    if "Costo AP" in props: costo = props["Costo AP"]["number"]
                    elif "Costo" in props: costo = props["Costo"]["number"]
                    elif "Coste" in props: costo = props["Coste"]["number"]
                    nivel_req = props["Nivel Requerido"]["number"]
                    desc_obj = props.get("Descripcion", {}).get("rich_text", [])
                    descripcion = desc_obj[0]["text"]["content"] if desc_obj else "Sin descripción"
                    icon_url = None
                    if "Icono" in props:
                        files = props["Icono"].get("files", [])
                        if files: icon_url = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
                    habilidades.append({"id": item["id"], "nombre": nombre, "costo": costo, "nivel_req": nivel_req, "descripcion": descripcion, "icon_url": icon_url})
                except Exception as e: pass
        return habilidades
    except: return []

def cargar_codice():
    if not DB_CODICE_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_CODICE_ID}/query"
    payload = {"sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]}
    try:
        res = requests.post(url, headers=headers, json=payload)
        items = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                props = r["properties"]
                try:
                    nom_list = props.get("Nombre", {}).get("title", [])
                    nombre = nom_list[0]["text"]["content"] if nom_list else "Recurso Sin Nombre"
                    nivel = props.get("Nivel Requerido", {}).get("number", 1) or 1
                    desc_list = props.get("Descripcion", {}).get("rich_text", [])
                    desc = desc_list[0]["text"]["content"] if desc_list else ""
                    tipo_obj = props.get("Tipo", {}).get("select")
                    tipo = tipo_obj["name"] if tipo_obj else "Archivo"
                    url_recurso = "#"
                    if "Enlace" in props and props["Enlace"]["url"]: url_recurso = props["Enlace"]["url"]
                    elif "Archivo" in props:
                        files = props["Archivo"].get("files", [])
                        if files: url_recurso = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
                    items.append({"nombre": nombre, "nivel": nivel, "descripcion": desc, "tipo": tipo, "url": url_recurso})
                except: pass
        return items
    except: return []

def cargar_mercado():
    if not DB_MERCADO_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MERCADO_ID}/query"
    payload = {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "sorts": [{"property": "Costo", "direction": "ascending"}]}
    try:
        res = requests.post(url, headers=headers, json=payload)
        items = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                props = r["properties"]
                try:
                    nom_list = props.get("Nombre", {}).get("title", [])
                    nombre = nom_list[0]["text"]["content"] if nom_list else "Item"
                    costo = props.get("Costo", {}).get("number", 0) or 0
                    desc_list = props.get("Descripcion", {}).get("rich_text", [])
                    desc = desc_list[0]["text"]["content"] if desc_list else ""
                    icon_list = props.get("Icono", {}).get("rich_text", [])
                    icon = icon_list[0]["text"]["content"] if icon_list else "📦"
                    items.append({"id": r["id"], "nombre": nombre, "costo": costo, "desc": desc, "icon": icon})
                except: pass
        return items
    except: return []

def enviar_solicitud(tipo, titulo_msg, cuerpo_msg, jugador_nombre):
    url = "https://api.notion.com/v1/pages"
    if tipo == "HABILIDAD":
        texto_final = f"{titulo_msg} | Costo: {cuerpo_msg}"
        tipo_select = "Poder"
    elif tipo == "COMPRA":
        texto_final = f"SOLICITUD DE COMPRA: {titulo_msg} | Costo: {cuerpo_msg} AP"
        tipo_select = "Mensaje"
    else:
        texto_final = f"{titulo_msg} - {cuerpo_msg}"
        tipo_select = "Mensaje"
    uni = st.session_state.uni_actual if st.session_state.uni_actual else "Sin Asignar"
    ano = st.session_state.ano_actual if st.session_state.ano_actual else "Sin Año"
    nuevo_mensaje = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Remitente": {"title": [{"text": {"content": jugador_nombre}}]}, 
            "Mensaje": {"rich_text": [{"text": {"content": texto_final}}]},
            "Procesado": {"checkbox": False},
            "Tipo": {"select": {"name": tipo_select}},
            "Status": {"select": {"name": "Pendiente"}}, 
            "Universidad": {"select": {"name": uni}},
            "Año": {"select": {"name": ano}}
        }
    }
    res = requests.post(url, headers=headers, json=nuevo_mensaje)
    return res.status_code == 200

def obtener_mis_solicitudes(jugador_nombre):
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {"filter": {"property": "Remitente", "title": {"equals": jugador_nombre}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}], "page_size": 15}
    res = requests.post(url, headers=headers, json=payload)
    historial = []
    if res.status_code == 200:
        for r in res.json()["results"]:
            props = r["properties"]
            try:
                msg_list = props.get("Mensaje", {}).get("rich_text", [])
                mensaje = msg_list[0]["text"]["content"] if msg_list else "Sin contenido"
                status_obj = props.get("Status", {}).get("select")
                status = status_obj["name"] if status_obj else "Pendiente"
                obs_list = props.get("Observaciones", {}).get("rich_text", [])
                obs = obs_list[0]["text"]["content"] if obs_list else None
                created = r["created_time"]
                historial.append({"mensaje": mensaje, "status": status, "obs": obs, "fecha": created})
            except: pass
    return historial

def obtener_puntaje_equipo_filtrado(nombre_escuadron, uni, ano):
    if not nombre_escuadron or not uni or not ano: return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"and": [{"property": "Nombre Escuadrón", "rich_text": {"equals": nombre_escuadron}}, {"property": "Universidad", "select": {"equals": uni}}, {"property": "Año", "select": {"equals": ano}}]}}
    try:
        res = requests.post(url, headers=headers, json=payload)
        total_mp = 0
        if res.status_code == 200:
            for m in res.json()["results"]:
                try: val = m["properties"]["MP"]["number"]; total_mp += val if val else 0
                except: pass
        return total_mp
    except: return 0

def cargar_ranking_filtrado(uni, ano):
    if not uni or not ano: return pd.DataFrame()
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"and": [{"property": "Universidad", "select": {"equals": uni}}, {"property": "Año", "select": {"equals": ano}}]}}
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            lista = []
            for p in res.json()["results"]:
                props = p["properties"]
                try:
                    nombre = props["Jugador"]["title"][0]["text"]["content"]
                    mp = props["MP"]["number"] or 0
                    esc_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                    escuadron = esc_obj[0]["text"]["content"] if esc_obj else "Sin Escuadrón"
                    lista.append({"Aspirante": nombre, "Escuadrón": escuadron, "MasterPoints": mp})
                except: pass
            df = pd.DataFrame(lista)
            if not df.empty: return df.sort_values(by="MasterPoints", ascending=False).reset_index(drop=True)
    except: pass
    return pd.DataFrame()

def actualizar_datos_sesion():
    if "nombre" in st.session_state and st.session_state.nombre:
        url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
        payload = {"filter": {"property": "Jugador", "title": {"equals": st.session_state.nombre}}}
        try:
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()
                if len(data["results"]) > 0:
                    props = data["results"][0]["properties"]
                    st.session_state.jugador = props
                    st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                    try:
                        rol_data = props.get("Rol", {}).get("select")
                        rol_usuario = rol_data["name"] if rol_data else None
                    except: rol_usuario = None
                    if rol_usuario: st.session_state.habilidades_data = cargar_habilidades_rol(rol_usuario)
                    st.session_state.codice_data = cargar_codice()
                    st.session_state.market_data = cargar_mercado()
                    st.rerun()
        except: pass

@st.cache_data(ttl=600)
def obtener_noticias():
    noticias = ["📡 Transmisión entrante desde Sector UAM-01...", "⚠️ Tormentas de iones detectadas...", "💡 Consejo: Revisa tus Habilidades...", "🏆 El ranking se actualiza en tiempo real...", "🔐 Seguridad de la red Praxis: Estable."]
    if DB_NOTICIAS_ID:
        try:
            url = f"https://api.notion.com/v1/databases/{DB_NOTICIAS_ID}/query"
            payload = {"filter": {"property": "Activa", "checkbox": {"equals": True}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}]}
            res = requests.post(url, headers=headers, json=payload)
            if res.status_code == 200:
                data = res.json()["results"]
                nn = []
                for n in data:
                    try: 
                        t = n["properties"]["Mensaje"]["title"][0]["text"]["content"]
                        nn.append(f"💠 {t}")
                    except: pass
                if nn: noticias = nn
        except: pass
    return "   |   ".join(noticias)

def validar_login():
    usuario = st.session_state.input_user.strip()
    clave = st.session_state.input_pass.strip()
    if not usuario or not clave:
        st.session_state.login_error = "⚠️ Ingresa usuario y contraseña."
        return
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Jugador", "title": {"equals": usuario}}}
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            if len(data["results"]) > 0:
                props = data["results"][0]["properties"]
                try:
                    c_real = props.get("Clave", {}).get("rich_text", [])[0]["text"]["content"]
                    if clave == c_real:
                        st.session_state.jugador = props
                        st.session_state.nombre = usuario
                        st.session_state.login_error = None
                        st.session_state.show_intro = True
                        try:
                            uni_data = props.get("Universidad", {}).get("select")
                            st.session_state.uni_actual = uni_data["name"] if uni_data else None
                            ano_data = props.get("Año", {}).get("select")
                            st.session_state.ano_actual = ano_data["name"] if ano_data else None
                            estado_data = props.get("Estado UAM", {}).get("select")
                            st.session_state.estado_uam = estado_data["name"] if estado_data else "Desconocido"
                        except: st.session_state.uni_actual = None; st.session_state.ano_actual = None; st.session_state.estado_uam = "Desconocido"
                        
                        sq_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                        sq_name = sq_obj[0]["text"]["content"] if sq_obj else "Sin Escuadrón"
                        st.session_state.squad_name = sq_name
                        st.session_state.team_stats = obtener_puntaje_equipo_filtrado(sq_name, st.session_state.uni_actual, st.session_state.ano_actual)
                        st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                        
                        rol_data = props.get("Rol", {}).get("select")
                        rol_usuario = rol_data["name"] if rol_data else None
                        if rol_usuario: st.session_state.habilidades_data = cargar_habilidades_rol(rol_usuario)
                        st.session_state.codice_data = cargar_codice()
                        st.session_state.market_data = cargar_mercado()
                    else: st.session_state.login_error = "❌ CLAVE INCORRECTA"
                except: st.session_state.login_error = "Error Credenciales"
            else: st.session_state.login_error = "❌ USUARIO NO ENCONTRADO"
        else: st.session_state.login_error = "⚠️ Error de conexión"
    except Exception as e: st.session_state.login_error = f"Error técnico: {e}"

def cerrar_sesion():
    st.session_state.clear()
    st.rerun()

def play_intro_sequence():
    placeholder = st.empty()
    intro_html = """
    <div class="intro-overlay">
        <div class="scanline"></div>
        <div class="core-loader"><div class="core-text">🔒</div></div>
        <div class="status-text">CONECTANDO...</div>
        <div class="bar-container"><div class="bar-fill" id="loading-bar"></div></div>
        <script>
            let bar = document.getElementById('loading-bar');
            let width = 0;
            let interval = setInterval(function() {
                if (width >= 100) { clearInterval(interval); }
                else { width++; bar.style.width = width + '%'; }
            }, 30);
        </script>
    </div>
    """
    placeholder.markdown(intro_html, unsafe_allow_html=True)
    time.sleep(3.5)
    placeholder.empty()

# ================= UI PRINCIPAL =================

# 1. CONTENEDOR MAESTRO (Evita el "fantasma")
main_placeholder = st.empty()

if not st.session_state.jugador:
    # --- PANTALLA LOGIN ---
    with main_placeholder.container():
        if os.path.exists("assets/cover.png"): st.image("assets/cover.png", use_container_width=True)
        with st.container():
            c_l, c_r = st.columns([1.2, 3.8])
            with c_l:
                if os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=110)
                else: st.markdown("🛡️")
            with c_r:
                st.markdown("<h3 style='margin-bottom:0;'>PRAXIS PRIMORIS</h3>", unsafe_allow_html=True)
                st.caption("PLATAFORMA COMPUTADORA CENTRAL")
            st.markdown("<br>", unsafe_allow_html=True)
            with st.form("login_form"):
                st.markdown("##### 🔐 IDENTIFICACIÓN REQUERIDA")
                st.text_input("Nickname (Usuario):", placeholder="Ingresa tu codename...", key="input_user")
                st.text_input("Password:", type="password", key="input_pass")
                st.form_submit_button("INICIAR ENLACE NEURAL", on_click=validar_login)
            
            with st.expander("🆘 ¿Problemas de Acceso?"):
                st.caption("Si olvidaste tu clave, solicita un reinicio al comando.")
                with st.form("reset_form", clear_on_submit=True):
                    reset_user = st.text_input("Ingresa tu Usuario (Aspirante):")
                    if st.form_submit_button("SOLICITAR REINICIO DE CLAVE"):
                        if reset_user:
                            with st.spinner("Enviando señal de auxilio..."):
                                time.sleep(1)
                                ok = enviar_solicitud("MENSAJE", "SOLICITUD DE RESET", f"El usuario {reset_user} solicita cambio de clave.", reset_user)
                                if ok: st.success("✅ Solicitud enviada.")
                                else: st.error("Error de conexión.")
                        else: st.warning("Ingresa tu nombre.")
        if st.session_state.login_error: st.error(st.session_state.login_error)

else:
    # --- LOGICA INTRO PRIORITARIA (SOLUCIÓN PANTALLA VERDE) ---
    if st.session_state.show_intro:
        main_placeholder.empty()
        play_intro_sequence()
        st.session_state.show_intro = False
        st.rerun()

    # --- DASHBOARD ---
    main_placeholder.empty() 

    news_text = obtener_noticias()
    st.markdown(f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{news_text}</div></div></div>""", unsafe_allow_html=True)

    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Ubicación Desconocida"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "Ciclo ?"
    estado_label = st.session_state.estado_uam if st.session_state.estado_uam else "Desconocido"
    
    # --- MODO ALUMNI / ESPECTADOR ---
    is_alumni = (estado_label == "Finalizado")

    status_color = "#00e5ff"
    if is_alumni: status_color = "#ff4b4b"
    elif estado_label == "Sin empezar": status_color = "#FFD700"

    c_head1, c_head2 = st.columns([1.2, 4.8])
    with c_head1: 
        if os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=100)
    with c_head2:
        st.markdown(f"<h2 style='margin:0; font-size:1.8em; line-height:1.2; text-shadow: 0 0 10px {THEME['glow']};'>Hola, {st.session_state.nombre}</h2>", unsafe_allow_html=True)
        header_html = textwrap.dedent(f"""
            <div style="margin-top: 10px; background: rgba(0, 20, 40, 0.5); border-left: 3px solid {THEME['primary']}; padding: 10px; border-radius: 0 10px 10px 0;">
                <div style="font-family: 'Orbitron', sans-serif; color: {THEME['text_highlight']}; font-size: 0.8em; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 0 0 5px {THEME['glow']};">🌌 MULTIVERSO DETECTADO</div>
                <div style="font-family: 'Orbitron', sans-serif; color: #e0f7fa; font-size: 1.3em; font-weight: bold; text-shadow: 0 0 15px {THEME['glow']}; line-height: 1.1; margin-bottom: 8px;">{uni_label.upper()}</div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-family: 'Orbitron', sans-serif; color: #FFD700; font-size: 1em; font-weight: bold; text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);">⚡ BATALLA {ano_label}</span>
                    <span style="border: 1px solid {status_color}; background-color: {status_color}20; padding: 2px 8px; border-radius: 4px; color: {status_color}; font-size: 0.7em; font-weight: bold; letter-spacing: 1px;">{estado_label.upper()}</span>
                </div>
            </div>
        """).replace('\n', '')
        st.markdown(header_html, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    b64_ap = get_img_as_base64("assets/icon_ap.png")

    tab_perfil, tab_ranking, tab_habilidades, tab_codice, tab_mercado, tab_comms = st.tabs(["👤 PERFIL", "🏆 RANKING", "⚡ HABILIDADES", "📜 CÓDICE", "🛒 MERCADO", "📡 COMUNICACIONES"])
    
    with tab_perfil:
        avatar_url = None
        try:
            f_list = p.get("Avatar", {}).get("files", [])
            if f_list: avatar_url = f_list[0].get("file", {}).get("url") or f_list[0].get("external", {}).get("url")
        except: pass
        try: rol = p.get("Rol", {}).get("select")["name"]
        except: rol = "Sin Rol"
        skuad = st.session_state.squad_name
        img_path = find_squad_image(skuad)
        b64_badge = get_img_as_base64(img_path) if img_path else ""
        try: vp = int(p.get("VP", {}).get("number", 1))
        except: vp = 0
        
        prog_act, prog_total, prog_pct, faltantes, is_max = calcular_progreso_nivel(mp)
        if is_max:
            progress_html = f"""<div class="level-progress-wrapper"><div class="level-progress-bg"><div class="level-progress-fill" style="width: 100%; background: #FFD700; box-shadow: 0 0 15px #FFD700;"></div></div><div class="level-progress-text" style="color: #FFD700;"><strong>¡NIVEL MÁXIMO ALCANZADO!</strong></div></div>"""
        else:
            progress_html = f"""<div class="level-progress-wrapper"><div class="level-progress-bg"><div class="level-progress-fill" style="width: {prog_pct}%;"></div></div><div class="level-progress-text">Faltan <strong>{faltantes} MP</strong> para el siguiente rango</div></div>"""

        squad_html = ""
        if b64_badge:
            squad_html = f"""<div style="margin-top:25px; border-top:1px solid #1c2e3e; padding-top:20px;"><div style="color:#FFD700; font-size:0.7em; letter-spacing:2px; font-weight:bold; margin-bottom:10px; font-family:'Orbitron';">PERTENECIENTE AL ESCUADRÓN</div><img src="data:image/png;base64,{b64_badge}" style="width:130px; filter:drop-shadow(0 0 15px rgba(0,0,0,0.6));"><div style="color:{THEME['text_highlight']}; font-size:1.2em; letter-spacing:3px; font-weight:bold; margin-top:10px; font-family:'Orbitron';">{skuad.upper()}</div></div>"""
        
        avatar_div = f'<img src="{avatar_url}" class="profile-avatar">' if avatar_url else '<div style="font-size:80px; line-height:140px;">👤</div>'
        profile_html = f"""<div class="profile-container"><div class="profile-avatar-wrapper">{avatar_div}</div><div class="profile-content"><div class="profile-name">{st.session_state.nombre}</div><div class="profile-role">Perteneciente a la orden de los <strong>{rol}</strong></div><div class="level-badge">NIVEL {nivel_num}: {nombre_rango.upper()}</div>{progress_html}{squad_html}</div></div>""".replace('\n', '')
        st.markdown(profile_html, unsafe_allow_html=True)
        
        c_egg1, c_egg2, c_egg3 = st.columns([1.5, 1, 1.5]) 
        with c_egg2:
            if st.button("💠 STATUS DEL SISTEMA", use_container_width=True):
                now = time.time()
                if now - st.session_state.last_easter_egg > 60:
                    st.session_state.last_easter_egg = now
                    msg = random.choice(SYSTEM_MESSAGES)
                    st.toast(msg, icon="🤖")
                    if random.random() < 0.1:
                        st.balloons()
                        enviar_solicitud("SISTEMA", "EASTER EGG ACTIVADO", f"El usuario {st.session_state.nombre} encontró el secreto.", "Sistema")
                else: st.toast("⚠️ Sistemas de enfriamiento activos. Espera...", icon="❄️")
        
        b64_mp = get_img_as_base64("assets/icon_mp.png")
        b64_vp = get_img_as_base64("assets/icon_vp.png")
        hud_html = textwrap.dedent(f"""<div class="hud-grid"><div class="hud-card" style="border-bottom: 3px solid #FFD700;"><img src="data:image/png;base64,{b64_mp}" class="hud-icon"><div class="epic-number" style="color:#FFD700;">{mp}</div><div class="hud-label">MasterPoints</div></div><div class="hud-card" style="border-bottom: 3px solid #00e5ff;"><img src="data:image/png;base64,{b64_ap}" class="hud-icon"><div class="epic-number" style="color:#00e5ff;">{ap}</div><div class="hud-label">AngioPoints</div></div><div class="hud-card" style="border-bottom: 3px solid #ff4b4b;"><img src="data:image/png;base64,{b64_vp}" class="hud-icon"><div class="epic-number" style="color:#ff4b4b;">{vp}%</div><div class="hud-label">VitaPoints</div></div></div>""").replace('\n', '')
        st.markdown(hud_html, unsafe_allow_html=True)
        
        st.markdown("### 🏅 SALÓN DE LA FAMA")
        try:
            insignias_data = p.get("Insignias", {}).get("multi_select", [])
            mis_insignias = [t["name"] for t in insignias_data]
        except: mis_insignias = []
        if not mis_insignias: st.caption("Aún no tienes insignias en tu historial. ¡Sigue completando misiones!")
        else:
            badge_html = '<div class="badge-grid">'
            for i, badge_name in enumerate(mis_insignias):
                modal_id = f"badge-modal-{i}"
                img_path = BADGE_MAP.get(badge_name, DEFAULT_BADGE)
                if os.path.exists(img_path):
                    b64_badge = get_img_as_base64(img_path)
                    content_html = f'<img src="data:image/png;base64,{b64_badge}" class="badge-img">'
                    holo_html = f'<img src="data:image/png;base64,{b64_badge}" class="holo-img">'
                else:
                    content_html = '<div style="font-size:40px;">🏅</div>'
                    holo_html = '<div style="font-size:100px;">🏅</div>'
                badge_html += f'<div class="badge-wrapper"><input type="checkbox" id="{modal_id}" class="badge-toggle"><label for="{modal_id}" class="badge-card"><div class="badge-img-container">{content_html}</div><div class="badge-name">{badge_name}</div></label><div class="badge-hologram-wrapper"><label for="{modal_id}" class="badge-close-backdrop"></label><div class="holo-content">{holo_html}<div class="holo-title">{badge_name}</div><div class="holo-desc">INSIGNIA DESBLOQUEADA</div><label for="{modal_id}" class="holo-close-btn">CERRAR</label></div></div></div>'
            badge_html += '</div>'
            st.markdown(badge_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        if mis_insignias:
            with st.expander("📲 CENTRO DE HOLO-TRANSMISIÓN (COMPARTIR)"):
                st.caption("Genera una tarjeta oficial de tus logros para tus redes.")
                selected_badge = st.selectbox("Selecciona insignia:", mis_insignias)
                if selected_badge:
                    badge_path = BADGE_MAP.get(selected_badge, DEFAULT_BADGE)
                    if st.button("GENERAR TARJETA"):
                        with st.spinner("Renderizando holograma..."):
                            current_squad_name = st.session_state.squad_name if st.session_state.squad_name else "Sin Escuadrón"
                            img_buffer = generar_tarjeta_social(selected_badge, st.session_state.nombre, current_squad_name, badge_path)
                            st.image(img_buffer, caption="Vista Previa", width=300)
                            st.download_button(label="⬇️ DESCARGAR IMAGEN", data=img_buffer, file_name=f"Praxis_Logro_{selected_badge}.png", mime="image/png")

        with st.expander("📘 MANUAL DE CAMPO: REGLAS DE ENFRENTAMIENTO"):
            st.markdown("""
            **Bienvenido a la Red Praxis, Aspirante.**
            Aquí se forjan las leyendas de la orden de los AngioMasters. Para sobrevivir y ascender, debes dominar los tres recursos vitales:
            
            #### 1. 🟡 MasterPoints (MP) - Tu Rango
            * **¿Qué son?** Representan tu experiencia y conocimiento técnico acumulado.
            * **¿Cómo se ganan?** Ganando Misiones, Hazañas y/o Expediciones, participación destacada entre otros.
            * **¿Para qué sirven?** Determinan tu **Nivel de Autorización** (1 a 5) y tu posición en el Ranking. ¡Los MP nunca se gastan, solo se acumulan! (a menos que cometas una falta grave)
            
            #### 2. 🔵 AngioPoints (AP) - Tu Moneda
            * **¿Qué son?** Créditos intercambiables por habilidades/poderes y en el mercado negro.
            * **¿Cómo se ganan?** Ganando Misiones, Hazañas y/o Expediciones, Misiones secundarias, tareas voluntarias, y encontrar "Easter Eggs".
            * **¿Para qué sirven?** Para comprar ventajas tácticas (tiempo extra, pistas) o desbloquear habilidades especiales. ¡Cuidado, estos sí se gastan!
            
            #### 3. 🔴 VitaPoints (VP) - Tu Supervivencia
            * **¿Qué son?** Tu salud académica. Empiezas con 100%.
            * **¿Cómo se pierden?** Errores graves, inasistencias injustificadas, retrasos.
            * **¿Qué pasa si llegan a 0?** Deberás realizar tareas, trabajos, etc., para poder revivir nuevamente. ¡Mantenlos altos!
            """)

    with tab_ranking:
        st.markdown(f"### ⚔️ TOP ASPIRANTES")
        df = st.session_state.ranking_data
        if df is not None and not df.empty:
            max_mp = int(df["MasterPoints"].max()) if df["MasterPoints"].max() > 0 else 1
            table_rows = ""
            for i, (index, row) in enumerate(df.head(10).iterrows()):
                rank = i + 1
                name = row["Aspirante"]
                squad = row["Escuadrón"]
                points = row["MasterPoints"]
                pct = (points / max_mp) * 100
                table_rows += f"""<tr class="rank-row"><td class="rank-cell rank-cell-rank">{rank}</td><td class="rank-cell"><div style="font-weight:bold; font-size:1.1em; color:#fff;">{name}</div><div style="color:#aaa; font-size:0.8em; margin-top:2px;">{squad}</div></td><td class="rank-cell rank-cell-last"><div style="display:flex; flex-direction:column; gap:5px;"><div style="text-align:right; font-family:'Orbitron'; color:#FFD700; font-weight:bold; font-size:1.1em;">{points}</div><div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div></div></td></tr>"""
            st.markdown(f"""<table class="rank-table">{table_rows}</table>""", unsafe_allow_html=True)
            st.markdown("### 🛡️ TOP ESCUADRONES")
            df_squads = df.groupby("Escuadrón")["MasterPoints"].sum().reset_index().sort_values(by="MasterPoints", ascending=False)
            if not df_squads.empty:
                max_squad_mp = int(df_squads["MasterPoints"].max()) if df_squads["MasterPoints"].max() > 0 else 1
                squad_rows = ""
                for i, (index, row) in enumerate(df_squads.iterrows()):
                    rank = i + 1
                    squad_name = row["Escuadrón"]
                    points = row["MasterPoints"]
                    pct = (points / max_squad_mp) * 100
                    squad_rows += f"""<tr class="rank-row"><td class="rank-cell rank-cell-rank">{rank}</td><td class="rank-cell"><div style="font-weight:bold; font-size:1.1em; color:#fff;">{squad_name}</div></td><td class="rank-cell rank-cell-last"><div style="display:flex; flex-direction:column; gap:5px;"><div style="text-align:right; font-family:'Orbitron'; color:#FFD700; font-weight:bold; font-size:1.1em;">{points}</div><div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div></div></td></tr>"""
                st.markdown(f"""<table class="rank-table">{squad_rows}</table>""", unsafe_allow_html=True)
            else: st.info("Sin datos de escuadrones.")
        else:
            st.info(f"Sin datos en el sector {uni_label}.")
            if st.button("🔄 Refrescar Señal"):
                st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                st.rerun()

    with tab_habilidades:
        st.markdown(f"### 📜 HABILIDADES: {rol.upper()}")
        core_html = f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">ENERGÍA<br>DISPONIBLE</div></div><div class="energy-val">{ap}</div></div>"""
        st.markdown(core_html, unsafe_allow_html=True)
        habilidades = st.session_state.habilidades_data
        if not habilidades: st.info("Sin datos en el Grimorio.")
        else:
            for hab in habilidades:
                nombre, costo = hab["nombre"], hab["costo"]
                desbloqueada, puede_pagar = nivel_num >= hab["nivel_req"], ap >= costo
                with st.container():
                    border_color = THEME['primary'] if desbloqueada else "#1c2630"
                    opacity, grayscale = ("1", "") if desbloqueada else ("0.5", "filter: grayscale(100%);")
                    banner_html = f'<img src="{hab.get("icon_url")}" class="skill-banner-img">' if hab.get("icon_url") else '<div class="skill-banner-placeholder">💠</div>'
                    ap_icon_html = f'<img src="data:image/png;base64,{b64_ap}" class="skill-cost-icon">'
                    card_html = f"""<div class="skill-card-container" style="border-left: 4px solid {border_color}; opacity: {opacity}; {grayscale}"><div class="skill-banner-col">{banner_html}</div><div class="skill-content-col"><div class="skill-title">{nombre}</div><p class="skill-desc">{hab["descripcion"]}</p></div><div class="skill-cost-col">{ap_icon_html}<div class="skill-cost-val">{costo}</div><div class="skill-cost-label">AP</div></div></div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
                    c_btn, _ = st.columns([1, 2])
                    with c_btn:
                        if is_alumni:
                            st.button(f"⛔ CICLO CERRADO", disabled=True, key=f"alumni_hab_{hab['id']}")
                        elif desbloqueada:
                            with st.popover("💠 PREPARAR", use_container_width=True):
                                st.markdown(f"### ⚠️ Confirmación de Conjuro\nEstás a punto de activar **{nombre}**.\n\n⚡ Costo: **{costo} AP**")
                                if st.button("🔥 CONFIRMAR", key=f"confirm_{hab['id']}"):
                                    if puede_pagar:
                                        with st.spinner("Canalizando..."):
                                            time.sleep(1)
                                            if enviar_solicitud("HABILIDAD", nombre, str(costo), st.session_state.nombre): st.toast("✅ Solicitud Enviada")
                                            else: st.error("Error de enlace.")
                                    else: st.toast("❌ Energía Insuficiente", icon="⚠️")
                        else: st.button(f"🔒 Nivel {hab['nivel_req']}", disabled=True, key=f"lk_{hab['id']}")

    with tab_codice:
        st.markdown("### 📜 ARCHIVOS SECRETOS")
        st.caption("Documentos clasificados recuperados de la Era Dorada.")
        codice_items = st.session_state.codice_data
        if not codice_items: st.info("Sin registros en el Códice.")
        else:
            for item in codice_items:
                # --- LOGICA DE BLOQUEO CODICE ---
                item_is_for_alumni = item["nombre"].startswith("[EX]") or item["nombre"].startswith("[ALUMNI]")
                
                if is_alumni and not item_is_for_alumni:
                    # Alumni restringido
                    lock_class, lock_icon = ("locked", "🔒")
                    action_html = f'<span style="color:#ff4444; font-size:0.8em; font-weight:bold;">⛔ CICLO CERRADO</span>'
                elif nivel_num < item["nivel"]:
                    # Nivel insuficiente
                    lock_class, lock_icon = ("locked", "🔒")
                    action_html = f'<span style="color:#ff4444; font-size:0.8em; font-weight:bold;">NIVEL {item["nivel"]} REQ.</span>'
                else:
                    # Desbloqueado
                    lock_class, lock_icon = ("", "🔓")
                    action_html = f'<a href="{item["url"]}" target="_blank" style="text-decoration:none; background:{THEME["primary"]}; color:black; padding:5px 15px; border-radius:5px; font-weight:bold; font-size:0.8em;">ACCEDER</a>'

                card_html = f"""<div class="codex-card {lock_class}"><div class="codex-icon">📄</div><div class="codex-info"><div class="codex-title">{item["nombre"]} {lock_icon}</div><div class="codex-desc">{item["descripcion"]}</div></div><div class="codex-action">{action_html}</div></div>"""
                st.markdown(card_html, unsafe_allow_html=True)
    
    with tab_mercado:
        st.markdown("### 🛒 EL BAZAR CLANDESTINO")
        st.caption("Intercambia tus AngioPoints por ventajas tácticas. Tus solicitudes serán enviadas a Valerius para aprobación.")
        core_html = f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">SALDO<br>ACTUAL</div></div><div class="energy-val" style="color: #00e5ff; text-shadow: 0 0 15px #00e5ff;">{ap}</div></div>"""
        st.markdown(core_html, unsafe_allow_html=True)
        market_items = st.session_state.market_data
        if not market_items:
            if not DB_MERCADO_ID: st.warning("⚠️ Base de datos de Mercado no configurada.")
            else: st.info("El mercado está vacío.")
        else:
            for item in market_items:
                item_is_for_alumni = item['nombre'].startswith("[EX]") or item['nombre'].startswith("[ALUMNI]")
                puede_ver_boton = True
                if is_alumni and not item_is_for_alumni: puede_ver_boton = False
                
                with st.container():
                    puede_comprar = ap >= item['costo']
                    price_color = "#00e5ff" if puede_comprar else "#ff4444"
                    market_html = f"""<div class="market-card"><div class="market-icon">{item['icon']}</div><div class="market-info"><div class="market-title">{item['nombre']}</div><div class="market-desc">{item['desc']}</div></div><div class="market-cost" style="color: {price_color}; text-shadow: 0 0 10px {price_color};">{item['costo']}<span>AP</span></div></div>"""
                    st.markdown(market_html, unsafe_allow_html=True)
                    c1, c2 = st.columns([3, 1])
                    with c2:
                        if puede_ver_boton:
                            if st.button(f"COMPRAR", key=f"buy_{item['id']}", disabled=not puede_comprar, use_container_width=True):
                                if puede_comprar:
                                    with st.spinner("Procesando..."):
                                        time.sleep(1)
                                        if enviar_solicitud("COMPRA", item['nombre'], str(item['costo']), st.session_state.nombre): st.success("✅ Enviado.")
                                        else: st.error("Error.")
                                else: st.error("Fondos insuficientes.")
                        else:
                            st.button("🔒 CERRADO", disabled=True, key=f"closed_{item['id']}", use_container_width=True)

    with tab_comms:
        st.markdown("### 📨 ENLACE DIRECTO AL COMANDO")
        if is_alumni:
            st.warning("📡 Enlace de comunicaciones desactivado para Aspirantes Finalizados. Solo modo lectura.")
        else:
            st.info("Utiliza este canal para reportar problemas, solicitar revisiones o comunicarte con el alto mando.")
            with st.form("comms_form_tab", clear_on_submit=True):
                msg_subject = st.text_input("Asunto / Razón:")
                msg_body = st.text_area("Mensaje:")
                if st.form_submit_button("📡 TRANSMITIR MENSAJE"):
                    if msg_subject and msg_body:
                        with st.spinner("Enviando..."):
                            time.sleep(1)
                            if enviar_solicitud("MENSAJE", msg_subject, msg_body, st.session_state.nombre): 
                                st.toast("✅ Enviado")
                                st.rerun()
                            else: st.error("Error.")
                    else: st.warning("Completa los campos.")
        st.markdown("---")
        st.markdown("#### 📂 BITÁCORA DE COMUNICACIONES")
        mi_historial = obtener_mis_solicitudes(st.session_state.nombre)
        if not mi_historial: st.caption("No hay registros.")
        else:
            for item in mi_historial:
                status_color, icon = ("#999", "⏳")
                if item["status"] == "Aprobado": status_color, icon = "#00e676", "✅"
                elif item["status"] == "Rechazado": status_color, icon = "#ff1744", "❌"
                elif item["status"] == "Respuesta": status_color, icon = "#00e5ff", "📩"
                try: 
                    utc_dt = datetime.fromisoformat(item['fecha'].replace('Z', '+00:00'))
                    fecha_str = utc_dt.astimezone(pytz.timezone('America/Santiago')).strftime("%d/%m/%Y %H:%M")
                except: fecha_str = "Fecha desc."
                log_html = f"""<div class="log-card" style="border-left-color: {status_color};"><div class="log-header"><span>{fecha_str}</span><span style="color:{status_color}; font-weight:bold;">{icon} {item['status'].upper()}</span></div><div class="log-body">{item['mensaje']}</div>{f'<div class="log-reply">🗣️ <strong>COMANDO:</strong> {item["obs"]}</div>' if item["obs"] else ''}</div>"""
                st.markdown(log_html, unsafe_allow_html=True)

    # --- BOTONES GLOBALES Y FOOTER (FUERA DE LAS TABS) ---
    st.markdown("---")
    c_refresh, c_logout = st.columns(2)
    with c_refresh:
        if st.button("ACTUALIZAR DATOS", use_container_width=True):
            actualizar_datos_sesion()
    with c_logout:
        if st.button("DESCONECTAR", use_container_width=True):
            cerrar_sesion()

# --- FOOTER UNIVERSAL (SIEMPRE VISIBLE AL FINAL) ---
st.markdown("""
    <div class="footer">
        PRAXIS PRIMORIS SYSTEM v1.0 <br> OPERADO POR VALERIUS
    </div>
""", unsafe_allow_html=True)
