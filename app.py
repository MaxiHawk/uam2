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
import json
from streamlit_lottie import st_lottie
from datetime import datetime, timedelta, date
import pytz
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter

# --- IMPORTS MODULARES OPTIMIZADOS ---
from config import (
    NOTION_TOKEN, HEADERS, ASSETS_LOTTIE, SYSTEM_MESSAGES,
    # Bases de Datos
    DB_JUGADORES_ID, DB_CODIGOS_ID, DB_LOGS_ID, DB_CONFIG_ID,
    DB_HABILIDADES_ID, DB_SOLICITUDES_ID, DB_NOTICIAS_ID, 
    DB_CODICE_ID, DB_MERCADO_ID, DB_ANUNCIOS_ID, DB_TRIVIA_ID, DB_MISIONES_ID,
    # Constantes de Juego (Ahora en config!)
    SESSION_TIMEOUT, NOMBRES_NIVELES, SQUAD_THEMES, BADGE_MAP, THEME_DEFAULT
)

from modules.notion_api import (
    verificar_modo_mantenimiento, registrar_evento_sistema, cargar_datos_jugador,
    cargar_misiones_activas, inscribir_jugador_mision, enviar_solicitud,
    procesar_codigo_canje, cargar_pregunta_aleatoria, procesar_recalibracion,
    cargar_estado_suministros, procesar_suministro,
    cargar_anuncios, procesar_compra_habilidad, cargar_habilidades, procesar_compra_mercado, obtener_miembros_escuadron
)

from modules.utils import (
    cargar_lottie_seguro, cargar_imagen_circular, generar_loot, 
    parsear_fecha_chile # <--- ¡NUESTRA NUEVA ARMA!
)

# Puente de compatibilidad
headers = HEADERS
THEME = THEME_DEFAULT # Valor inicial

st.set_page_config(page_title="Praxis Primoris", page_icon="💠", layout="centered")

# --- 🛡️ MODO MANTENIMIENTO (KILL SWITCH) ---
if verificar_modo_mantenimiento():
    # (Mantén tu código de mantenimiento aquí, no cambies nada dentro del if)
    st.markdown("""
        <style>
            .stApp { background-color: #1a0505; color: #ff4444; }
            .maintenance-container { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 80vh; text-align: center; font-family: 'Courier New', monospace; border: 2px solid #ff4444; padding: 40px; border-radius: 10px; background: rgba(255, 0, 0, 0.05); box-shadow: 0 0 50px rgba(255, 0, 0, 0.2); }
            .blink { animation: blinker 1.5s linear infinite; font-size: 3em; margin-bottom: 20px; }
            @keyframes blinker { 50% { opacity: 0; } }
        </style>
        <div class="maintenance-container"><div class="blink">⛔</div><h1 style="color: #ff4444;">SISTEMAS OFFLINE</h1><p>Mantenimiento en curso.</p></div>
    """, unsafe_allow_html=True)
    st.stop()

# --- MAPA DE INSIGNIAS (ACTUALIZADO V2) ---
BADGE_MAP = {}
for i in range(1, 10): BADGE_MAP[f"Misión {i}"] = f"assets/insignias/mision_{i}.png"
for i in range(1, 8): BADGE_MAP[f"Hazaña {i}"] = f"assets/insignias/hazana_{i}.png"
for i in range(1, 4): BADGE_MAP[f"Expedición {i}"] = f"assets/insignias/expedicion_{i}.png"
DEFAULT_BADGE = "assets/insignias/default.png"

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "player_page_id" not in st.session_state: st.session_state.player_page_id = None 
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "popup_shown" not in st.session_state: st.session_state.popup_shown = False
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "login_error" not in st.session_state: st.session_state.login_error = None
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None
if "habilidades_data" not in st.session_state: st.session_state.habilidades_data = []
if "codice_data" not in st.session_state: st.session_state.codice_data = [] 
if "market_data" not in st.session_state: st.session_state.market_data = []
if "anuncios_data" not in st.session_state: st.session_state.anuncios_data = [] 
if "uni_actual" not in st.session_state: st.session_state.uni_actual = None
if "ano_actual" not in st.session_state: st.session_state.ano_actual = None
if "estado_uam" not in st.session_state: st.session_state.estado_uam = None
if "last_active" not in st.session_state: st.session_state.last_active = time.time()
if "last_easter_egg" not in st.session_state: st.session_state.last_easter_egg = 0
if "trivia_question" not in st.session_state: st.session_state.trivia_question = None
if "trivia_feedback_mode" not in st.session_state: st.session_state.trivia_feedback_mode = False
if "trivia_last_result" not in st.session_state: st.session_state.trivia_last_result = None
if "supply_claimed_session" not in st.session_state: st.session_state.supply_claimed_session = False
if "previous_login_timestamp" not in st.session_state: st.session_state.previous_login_timestamp = None
if "redeem_key_id" not in st.session_state: st.session_state.redeem_key_id = 0

if st.session_state.get("jugador") is not None:
    if time.time() - st.session_state.last_active > SESSION_TIMEOUT:
        st.session_state.jugador = None
        st.session_state.clear()
        st.rerun()
    else:
        st.session_state.last_active = time.time()

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

        .feedback-box {{
            background: rgba(0,0,0,0.6); border-radius: 10px; padding: 25px; 
            text-align: center; margin-bottom: 20px; animation: fadeIn 0.5s;
        }}
        .feedback-correct {{ border: 2px solid #00e676; box-shadow: 0 0 25px rgba(0, 230, 118, 0.4); }}
        .feedback-wrong {{ border: 2px solid #ff1744; box-shadow: 0 0 25px rgba(255, 23, 68, 0.4); }}
        .feedback-title {{ font-family: 'Orbitron'; font-size: 1.5em; margin-bottom: 15px; font-weight: bold; text-transform: uppercase; }}
        .feedback-text {{ font-size: 1.1em; color: #eee; line-height: 1.5; }}
        
        .supply-box {{
            background: linear-gradient(135deg, rgba(20,40,60,0.9), rgba(10,20,30,0.95));
            border: 2px dashed var(--primary-color);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-bottom: 30px;
            animation: pulse 3s infinite;
        }}
        .supply-title {{ font-family: 'Orbitron'; font-size: 1.3em; color: var(--text-highlight); margin-bottom: 5px; }}
        .supply-desc {{ font-size: 0.9em; color: #aaa; margin-bottom: 15px; }}
        @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(0, 255, 157, 0.4); }} 70% {{ box-shadow: 0 0 0 15px rgba(0, 255, 157, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(0, 255, 157, 0); }} }}

        .trivia-container {{
            background: linear-gradient(145deg, rgba(20, 10, 30, 0.8), rgba(10, 5, 20, 0.9));
            border: 2px solid #e040fb;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 0 25px rgba(224, 64, 251, 0.3);
            margin-bottom: 20px;
        }}
        .trivia-question {{ font-family: 'Orbitron'; font-size: 1.2em; color: #fff; margin-bottom: 20px; }}

        .popup-container {{
            background: linear-gradient(135deg, rgba(10,20,30,0.95), rgba(0,5,10,0.98));
            border: 2px solid var(--primary-color);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 0 30px var(--glow-color);
            position: relative;
            animation: slide-in 0.5s ease-out;
        }}
        @keyframes slide-in {{ 0% {{ transform: translateY(-20px); opacity: 0; }} 100% {{ transform: translateY(0); opacity: 1; }} }}
        .popup-title {{ font-family: 'Orbitron'; font-size: 1.5em; color: var(--text-highlight); margin-bottom: 10px; text-transform: uppercase; border-bottom: 1px solid #333; padding-bottom: 5px; }}
        .popup-body {{ font-size: 1em; color: #fff; line-height: 1.5; margin-bottom: 15px; }}
        .popup-date {{ font-size: 0.7em; color: #888; text-align: right; font-style: italic; }}

        @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(-10px); }} to {{ opacity:1; transform:translateY(0); }} }}

        /* TICKER FIXED */
        .ticker-wrap {{
            width: 100%;
            overflow: hidden;
            background-color: rgba(0, 0, 0, 0.6);
            border-top: 1px solid var(--primary-color);
            border-bottom: 1px solid var(--primary-color);
            white-space: nowrap !important;
            box-sizing: border-box;
            height: 35px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
        }}
        
        .ticker-wrap:hover .ticker {{
            animation-play-state: paused; 
        }}

        .ticker {{
            display: inline-block;
            white-space: nowrap !important;
            padding-right: 100%;
            animation: ticker-animation 60s linear infinite;
        }}

        .ticker-item {{
            display: inline-block;
            padding: 0 2rem;
            font-size: 0.9em;
            color: var(--text-highlight);
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 1px;
        }}

        @keyframes ticker-animation {{
            0% {{ transform: translate3d(0, 0, 0); }}
            100% {{ transform: translate3d(-100%, 0, 0); }}
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
        .skill-title {{ 
            font-family: 'Orbitron', sans-serif; 
            font-size: 1.3em; 
            font-weight: 900; 
            color: #ffffff !important; /* Fuerza el color blanco */
            margin-bottom: 5px; 
            text-transform: uppercase;
            text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
        }}
        .skill-banner-col {{ width: 130px; flex-shrink: 0; background: #050810; display: flex; align-items: center; justify-content: center; border-right: 1px solid #1c2e3e; }}
        .skill-banner-img {{ width: 100%; height: 100%; object-fit: cover; }}
        .skill-content-col {{ flex-grow: 1; padding: 15px; display: flex; flex-direction: column; justify-content: center; }}
        .skill-cost-col {{ width: 100px; flex-shrink: 0; background: rgba(255, 255, 255, 0.03); border-left: 1px solid #1c2e3e; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; }}
        /* --- PEGAR AQUÍ (Línea ~304, fuera del @media) --- */
        .skill-cost-icon {{ 
            width: 35px; 
            height: 35px; 
            margin-bottom: 5px; 
            /* AHORA SÍ: Neón para todos */
            filter: drop-shadow(0 0 5px #00e5ff) drop-shadow(0 0 10px #00e5ff);
            transition: 0.3s;
        }}
        
        .skill-card-container:hover .skill-cost-icon {{
            filter: drop-shadow(0 0 8px #00e5ff) drop-shadow(0 0 20px #00e5ff);
            transform: scale(1.1);
        }}
        /* ------------------------------------------------ */
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
@st.cache_data(show_spinner=False)
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

def generar_tarjeta_social(badge_name, player_name, squad_name, badge_path):
    neon_color = "#00ff9d"
    gold_color = "#FFD700"
    W, H = 1080, 1920
    bg_color = '#010204'
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)

    bg_custom_path = None
    if os.path.exists("assets/social_bg.png"): bg_custom_path = "assets/social_bg.png"
    elif os.path.exists("assets/social_bg.jpg"): bg_custom_path = "assets/social_bg.jpg"

    if bg_custom_path:
        bg_img = Image.open(bg_custom_path).convert("RGBA")
        bg_img = bg_img.resize((W, H))
        img.paste(bg_img, (0, 0))
        overlay = Image.new('RGBA', (W, H), (0, 0, 0, 150)) 
        img.paste(overlay, (0, 0), overlay)
    else:
        grid_color = "#080c14"
        for x in range(0, W, 60): draw.line([(x, 0), (x, H)], fill=grid_color, width=2)
        for y in range(0, H, 60): draw.line([(0, y), (W, y)], fill=grid_color, width=2)
        offset_frame = 45
        draw.rectangle([offset_frame, offset_frame, W-offset_frame, H-offset_frame], outline=neon_color, width=10)
        draw.rectangle([offset_frame+15, offset_frame+15, W-(offset_frame+15), H-(offset_frame+15)], outline="#0a0f1a", width=6)
        node_radius = 20
        corners = [(offset_frame, offset_frame), (W-offset_frame, offset_frame), (offset_frame, H-offset_frame), (W-offset_frame, H-offset_frame)]
        for cx, cy in corners:
            draw.ellipse((cx-node_radius-5, cy-node_radius-5, cx+node_radius+5, cy+node_radius+5), fill=neon_color)
            draw.ellipse((cx-node_radius, cy-node_radius, cx+node_radius, cy+node_radius), fill=bg_color, outline=neon_color, width=4)

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
    glow_draw_wide.ellipse((50, 50, glow_size-50, glow_size-50), fill=nc_rgb + (40,))
    glow_img_wide = glow_img_wide.filter(ImageFilter.GaussianBlur(radius=90))
    
    core_size = 600
    glow_img_core = Image.new('RGBA', (core_size, core_size), (0,0,0,0))
    glow_draw_core = ImageDraw.Draw(glow_img_core)
    glow_draw_core.ellipse((20, 20, core_size-20, core_size-20), fill=nc_rgb + (100,))
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
def actualizar_ultima_conexion(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    chile_tz = pytz.timezone('America/Santiago')
    now_iso = datetime.now(chile_tz).isoformat()
    payload = {
        "properties": {
            "Ultima Conexion": {"date": {"start": now_iso}}
        }
    }
    try: requests.patch(url, headers=headers, json=payload)
    except: pass

def es_anuncio_relevante(anuncio, user_uni, user_year, is_alumni):
    target_uni = anuncio.get("universidad", "Todas")
    match_uni = False
    if isinstance(target_uni, list):
        if "Todas" in target_uni or user_uni in target_uni: match_uni = True
    elif target_uni == "Todas" or target_uni == user_uni:
        match_uni = True
    if not match_uni: return False

    target_year = anuncio.get("año", "Todas")
    match_year = False
    if not target_year: target_year = "Todas"
    if isinstance(target_year, list):
        if "Todas" in target_year or user_year in target_year: match_year = True
    elif target_year == "Todas" or target_year == user_year:
        match_year = True
    if not match_year: return False

    return True

# --- FUNCIONES BASE ---
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

@st.cache_data(ttl=3600)
def cargar_habilidades_rol(rol_jugador):
    if not rol_jugador: return []
    # Importante: Aseguramos que DB_HABILIDADES_ID esté importado en app.py
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    payload = {
        "filter": {"property": "Rol", "select": {"equals": rol_jugador}}, 
        "sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        habilidades = []
        if res.status_code == 200:
            for item in res.json()["results"]:
                props = item["properties"]
                try:
                    # --- BÚSQUEDA INTELIGENTE DEL TÍTULO (FIX) ---
                    nombre = "Habilidad Sin Nombre"
                    # Buscamos cualquier propiedad que sea de tipo 'title'
                    for key, val in props.items():
                        if val['type'] == 'title':
                            content_list = val.get("title", [])
                            if content_list:
                                nombre = "".join([t.get("plain_text", "") for t in content_list])
                            break 
                    # ---------------------------------------------

                    costo = 0
                    if "Costo AP" in props: costo = props.get("Costo AP", {}).get("number", 0)
                    elif "Costo" in props: costo = props.get("Costo", {}).get("number", 0)
                    
                    nivel_req = 1
                    if "Nivel Requerido" in props: 
                        nivel_req = props.get("Nivel Requerido", {}).get("number", 1)

                    desc_obj = props.get("Descripcion", {}).get("rich_text", [])
                    descripcion = desc_obj[0]["text"]["content"] if desc_obj else "Sin descripción"
                    
                    icon_url = None
                    if "Icono" in props:
                        files = props["Icono"].get("files", [])
                        if files: 
                            icon_url = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
                        
                    habilidades.append({
                        "id": item["id"], 
                        "nombre": nombre, 
                        "costo": costo, 
                        "nivel_req": nivel_req, 
                        "descripcion": descripcion, 
                        "icon_url": icon_url
                    })
                except Exception as e: pass
        return habilidades
    except: return []

@st.cache_data(ttl=3600)
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

@st.cache_data(ttl=600)
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
                    
                    # --- NUEVO: Detectar si es dinero real ---
                    es_dinero_real = props.get("Dinero Real", {}).get("checkbox", False)
                    # ----------------------------------------

                    items.append({
                        "id": r["id"], 
                        "nombre": nombre, 
                        "costo": costo, 
                        "desc": desc, 
                        "icon": icon,
                        "es_dinero_real": es_dinero_real # Guardamos el dato
                    })
                except: pass
        return items
    except: return []


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
                
                fecha_resp = None
                if "Fecha respuesta" in props and props["Fecha respuesta"]["date"]:
                    fecha_resp = props["Fecha respuesta"]["date"]["start"]

                historial.append({
                    "mensaje": mensaje, 
                    "status": status, 
                    "obs": obs, 
                    "fecha": created,
                    "fecha_respuesta": fecha_resp 
                })
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

@st.cache_data(ttl=300)
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
                    st.session_state.anuncios_data = cargar_anuncios()
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
                result_obj = data["results"][0]
                props = result_obj["properties"]
                page_id = result_obj["id"]
                try:
                    c_real = props.get("Clave", {}).get("rich_text", [])[0]["text"]["content"]
                    if clave == c_real:
                        st.session_state.jugador = props
                        st.session_state.player_page_id = page_id
                        st.session_state.nombre = usuario
                        
                        last_login_iso = None
                        try:
                            if "Ultima Conexion" in props and props["Ultima Conexion"]["date"]:
                                last_login_iso = props["Ultima Conexion"]["date"]["start"]
                        except: pass
                        st.session_state.previous_login_timestamp = last_login_iso
                        
                        actualizar_ultima_conexion(page_id)
                        
                        st.session_state.login_error = None
                        st.session_state.show_intro = True
                        st.session_state.popup_shown = False
                        st.session_state.supply_claimed_session = False
                        st.session_state.trivia_feedback_mode = False 
                        st.session_state.trivia_question = None
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
                        st.session_state.anuncios_data = cargar_anuncios()
                    else: st.session_state.login_error = "❌ CLAVE INCORRECTA"
                except: st.session_state.login_error = "Error Credenciales"
            else: st.session_state.login_error = "❌ USUARIO NO ENCONTRADO"
        else: st.session_state.login_error = "⚠️ Error de conexión"
    except Exception as e: st.session_state.login_error = f"Error técnico: {e}"

def cerrar_sesion():
    st.session_state.clear()
    st.rerun()

# --- NUEVAS FUNCIONES: SISTEMA DE MISIONES ---
    
# ================= UI PRINCIPAL =================

main_placeholder = st.empty()

if not st.session_state.jugador:
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
    main_placeholder.empty() 

    # --- CENTRO DE NOTIFICACIONES (FEEDBACK LOOP) ---
    if "notificaciones_check" not in st.session_state:
        st.session_state.notificaciones_check = False

    if not st.session_state.notificaciones_check:
        st.session_state.notificaciones_check = True 
        
        historial_reciente = obtener_mis_solicitudes(st.session_state.nombre)
        
        fecha_corte = None
        if "previous_login_timestamp" in st.session_state and st.session_state.previous_login_timestamp:
            try:
                raw_prev = st.session_state.previous_login_timestamp
                chile_tz = pytz.timezone('America/Santiago')
                if "T" in raw_prev:
                    dt_prev = datetime.fromisoformat(raw_prev.replace('Z', '+00:00'))
                    fecha_corte = dt_prev.astimezone(chile_tz)
                else:
                    fecha_corte = chile_tz.localize(datetime.strptime(raw_prev, "%Y-%m-%d"))
            except: pass
        
        if fecha_corte and historial_reciente:
            for req in historial_reciente:
                if req.get('fecha_respuesta'): 
                    try:
                        resp_iso = req['fecha_respuesta']
                        if "T" in resp_iso:
                            dt_resp = datetime.fromisoformat(resp_iso.replace('Z', '+00:00')).astimezone(pytz.timezone('America/Santiago'))
                        else:
                            dt_resp = pytz.timezone('America/Santiago').localize(datetime.strptime(resp_iso, "%Y-%m-%d"))
                        
                        if dt_resp > fecha_corte:
                            icono = "✅" if req['status'] == "Aprobado" else "❌" if req['status'] == "Rechazado" else "📩"
                            st.toast(f"{icono} {req['status'].upper()}: {req['mensaje']}", icon="🔔")
                            time.sleep(0.5) 
                    except: pass

    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Ubicación Desconocida"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "Ciclo ?"
    estado_label = st.session_state.estado_uam if st.session_state.estado_uam else "Desconocido"
    is_alumni = (estado_label == "Finalizado")
    status_color = "#ff4b4b" if is_alumni else "#00e5ff"
    if estado_label == "Sin empezar": status_color = "#FFD700"

    # --- POPUP ANUNCIO INTELIGENTE ---
    if not st.session_state.popup_shown and st.session_state.anuncios_data:
        if not is_alumni:
            anuncio_para_mostrar = None
            for anuncio in st.session_state.anuncios_data:
                if es_anuncio_relevante(anuncio, uni_label, ano_label, is_alumni):
                    anuncio_para_mostrar = anuncio
                    break
            
            if anuncio_para_mostrar:
                st.session_state.popup_shown = True
                # --- LIMPIEZA NEO: Usamos el helper ---
                fecha_popup = parsear_fecha_chile(anuncio_para_mostrar['fecha'], "%d/%m/%Y")
                # --------------------------------------

                with st.expander("🚨 TRANSMISIÓN PRIORITARIA ENTRANTE", expanded=True):
                    st.markdown(f"""
                    <div class="popup-container">
                        <div class="popup-title">{anuncio_para_mostrar['titulo']}</div>
                        <div class="popup-body">{anuncio_para_mostrar['contenido']}</div>
                        <div class="popup-date">FECHA ESTELAR: {fecha_popup}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button("ENTENDIDO, CERRAR ENLACE"):
                        st.rerun()

    news_text = obtener_noticias()
    st.markdown(f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{news_text}</div></div></div>""", unsafe_allow_html=True)

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

    tab_perfil, tab_ranking, tab_habilidades, tab_misiones, tab_codice, tab_mercado, tab_trivia, tab_codes, tab_comms = st.tabs(["👤 PERFIL", "🏆 RANKING", "⚡ HABILIDADES", "🚀 MISIONES", "📜 CÓDICE", "🛒 MERCADO", "🔮 ORÁCULO", "🔐 CÓDIGOS", "📡 COMUNICACIONES"])    
    with tab_perfil:
        # DIAGNOSTICO SUMINISTROS (SOLO ACTIVOS)
        # Si es Alumni, no mostramos nada. Si es activo, mostramos el estado.
        if not is_alumni:
            supply_status_text = "🔴 ENLACE DE SUMINISTROS: OFF"
            supply_active = cargar_estado_suministros()
            if supply_active: supply_status_text = "🟢 ENLACE DE SUMINISTROS: ON"
            st.caption(supply_status_text)
        else:
            supply_active = False # Forzamos apagado para Alumni por seguridad
        
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
        
        if not is_alumni:
            chile_tz = pytz.timezone('America/Santiago')
            today_chile = datetime.now(chile_tz).date()
            
            claimed_today = False
            last_supply_str = None
            
            try:
                ls_prop = p.get("Ultimo Suministro")
                if ls_prop:
                    last_supply_str = ls_prop.get("date", {}).get("start")
            except: last_supply_str = None

            if last_supply_str:
                try:
                    if "T" in last_supply_str:
                        dt_obj = datetime.fromisoformat(last_supply_str.replace('Z', '+00:00'))
                        if dt_obj.tzinfo is None:
                            dt_obj = pytz.utc.localize(dt_obj)
                        date_stored = dt_obj.astimezone(chile_tz).date()
                    else:
                        date_stored = datetime.strptime(last_supply_str, "%Y-%m-%d").date()
                    
                    if date_stored == today_chile:
                        claimed_today = True
                except: pass
            
            if st.session_state.supply_claimed_session:
                claimed_today = True

            if supply_active:
                    if claimed_today:
                        st.info("✅ Suministros diarios ya reclamados.")
                    else:
                        # --- INICIO DEL CONTENEDOR MAESTRO ---
                        # 1. Creamos un espacio único para TODO (Texto + Botón)
                        supply_container = st.empty()
                        clicked = False

                        # 2. Dibujamos el Banner y el Botón DENTRO de ese espacio
                        with supply_container.container():
                            st.markdown("""
                            <div class="supply-box">
                                <div class="supply-title">📡 SEÑAL DE SUMINISTROS DETECTADA</div>
                                <div class="supply-desc">El Sumo Cartógrafo ha liberado un paquete de ayuda en tu sector.</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Capturamos el clic en una variable
                            if st.button("📦 RECLAMAR SUMINISTROS", use_container_width=True):
                                clicked = True

                        # 3. SI SE HIZO CLIC...
                        if clicked:
                            # 1. Limpieza inicial
                            supply_container.empty()
                            anim_stage = st.empty()
                            
                            tier, rewards, icon = generar_loot()
                            if procesar_suministro(tier, rewards):
                                st.session_state.supply_claimed_session = True
                                
                                # Construimos el texto real de recompensas
                                reward_text = f"+{rewards['AP']} AP"
                                if rewards['MP'] > 0: reward_text += f" | +{rewards['MP']} MP"
                                if rewards['VP'] > 0: reward_text += f" | +{rewards['VP']} VP"
                                
                                # Lógica de Animación (EL CÓDIGO QUE FALTABA)
                                with anim_stage:
                                    lottie_target = "loot_legendary" if tier == "Legendario" else "loot_epic"
                                    # Usamos la función segura
                                    ani_data = cargar_lottie_seguro(ASSETS_LOTTIE.get(lottie_target, ""))
                                    if ani_data:
                                        st_lottie(ani_data, height=300, key=f"loot_anim_{time.time()}")
                                
                                # Feedback Texto
                                icon_map = {"Común": "📦", "Raro": "💼", "Épico": "💠", "Legendario": "👑"}
                                st.toast(f"SUMINISTRO {tier.upper()}: {reward_text}", icon=icon_map.get(tier, "📦"))
                                
                                time.sleep(2.5)
                                anim_stage.empty() # Borra la animación
                                
                                # --- TRUCO DE MEMORIA (Optimistic UI) ---
                                
                                # A) Mensaje verde final
                                st.info("✅ Suministros diarios ya reclamados.")
                                
                                # B) Hack de Memoria para bloqueo instantáneo
                                from datetime import datetime
                                import pytz
                                chile_tz = pytz.timezone('America/Santiago')
                                now_iso = datetime.now(chile_tz).isoformat()
                                
                                if "jugador" in st.session_state:
                                    if "Ultimo Suministro" not in st.session_state.jugador:
                                        st.session_state.jugador["Ultimo Suministro"] = {}
                                    st.session_state.jugador["Ultimo Suministro"]["date"] = {"start": now_iso}
                                
                                time.sleep(1.0)
                                actualizar_datos_sesion() 
                            else:
                                st.error("Error de conexión.")
        
        c_egg1, c_egg2, c_egg3 = st.columns([1.5, 1, 1.5]) 
        with c_egg2:
            # --- CORRECCIÓN: BLOQUEO PARA ALUMNI ---
            if is_alumni:
                # Botón gris y desactivado para los retirados
                st.button("⛔ SISTEMA OFFLINE", disabled=True, key="status_alumni", use_container_width=True)
            else:
                # Botón funcional para los activos
                if st.button("💠 STATUS DEL SISTEMA", use_container_width=True):
                    now = time.time()
                    if now - st.session_state.last_easter_egg > 60:
                        st.session_state.last_easter_egg = now
                        msg = random.choice(SYSTEM_MESSAGES)
                        st.toast(msg, icon="🤖")
                        # 10% de probabilidad de ganar AP extra
                        if random.random() < 0.1:
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
        # --- PARCHE CSS: Estilo para el título de la habilidad ---
        st.markdown("""
        <style>
            .skill-title {
                font-family: 'Orbitron', sans-serif;
                font-weight: 900;
                font-size: 1.3em;
                color: #ffffff !important;
                margin-bottom: 5px;
                text-transform: uppercase;
                text-shadow: 0 0 10px rgba(0, 229, 255, 0.5);
            }
            .skill-desc {
                font-size: 0.85em;
                color: #b0bec5;
                line-height: 1.4;
            }
        </style>
        """, unsafe_allow_html=True)
      
        
        # Recuperamos datos del Rol
        rol_data = p.get("Rol", {}).get("select")
        rol_jugador_actual = rol_data.get("name") if rol_data else None
        
        titulo_rol = rol_jugador_actual.upper() if rol_jugador_actual else "RECLUTA"
        st.markdown(f"### ⚡ HABILIDADES DE: {titulo_rol}")
        
        # Panel de Energía
        core_html = f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">ANGIOPOINTS<br>DISPONIBLES</div></div><div class="energy-val" style="color: #00e5ff; text-shadow: 0 0 15px #00e5ff;">{ap}</div></div>"""
        st.markdown(core_html, unsafe_allow_html=True)

        if is_alumni:
             st.info("⛔ El mercado de habilidades está cerrado para agentes retirados.")
        elif not rol_jugador_actual:
             st.warning("⚠️ Tu perfil no tiene un ROL asignado. Contacta al comando.")
        else:
            # Forzamos recarga si el nombre no se ve (limpia cache en la primera carga)
            skills_reales = cargar_habilidades(rol_jugador_actual)
            
            if not skills_reales:
                st.info(f"No se encontraron habilidades tácticas para **{rol_jugador_actual}**.")
            else:
                for i, item in enumerate(skills_reales):
                    # Lógica
                    bloqueada_por_nivel = nivel_num < item['nivel_req']
                    sin_saldo = ap < item['costo']
                    
                    # Estilos
                    primary_col = THEME.get('primary', '#00ff9d')
                    border_color = primary_col if not bloqueada_por_nivel else "#444"
                    opacity = "1.0" if not bloqueada_por_nivel else "0.7"
                    grayscale = "" if not bloqueada_por_nivel else "filter: grayscale(100%);"
                    
                    # Imagen
                    img_src = item['icon_url'] if item['icon_url'] else "https://cdn-icons-png.flaticon.com/512/2646/2646067.png"
                    
                    # --- DISEÑO MEJORADO: Texto más grande ---
                    card_html = f"""
                    <div class="skill-card-container" style="border-left: 4px solid {border_color}; opacity: {opacity}; {grayscale} height: 150px;">
                        <div class="skill-banner-col" style="width: 150px; padding: 0; overflow: hidden; background: #000;">
                            <img src="{img_src}" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.9;">
                        </div>
                        <div class="skill-content-col" style="padding-left: 25px;">
                            <div class="skill-title" style="font-family: 'Orbitron'; font-weight: bold; color: #fff; font-size: 1.4em; letter-spacing: 1px; text-shadow: 0 0 5px rgba(0,0,0,0.8); margin-bottom: 5px;">{item['nombre']}</div>
                            <div class="skill-desc" style="font-size: 1em; color: #ddd; margin-top: 5px; line-height: 1.3;">{item['desc']}</div>
                            <div style="font-size: 0.85em; color: {border_color}; margin-top: 10px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase;">🔒 NIVEL REQUERIDO: {item['nivel_req']}</div>
                        </div>
                        <div class="skill-cost-col" style="min-width: 100px; background: rgba(0,0,0,0.3);">
                            <img src="data:image/png;base64,{b64_ap}" class="skill-cost-icon" style="width: 40px; margin-bottom: 5px;">
                            <div class="skill-cost-val" style="font-family: 'Orbitron'; font-weight: bold; font-size: 1.8em; color: #fff; text-shadow: 0 0 10px #00e5ff;">{item['costo']}</div>
                        </div>
                    </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # Botones
                    c_fill, c_btn = st.columns([1.5, 1.5])
                    with c_btn:
                        if bloqueada_por_nivel:
                            st.button(f"🔒 NVL {item['nivel_req']}", disabled=True, key=f"lk_{item['id']}", use_container_width=True)
                        elif sin_saldo:
                            st.button(f"💸 FALTA AP", disabled=True, key=f"noap_{item['id']}", use_container_width=True)
                        else:
                            with st.popover("⚡ ACTIVAR", use_container_width=True):
                                st.markdown(f"""
                                <div style="text-align: center; border: 1px solid {primary_col}; padding: 15px; border-radius: 10px; background: rgba(0,0,0,0.5);">
                                    <div style="color: #aaa; font-size: 0.8em; letter-spacing: 2px;">CONFIRMAR DESPLIEGUE</div>
                                    <div style="font-family: 'Orbitron'; font-size: 1.6em; font-weight: bold; color: #00e5ff; margin: 10px 0; text-shadow: 0 0 15px #00e5ff;">{item['nombre']}</div>
                                    <div style="display: flex; justify-content: center; align-items: center; gap: 10px; margin-bottom: 10px;">
                                        <span style="color: #fff;">COSTO:</span>
                                        <span style="color: #00e5ff; font-weight: bold; font-size: 1.2em; text-shadow: 0 0 5px #00e5ff;">{item['costo']} AP</span>
                                    </div>
                                    <div style="font-size: 0.8em; color: #ccc; font-style: italic;">"Se enviará una solicitud prioritaria al Comando."</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                st.markdown("<br>", unsafe_allow_html=True)
                                
                                if st.button("🚀 EJECUTAR PROTOCOLO", key=f"btn_{item['id']}", type="primary", use_container_width=True):
                                    with st.spinner("Estableciendo enlace neural..."):
                                        exito, msg = procesar_compra_habilidad(
                                            item['nombre'], 
                                            item['costo'], 
                                            0, 
                                            item['id']
                                        )
                                        if exito:
                                            # --- NUEVO DISEÑO: AZUL AP Y SIN GLOBOS ---
                                            st.markdown(f"""
                                            <div style="margin-top: 15px; text-align: center; padding: 15px; border: 1px solid #00e5ff; background: rgba(0, 229, 255, 0.1); border-radius: 10px; box-shadow: 0 0 15px rgba(0, 229, 255, 0.2);">
                                                <div style="font-family: 'Orbitron'; font-size: 1.2em; font-weight: bold; color: #00e5ff; text-shadow: 0 0 5px #00e5ff;">✅ SOLICITUD ENVIADA</div>
                                                <div style="font-size: 0.9em; color: #fff; margin-top: 5px;">Se han descontado <strong style="color: #00e5ff;">{item['costo']} AP</strong> de tu saldo.</div>
                                                <div style="font-size: 0.75em; color: #aaa; margin-top: 5px;">Esperando confirmación del Comando.</div>
                                            </div>
                                            """, unsafe_allow_html=True)
                                            # ------------------------------------------
                                            time.sleep(2.5) # Damos un poco más de tiempo para leer
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                            
       
    with tab_misiones:
        import re
        import os

        # --- CSS TÁCTICO (V7.1: FINAL STABLE) ---
        primary_sync_color = "#e040fb" # Lavanda Neón para Misiones Grupales
        
        st.markdown(f"""
        <style>
            .mission-card {{
                background: linear-gradient(135deg, #0f1520 0%, #050810 100%);
                border: 1px solid #333;
                border-radius: 12px;
                padding: 0;
                margin-bottom: 20px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                transition: transform 0.2s;
            }}
            .mission-header {{
                padding: 12px 20px;
                display: flex; justify-content: space-between; align-items: center;
                border-bottom: 1px solid rgba(255,255,255,0.1);
                background: rgba(0,0,0,0.2);
            }}
            .mission-title {{
                font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 1.2em;
                color: #fff; text-transform: uppercase; display: flex; align-items: center; gap: 10px;
            }}
            
            .mission-narrative {{
                background: rgba(0, 229, 255, 0.05); color: #00e5ff; 
                font-style: italic; font-size: 0.85em; padding: 8px 20px;
                border-bottom: 1px dashed rgba(0, 229, 255, 0.2);
            }}
            .mission-body {{ padding: 15px 20px; color: #b0bec5; font-size: 0.95em; line-height: 1.5; }}
            
            .rewards-box {{
                background: rgba(0,0,0,0.3); margin: 0 20px 15px 20px; padding: 10px;
                border-radius: 8px; border: 1px solid #333; display: flex; align-items: center; gap: 15px;
            }}
            .reward-badge-img {{ width: 50px; height: 50px; object-fit: contain; filter: drop-shadow(0 0 5px #FFD700); }}
            .reward-text {{ font-size: 0.9em; color: #e0e0e0; font-family: monospace; letter-spacing: 0.5px; }}
            
            .mission-footer {{
                background: rgba(0, 0, 0, 0.4); padding: 10px 20px;
                display: flex; justify-content: space-between; align-items: center;
                border-top: 1px solid rgba(255,255,255,0.05);
            }}
            .mission-timer {{ font-family: monospace; font-size: 0.85em; color: #aaa; display: flex; align-items: center; gap: 5px; }}
            .mission-status {{ font-weight: bold; font-size: 0.8em; letter-spacing: 1px; text-transform: uppercase; }}

            /* SYNC BAR */
            .sync-bar-bg {{ width: 100%; height: 10px; background: #2a2a2a; border-radius: 5px; margin-top: 8px; overflow: hidden; border: 1px solid #444; }}
            .sync-bar-fill {{ height: 100%; background: {primary_sync_color}; box-shadow: 0 0 15px {primary_sync_color}; transition: width 0.5s ease; }}
            .sync-label {{ 
                font-family: 'Orbitron'; font-size: 0.85em; color: {primary_sync_color}; 
                margin-top: 5px; display: flex; justify-content: space-between; font-weight: bold;
                text-shadow: 0 0 5px rgba(224, 64, 251, 0.3);
            }}
        </style>
        """, unsafe_allow_html=True)

        st.markdown("### 🚀 CENTRO DE OPERACIONES TÁCTICAS")
        
        if is_alumni:
            st.info("⛔ ACCESO DENEGADO: Área restringida para Agentes Activos.")
        else:
            st.caption("Calendario de despliegue de Operaciones.")
            misiones = cargar_misiones_activas()
            
            # Carga inteligente de miembros
            mi_escuadron_lista = []
            if any(m['tipo'] == "Misión" for m in misiones):
                mi_escuadron_lista = obtener_miembros_escuadron(
                    st.session_state.squad_name, 
                    st.session_state.uni_actual, 
                    st.session_state.ano_actual
                )

            chile_tz = pytz.timezone('America/Santiago')
            now_chile = datetime.now(chile_tz)

            def parse_notion_date(date_str):
                if not date_str: return None
                try:
                    if "T" in date_str: dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    else: dt = chile_tz.localize(datetime.strptime(date_str, "%Y-%m-%d"))
                    if dt.tzinfo is None: dt = pytz.utc.localize(dt).astimezone(chile_tz)
                    else: dt = dt.astimezone(chile_tz)
                    return dt
                except: return None

            if not misiones:
                st.info("📡 No hay operaciones programadas en el radar.")
            else:
                for m in misiones:
                    uni_usuario = st.session_state.uni_actual
                    targets = m.get("target_unis", ["Todas"])
                    if "Todas" not in targets and uni_usuario not in targets: continue
                    
                    dt_apertura = parse_notion_date(m['f_apertura'])
                    dt_cierre = parse_notion_date(m['f_cierre'])
                    dt_lanzamiento = parse_notion_date(m['f_lanzamiento'])
                    
                    lista_inscritos = [x.strip() for x in m['inscritos'].split(",") if x.strip()]
                    esta_inscrito = st.session_state.nombre in lista_inscritos
                    es_mision_grupal = (m['tipo'] == "Misión")
                    
                    # --- PREPARACIÓN DE DATOS VISUALES ---
                    if es_mision_grupal:
                        icon_type = "🧬"
                        border_color = primary_sync_color
                        
                        confirmados_escuadron = [p for p in lista_inscritos if p in mi_escuadron_lista]
                        total_squad = len(mi_escuadron_lista) if mi_escuadron_lista else 1
                        count_confirmados = len(confirmados_escuadron)
                        progress_pct = int((count_confirmados / total_squad) * 100) if total_squad > 0 else 0
                        squad_synced = (progress_pct >= 100)
                        
                        glow = f"box-shadow: 0 0 15px {border_color}40;"
                        status_text = "PROTOCOLO DE SINCRONIZACIÓN"
                        status_color = border_color
                        time_display = f"LÍMITE DE ENVÍO: {dt_cierre.strftime('%d/%m %H:%M')}" if dt_cierre else "SIN LÍMITE"
                    else:
                        es_expedicion = m['tipo'] == "Expedición"
                        border_color = "#bf360c" if es_expedicion else "#FFD700"
                        icon_type = "🌋" if es_expedicion else "⚔️"
                        
                        if dt_apertura and now_chile < dt_apertura:
                            estado_fase, status_text, status_color = "PRE", "🔒 ENCRIPTADO", "#666"
                        elif (dt_apertura and dt_cierre) and (dt_apertura <= now_chile <= dt_cierre):
                            estado_fase, status_text, status_color = "OPEN", "🔓 INSCRIPCIÓN ABIERTA", "#00e676"
                        elif dt_cierre and now_chile > dt_cierre:
                            estado_fase, status_text, status_color = "CLOSED", "🔒 CERRADO", "#ff1744"
                        else:
                            estado_fase, status_text, status_color = "CLOSED", "🔒 CERRADO", "#666"
                        
                        glow = f"box-shadow: 0 0 15px {border_color}40;" if estado_fase == "OPEN" else ""
                        time_display = f"INICIO: {dt_lanzamiento.strftime('%d/%m %H:%M') if dt_lanzamiento else 'TBA'}"

                    # --- IMAGEN ---
                    badge_html = ""
                    raw_filename = m.get('insignia_file', "")
                    if raw_filename:
                        clean_filename = raw_filename.strip()
                        possible_paths = [f"assets/{clean_filename}", f"assets/insignias/{clean_filename}", f"{clean_filename}"]
                        found_path = next((p for p in possible_paths if os.path.exists(p)), None)
                        if found_path:
                            b64_insignia = get_img_as_base64(found_path)
                            badge_html = f'<img src="data:image/png;base64,{b64_insignia}" class="reward-badge-img">'
                        else:
                            badge_html = f'<span style="font-size: 2em; cursor: help;" title="No se encontró: {clean_filename}">🏆</span>'
                    else:
                        badge_html = '<span style="font-size: 2em;">🏆</span>'

                    # --- COLORIZACIÓN ---
                    txt_recompensas = m['recompensas_txt']
                    txt_recompensas = re.sub(r'(\d+\s*AP)', r'<span style="color:#00e5ff; font-weight:bold;">\1</span>', txt_recompensas)
                    txt_recompensas = re.sub(r'(\d+\s*MP)', r'<span style="color:#FFD700; font-weight:bold;">\1</span>', txt_recompensas)

                    # --- RENDERIZADO HTML ---
                    with st.container():
                        card_html = f"""
<div class="mission-card" style="border-left: 5px solid {border_color}; {glow}">
<div class="mission-header">
<div class="mission-title">{icon_type} {m['nombre']}</div>
</div>
<div class="mission-narrative">"{m['narrativa']}"</div>
<div class="mission-body">{m['descripcion']}</div>
<div class="rewards-box">
{badge_html}
<div>
<div style="font-size: 0.7em; color: #888; text-transform: uppercase; letter-spacing: 1px;">Recompensas</div>
<div class="reward-text">{txt_recompensas}</div>
</div>
</div>
<div class="mission-footer">
<div class="mission-timer">⏳ {time_display}</div>
<div class="mission-status" style="color: {status_color};">{status_text}</div>
</div>
</div>
"""
                        st.markdown(card_html, unsafe_allow_html=True)
                        
                        # --- BOTONERA ---
                        if es_mision_grupal:
                            # LÓGICA GRUPAL
                            st.markdown(f"""
                            <div class="sync-bar-bg">
                                <div class="sync-bar-fill" style="width: {progress_pct}%;"></div>
                            </div>
                            <div class="sync-label">
                                <span>SINCRONIZACIÓN AL {progress_pct}%</span>
                                <span>({count_confirmados}/{total_squad} ASPIRANTES)</span>
                            </div>
                            """, unsafe_allow_html=True)
                            st.markdown("<br>", unsafe_allow_html=True)

                            c1, c2 = st.columns([2, 1])
                            with c1:
                                if squad_synced:
                                    # CAMBIO AQUÍ: SQUAD -> ESCUADRÓN
                                    st.success("✅ **ESCUADRÓN SINCRONIZADO**")
                                    with st.expander("🔓 ACCESO A DATOS CLASIFICADOS", expanded=True):
                                        st.markdown(f"**🔑 CLAVE:** `{m['password']}`")
                                        st.markdown(f"**🌐 ENLACE:** [ACCEDER AL TERMINAL]({m['link']})")
                                else:
                                    faltantes = [nm for nm in mi_escuadron_lista if nm not in confirmados_escuadron]
                                    if faltantes:
                                        faltantes_str = ", ".join(faltantes[:3]) + ("..." if len(faltantes) > 3 else "")
                                        st.info(f"⏳ **FALTAN:** {faltantes_str}")
                                    else:
                                        st.info("⏳ Esperando red neuronal...")

                            with c2:
                                if not esta_inscrito:
                                    mision_vencida = dt_cierre and now_chile > dt_cierre
                                    if mision_vencida:
                                        st.button("🔒 TIEMPO AGOTADO", disabled=True, use_container_width=True)
                                    else:
                                        if st.button("🫡 CONFIRMAR ORDEN", key=f"sync_{m['id']}", type="primary", use_container_width=True):
                                            with st.spinner("Sincronizando..."):
                                                if inscribir_jugador_mision(m['id'], m['inscritos'], st.session_state.nombre):
                                                    st.toast("ENLACE ESTABLECIDO", icon="🧬")
                                                    time.sleep(1)
                                                    st.rerun()
                                                else: st.error("Error.")
                                else:
                                    st.button("✅ LISTO", disabled=True, key=f"rdy_sync_{m['id']}", use_container_width=True)

                        else:
                            # LÓGICA INDIVIDUAL
                            c1, c2 = st.columns([2, 1])
                            with c1:
                                if esta_inscrito:
                                    mision_lanzada = now_chile >= dt_lanzamiento
                                    if mision_lanzada:
                                        st.success("🟢 **OPERACIÓN EN CURSO**")
                                        with st.expander("📂 ACCEDER A DATOS DE ACTIVIDAD", expanded=True):
                                            st.markdown(f"**🔑 CLAVE:** `{m['password']}`")
                                            st.markdown(f"**🌐 ENLACE:** [INICIAR]({m['link']})")
                                    else:
                                        st.info(f"✅ **INSCRITO** | Esperando fecha de lanzamiento...")
                                elif estado_fase == "PRE":
                                    st.warning(f"⏳ Inscripciones: {dt_apertura.strftime('%d/%m %H:%M')}")
                                elif estado_fase == "CLOSED":
                                    st.error("Inscripciones Cerradas")

                            with c2:
                                if estado_fase == "OPEN" and not esta_inscrito:
                                    with st.popover("📝 INSCRIBIRME", use_container_width=True):
                                        st.markdown(f"### ⚠️ Compromiso de Servicio")
                                        st.markdown(f"**{m['nombre']}**")
                                        st.error(f"**ADVERTENCIA:** {m['advertencia']}")
                                        st.caption("Al confirmar, aceptas las condiciones y penalizaciones por abandono.")
                                        if st.button("🚀 ACEPTO EL RIESGO", key=f"join_{m['id']}", type="primary", use_container_width=True):
                                            with st.spinner("Firmando contrato..."):
                                                if inscribir_jugador_mision(m['id'], m['inscritos'], st.session_state.nombre):
                                                    st.toast("CONTRATO VINCULANTE ACEPTADO", icon="✅")
                                                    time.sleep(1.5)
                                                    st.rerun()
                                                else: st.error("Error.")
                                elif esta_inscrito:
                                    st.button("✅ LISTO", disabled=True, key=f"rdy_{m['id']}", use_container_width=True)
                                else:
                                    st.button("🔒", disabled=True, key=f"lck_{m['id']}", use_container_width=True) 
                                
    with tab_codice:
        st.markdown("### 📜 ARCHIVOS SECRETOS")
        
        if is_alumni:
            # PANTALLA DE BLOQUEO PARA VETERANOS
            st.markdown("""
            <div style="background: rgba(40, 10, 10, 0.5); border: 1px solid #ff4444; border-radius: 10px; padding: 20px; text-align: center; margin-top: 20px;">
                <div style="font-size: 3em;">⛔</div>
                <div style="font-family: 'Orbitron'; color: #ff4444; font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">ACCESO DENEGADO</div>
                <div style="color: #ccc; font-size: 0.9em;">
                    Los Archivos Secretos contienen material sensible clasificado.<br>
                    Tu autorización ha expirado al finalizar tu ciclo operativo.
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            st.caption("Documentos clasificados recuperados de la Era Dorada.")
            codice_items = st.session_state.codice_data
            if not codice_items: st.info("Sin registros en el Códice.")
            else:
                for item in codice_items:
                    if nivel_num < item["nivel"]:
                        lock_class, lock_icon = ("locked", "🔒")
                        action_html = f'<span style="color:#ff4444; font-size:0.8em; font-weight:bold;">NIVEL {item["nivel"]} REQ.</span>'
                    else:
                        lock_class, lock_icon = ("", "🔓")
                        action_html = f'<a href="{item["url"]}" target="_blank" style="text-decoration:none; background:{THEME["primary"]}; color:black; padding:5px 15px; border-radius:5px; font-weight:bold; font-size:0.8em;">ACCEDER</a>'

                    card_html = f"""<div class="codex-card {lock_class}"><div class="codex-icon">📄</div><div class="codex-info"><div class="codex-title">{item["nombre"]} {lock_icon}</div><div class="codex-desc">{item["descripcion"]}</div></div><div class="codex-action">{action_html}</div></div>"""
                    st.markdown(card_html, unsafe_allow_html=True)
    
    with tab_mercado:
        st.markdown("### 🛒 EL BAZAR CLANDESTINO")
        st.caption("Intercambia tus AngioPoints por ventajas tácticas. Tus solicitudes serán enviadas a Valerius para aprobación.")
        
        # Panel de Energía (AP)
        core_html = f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">ENERGÍA<br>DISPONIBLE</div></div><div class="energy-val" style="color: #00e5ff; text-shadow: 0 0 15px #00e5ff;">{ap}</div></div>"""
        st.markdown(core_html, unsafe_allow_html=True)
        
        market_items = st.session_state.market_data
        
        if not market_items:
            if not DB_MERCADO_ID: st.warning("⚠️ Base de datos de Mercado no configurada.")
            else: st.info("El mercado está vacío.")
        else:
            # Bucle Principal de Mercado
            for item in market_items:
                
                # 1. Datos del Item (Detectamos si es dinero real)
                is_real_money = item.get("es_dinero_real", False)
                
                # 2. Lógica de Visibilidad (Alumni vs Activos)
                is_exclusive = "[EX]" in item['nombre'] or "[ALUMNI]" in item['nombre']
                puede_ver_boton = True
                texto_boton_cerrado = ""

                if is_alumni:
                    # Alumni ve exclusivos O dinero real
                    if not is_exclusive and not is_real_money:
                        puede_ver_boton = False
                        texto_boton_cerrado = "⛔ CICLO CERRADO"
                else:
                    # Activos no ven exclusivos (pero sí pueden ver dinero real si quieres)
                    if is_exclusive:
                        puede_ver_boton = False
                        texto_boton_cerrado = "🔒 SOLO VETERANOS"

                # 3. Renderizado de Tarjeta
                with st.container():
                    # Lógica de Precio y Color
                    if is_real_money:
                        # Si es dinero real, siempre "puede comprar" (no depende de AP)
                        puede_comprar = True
                        price_color = "#00ff00" # Verde para Dinero
                        costo_display = f"${item['costo']:,}" # Formato dinero (ej: $15,000)
                        moneda_label = "CLP" # O la moneda que prefieras
                    else:
                        # Lógica AP normal
                        puede_comprar = ap >= item['costo']
                        price_color = "#00e5ff" if puede_comprar else "#ff4444"
                        costo_display = str(item['costo'])
                        moneda_label = "AP"
                    
                    # HTML de la Tarjeta
                    market_html = f"""<div class="market-card"><div class="market-icon">{item['icon']}</div><div class="market-info"><div class="market-title">{item['nombre']}</div><div class="market-desc">{item['desc']}</div></div><div class="market-cost" style="color: {price_color}; text-shadow: 0 0 10px {price_color};">{costo_display}<span>{moneda_label}</span></div></div>"""
                    st.markdown(market_html, unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([3, 1])
                    with c2:
                        if puede_ver_boton:
                            if puede_comprar:
                                # Usamos un Popover para la confirmación de seguridad
                                with st.popover(f"ADQUIRIR", use_container_width=True):
                                    st.markdown(f"""
                                    <div style="text-align: center;">
                                        <div style="font-size: 3em;">{item['icon']}</div>
                                        <h3 style="margin: 0; color: #00e5ff;">{item['nombre']}</h3>
                                        <p style="color: #aaa; font-size: 0.9em;">¿Iniciar proceso de compra?</p>
                                        <div style="background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px; margin: 10px 0;">
                                            Valor: <strong style="color: {price_color};">{costo_display} {moneda_label}</strong>
                                        </div>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                    if st.button("🚀 CONFIRMAR SOLICITUD", key=f"confirm_{item['id']}", type="primary", use_container_width=True):
                                        with st.spinner("Contactando proveedor..."):
                                            # Pasamos el flag de dinero real a la función
                                            exito, msg = procesar_compra_mercado(item['nombre'], item['costo'], is_real_money)
                                            if exito:
                                                st.success("✅ ¡Solicitud Enviada!")
                                                time.sleep(2)
                                                actualizar_datos_sesion()
                                            else:
                                                st.error(msg)
                            else:
                                # Botón deshabilitado si no hay dinero AP
                                st.button(f"💸 FALTA AP", disabled=True, key=f"no_money_{item['id']}", use_container_width=True)
                        else:
                            # Botón de bloqueo (Alumni/Veteranos)
                            st.button(texto_boton_cerrado, disabled=True, key=f"closed_{item['id']}", use_container_width=True)

    with tab_trivia:
        st.markdown("### 🔮 EL ORÁCULO DE VALERIUS")
        
        if is_alumni:
            # PANTALLA DE BLOQUEO PARA VETERANOS
            st.markdown("""
            <div style="background: rgba(40, 10, 10, 0.5); border: 1px solid #ff4444; border-radius: 10px; padding: 20px; text-align: center; margin-top: 20px;">
                <div style="font-size: 3em;">⛔</div>
                <div style="font-family: 'Orbitron'; color: #ff4444; font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">ACCESO DENEGADO</div>
                <div style="color: #ccc; font-size: 0.9em;">
                    El enlace neuronal con el Oráculo ha sido cortado.<br>
                    La recalibración del sistema es tarea exclusiva de las unidades activas.
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        else:
            st.caption("Valerius necesita recalibrar sus bancos de memoria. Confirma los datos perdidos para ganar AP. **(1 Intento por Día)**")
            
            can_play = True
            msg_wait = ""
            
            last_play_str = None
            try:
                recal_prop = p.get("Ultima Recalibracion")
                if recal_prop:
                    last_play_str = recal_prop.get("date", {}).get("start") 
            except: last_play_str = None

            if last_play_str:
                chile_tz = pytz.timezone('America/Santiago')
                now_chile = datetime.now(chile_tz)
                try:
                    # Parseo robusto
                    if "T" in last_play_str:
                        last_play_dt = datetime.fromisoformat(last_play_str.replace('Z', '+00:00'))
                        # Convertir a Chile si viene en UTC
                        if last_play_dt.tzinfo is None:
                            last_play_dt = pytz.utc.localize(last_play_dt)
                        last_play_dt = last_play_dt.astimezone(chile_tz)
                    else:
                        dt_naive = datetime.strptime(last_play_str, "%Y-%m-%d")
                        last_play_dt = chile_tz.localize(dt_naive)
                    
                    # --- LÓGICA DE RESET A MEDIANOCHE ---
                    # Comparamos solo las FECHAS (Año, Mes, Día)
                    if last_play_dt.date() == now_chile.date():
                        can_play = False
                        # Calculamos tiempo para las 00:00 de mañana
                        manana = now_chile.date() + timedelta(days=1)
                        midnight = chile_tz.localize(datetime.combine(manana, datetime.min.time()))
                        remaining = midnight - now_chile
                        
                        hours, remainder = divmod(remaining.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        msg_wait = f"{hours}h {minutes}m"
                    # ------------------------------------
                except Exception as e:
                    print(f"Error fecha trivia: {e}")
                    can_play = True # Ante la duda, dejar jugar

            if st.session_state.trivia_feedback_mode:
                res = st.session_state.trivia_last_result
                if res['correct']:
                    st.markdown(f"""
                    <div class="feedback-box feedback-correct">
                        <div class="feedback-title" style="color: #00e676;">✅ ¡SISTEMAS ESTABILIZADOS!</div>
                        <div class="feedback-text">Has aportado coherencia a la red.<br>Recompensa: <strong>+{res['reward']} AP</strong></div>
                        <br>
                        <div style="font-size: 0.9em; color: #aaa;">{res['explanation_correct']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="feedback-box feedback-wrong">
                        <div class="feedback-title" style="color: #ff1744;">❌ ERROR DE COHERENCIA</div>
                        <div class="feedback-text">Datos corruptos detectados. La respuesta correcta era la opción <strong>{res['correct_option']}</strong>.</div>
                        <br>
                        <div style="font-size: 0.9em; color: #aaa;">{res['explanation_wrong']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                if st.button("ENTENDIDO, CERRAR CONEXIÓN", use_container_width=True):
                    # 1. Limpieza de estado local
                    st.session_state.trivia_feedback_mode = False
                    st.session_state.trivia_question = None
                    
                    # 2. HACK DE MEMORIA (Optimistic UI):
                    # Inyectamos la fecha de HOY en la sesión local manualmente.
                    # Esto hace que la barra de tiempo aparezca INMEDIATAMENTE al recargar,
                    # sin esperar a que 'actualizar_datos_sesion' traiga el dato de Notion.
                    from datetime import datetime
                    import pytz
                    chile_tz = pytz.timezone('America/Santiago')
                    now_iso = datetime.now(chile_tz).isoformat()
                    
                    if "jugador" in st.session_state and st.session_state.jugador:
                        # Simulamos que la propiedad ya se actualizó
                        if "Ultima Recalibracion" not in st.session_state.jugador:
                            st.session_state.jugador["Ultima Recalibracion"] = {}
                        st.session_state.jugador["Ultima Recalibracion"]["date"] = {"start": now_iso}
                    
                    # 3. Recarga visual inmediata
                    st.rerun() 

            elif not can_play:
                st.info(f"❄️ SISTEMAS RECALIBRANDO. Vuelve en: **{msg_wait}**")
                st.progress(100)

            else:
                if not st.session_state.trivia_question:
                    with st.spinner("Escaneando sectores corruptos..."):
                        q = cargar_pregunta_aleatoria()
                        if q: st.session_state.trivia_question = q
                        else: st.info("Sistemas al 100%. No se requieren reparaciones hoy.")
                
                if st.session_state.trivia_question:
                    q = st.session_state.trivia_question
                    st.markdown(f"""<div class="trivia-container"><div class="trivia-question">{q['pregunta']}</div></div>""", unsafe_allow_html=True)
                    
                    col_a, col_b, col_c = st.columns(3)
                    
                    def handle_choice(choice):
                        is_correct = (choice == q['correcta'])
                        reward = q['recompensa'] if is_correct else 0
                        
                        st.session_state.trivia_feedback_mode = True
                        st.session_state.trivia_last_result = {
                            "correct": is_correct,
                            "reward": reward,
                            "correct_option": q['correcta'],
                            "explanation_correct": q.get("exp_correcta", "Respuesta Correcta."),
                            "explanation_wrong": q.get("exp_incorrecta", "Respuesta Incorrecta.")
                        }
                        
                        # PASAMOS EL ID PÚBLICO AQUÍ vvv
                        procesar_recalibracion(reward, is_correct, q['ref_id'], q.get('public_id'))
                        st.rerun()

                    with col_a:
                        if st.button(f"A) {q['opcion_a']}", use_container_width=True): handle_choice("A")
                    with col_b:
                        if st.button(f"B) {q['opcion_b']}", use_container_width=True): handle_choice("B")
                    with col_c:
                        if st.button(f"C) {q['opcion_c']}", use_container_width=True): handle_choice("C")
 # --- PESTAÑA CÓDIGOS (VERSIÓN 2.0: SOPORTE INSIGNIAS) ---
    with tab_codes:
        st.markdown("### 🔐 PROTOCOLO DE DESENCRIPTACIÓN")
        
        if is_alumni:
            # PANTALLA DE BLOQUEO PARA VETERANOS
            st.markdown("""
            <div style="background: rgba(40, 10, 10, 0.5); border: 1px solid #ff4444; border-radius: 10px; padding: 20px; text-align: center; margin-top: 20px;">
                <div style="font-size: 3em;">⛔</div>
                <div style="font-family: 'Orbitron'; color: #ff4444; font-size: 1.2em; font-weight: bold; margin-bottom: 10px;">ACCESO DENEGADO</div>
                <div style="color: #ccc; font-size: 0.9em;">
                    El Protocolo de Desencriptación está reservado exclusivamente para agentes en servicio activo.<br>
                    Tu credencial de veterano no tiene permisos de escritura en este terminal.
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        else:
            # INTERFAZ NORMAL
            st.caption("Introduce las claves tácticas para desbloquear recursos e insignias secretas.")
            
            # Espacio reservado para animaciones
            animation_spot = st.empty() 
            
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                st.image("https://cdn-icons-png.flaticon.com/512/3064/3064197.png", width=80)
                st.markdown("<br>", unsafe_allow_html=True)
                
                current_key = f"redeem_input_{st.session_state.redeem_key_id}"
                code_input = st.text_input("CLAVE DE ACCESO:", key=current_key, placeholder="X-X-X-X")
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("🔓 DESENCRIPTAR CÓDIGO", use_container_width=True):
                    if code_input:
                        with st.spinner("Verificando firma digital..."):
                            time.sleep(0.5)
                            # Llamamos a la nueva función que retorna 3 valores
                            success, msg, rewards = procesar_codigo_canje(code_input.strip())
                            
                            if success:
                                # --- CASO ÉXITO ---
                                with animation_spot:
                                    ani_hack = cargar_lottie_seguro(ASSETS_LOTTIE["success_hack"])
                                    if ani_hack:
                                        st_lottie(ani_hack, height=300, key=f"anim_{time.time()}")
                                
                                time.sleep(2.0)
                                animation_spot.empty()
                                
                                # Feedback detallado
                                msg_final = f"✅ **ACCESO CONCEDIDO**\n\n"
                                if rewards.get("AP", 0) > 0:
                                    msg_final += f"➕ **{rewards['AP']} AngioPoints** agregados.\n"
                                
                                if rewards.get("Insignia"):
                                    badge_name = rewards["Insignia"]
                                    msg_final += f"🎖️ **¡NUEVA INSIGNIA DESBLOQUEADA!**: {badge_name}"
                                    st.balloons() # ¡Fiesta por la insignia!

                                st.success(msg_final)
                                time.sleep(3)
                                
                                # Reset input y datos
                                st.session_state.redeem_key_id += 1
                                actualizar_datos_sesion()
                            
                            else:
                                # --- CASO ERROR ---
                                with animation_spot:
                                    ani_error = cargar_lottie_seguro(ASSETS_LOTTIE.get("error_hack", "")) 
                                    if ani_error:
                                        st_lottie(ani_error, height=200, key=f"fail_{time.time()}")
                                
                                time.sleep(1.5)
                                animation_spot.empty()
                                st.error(f"{msg}")
                    else:
                        st.warning("⚠️ Ingrese una clave válida.")

    with tab_comms:
        st.markdown("### 📡 TRANSMISIONES DE VALERIUS")
        anuncios = st.session_state.anuncios_data
        
        anuncios_visibles = []
        if anuncios:
            for anuncio in anuncios:
                if es_anuncio_relevante(anuncio, uni_label, ano_label, is_alumni):
                    anuncios_visibles.append(anuncio)

        if not anuncios_visibles:
            st.info("Sin transmisiones en tu frecuencia.")
        else:
            for anuncio in anuncios_visibles:
                # --- LIMPIEZA NEO ---
                fecha_display = parsear_fecha_chile(anuncio['fecha'], "%d/%m/%Y")
                # --------------------

                with st.container():
                    st.markdown(f"""
                    <div style="background: rgba(0, 50, 50, 0.3); border-left: 4px solid var(--primary-color); padding: 15px; border-radius: 5px; margin-bottom: 10px;">
                        <div style="color: var(--primary-color); font-weight: bold; font-family: 'Orbitron'; font-size: 1.1em;">{anuncio['titulo']}</div>
                        <div style="color: #aaa; font-size: 0.8em; margin-bottom: 5px;">{fecha_display}</div>
                        <div style="color: #fff;">{anuncio['contenido']}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        st.markdown("---")
        
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
                # --- LIMPIEZA NEO ---
                fecha_str = parsear_fecha_chile(item['fecha'])
                # --------------------
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
