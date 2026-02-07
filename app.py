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
    # Constantes de Juego
    SESSION_TIMEOUT, NOMBRES_NIVELES, SQUAD_THEMES, BADGE_MAP, THEME_DEFAULT
)

from modules.notion_api import (
    verificar_modo_mantenimiento, registrar_evento_sistema, cargar_datos_jugador,
    cargar_misiones_activas, inscribir_jugador_mision, enviar_solicitud,
    procesar_codigo_canje, cargar_pregunta_aleatoria, procesar_recalibracion,
    cargar_estado_suministros, procesar_suministro,
    cargar_anuncios, procesar_compra_habilidad, cargar_habilidades, 
    procesar_compra_mercado, obtener_miembros_escuadron, registrar_setup_inicial
)

from modules.utils import (
    cargar_lottie_seguro, cargar_imagen_circular, generar_loot, 
    parsear_fecha_chile
)

# Puente de compatibilidad
headers = HEADERS
THEME = THEME_DEFAULT 

st.set_page_config(page_title="Praxis Primoris", page_icon="💠", layout="centered")

# --- 🛡️ MODO MANTENIMIENTO ---
if "maintenance_bypass" not in st.session_state:
    st.session_state.maintenance_bypass = False

if verificar_modo_mantenimiento() and not st.session_state.maintenance_bypass:
    try: ADMIN_PASS = st.secrets["ADMIN_PASSWORD"]
    except: ADMIN_PASS = "admin123"

    st.markdown("""
        <style>
            .stApp { background-color: #1a0505; color: #ff4444; }
            .maintenance-container { 
                display: flex; flex-direction: column; align-items: center; justify-content: center; 
                height: 70vh; text-align: center; font-family: 'Courier New', monospace; 
                border: 2px solid #ff4444; padding: 40px; border-radius: 10px; 
                background: rgba(255, 0, 0, 0.05); box-shadow: 0 0 50px rgba(255, 0, 0, 0.2); 
            }
            .blink { animation: blinker 1.5s linear infinite; font-size: 3em; margin-bottom: 20px; }
            @keyframes blinker { 50% { opacity: 0; } }
        </style>
        <div class="maintenance-container">
            <div class="blink">⛔</div>
            <h1 style="color: #ff4444;">SISTEMAS OFFLINE</h1>
            <p>Protocolo de Mantenimiento Activo.<br>La red Praxis se reiniciará en breve.</p>
        </div>
    """, unsafe_allow_html=True)

    with st.expander("🔐 ACCESO DE EMERGENCIA (ADMIN)"):
        pass_input = st.text_input("Credencial de Mando:", type="password", key="maint_pass")
        if st.button("FORZAR ENTRADA"):
            if pass_input == ADMIN_PASS:
                st.session_state.maintenance_bypass = True
                st.toast("ACCESO DE EMERGENCIA CONCEDIDO", icon="🔓")
                time.sleep(1)
                st.rerun()
            else: st.error("DENEGADO")
    st.stop()

# --- MAPA DE INSIGNIAS ---
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
        
        /* ESTILOS COMUNES */
        .centered-container, .profile-container, .hud-grid, .badge-grid, 
        .energy-core, .rank-table, .log-card, .skill-card-container, .codex-card, .market-card {{
            max-width: 700px; margin-left: auto !important; margin-right: auto !important;
        }}

        /* TICKER */
        .ticker-wrap {{
            width: 100%; overflow: hidden; background-color: rgba(0, 0, 0, 0.6);
            border-top: 1px solid var(--primary-color); border-bottom: 1px solid var(--primary-color);
            white-space: nowrap !important; box-sizing: border-box; height: 35px;
            margin-bottom: 20px; display: flex; align-items: center;
        }}
        .ticker {{ display: inline-block; white-space: nowrap !important; padding-right: 100%; animation: ticker-animation 60s linear infinite; }}
        .ticker-item {{ display: inline-block; padding: 0 2rem; font-size: 0.9em; color: var(--text-highlight); font-family: 'Orbitron', sans-serif; letter-spacing: 1px; }}
        @keyframes ticker-animation {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-100%, 0, 0); }} }}

        /* BOTONES */
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

        /* PERFIL */
        .profile-container {{ 
            background: linear-gradient(180deg, rgba(6, 22, 38, 0.95), rgba(4, 12, 20, 0.98)); 
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 20px; padding: 20px; 
            margin-top: 70px; margin-bottom: 30px; position: relative; 
            box-shadow: 0 10px 40px -10px var(--glow-color); text-align: center;
        }}
        .profile-avatar-wrapper {{ 
            position: absolute; top: -70px; left: 50%; transform: translateX(-50%); 
            width: 160px; height: 160px; border-radius: 50%; padding: 5px; 
            background: var(--bg-dark); border: 2px solid #e0f7fa; 
            box-shadow: 0 0 25px var(--glow-color); z-index: 10; 
        }}
        .profile-avatar {{ width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }}
        .profile-content {{ margin-top: 90px; }}
        .profile-name {{ font-family: 'Orbitron'; font-size: 2.2em; font-weight: 900; color: #fff; text-transform: uppercase; margin-bottom: 5px; text-shadow: 0 0 10px rgba(0,0,0,0.8); }}
        .profile-role {{ color: #b0bec5; font-size: 1.1em; margin-bottom: 15px; font-weight: 400; letter-spacing: 1px; }}
        .profile-role strong {{ color: var(--text-highlight); font-weight: bold; text-transform: uppercase; }}
        .level-badge {{ display: inline-block; background: rgba(0, 0, 0, 0.4); border: 1px solid var(--primary-color); padding: 8px 25px; border-radius: 30px; font-family: 'Orbitron', sans-serif; font-size: 1.4em; font-weight: 700; color: var(--text-highlight); text-shadow: 0 0 15px var(--glow-color); margin-top: 10px; margin-bottom: 20px; box-shadow: 0 0 15px rgba(0,0,0,0.5); }}
        
        /* BARRAS DE PROGRESO */
        .level-progress-wrapper {{ width: 80%; margin: 0 auto 20px auto; }}
        .level-progress-bg {{ background: #1c2e3e; height: 10px; border-radius: 5px; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5); }}
        .level-progress-fill {{ height: 100%; background: #FFD700; border-radius: 5px; box-shadow: 0 0 15px #FFD700; transition: width 1s ease-in-out; }}
        .level-progress-text {{ font-size: 0.8em; color: #aaa; margin-top: 5px; letter-spacing: 1px; }}
        
        /* HUD */
        .hud-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 30px; }}
        .hud-card {{ background: var(--bg-card); border: 1px solid #1c2e3e; border-radius: 15px; padding: 15px; text-align: center; position: relative; overflow: hidden; }}
        .hud-icon {{ width: 40px; height: 40px; object-fit: contain; margin-bottom: 5px; opacity: 0.9; }}
        .epic-number {{ font-family: 'Orbitron'; font-size: 2.5em; font-weight: 900; line-height: 1; margin: 5px 0; text-shadow: 0 0 20px currentColor; }}
        .hud-label {{ font-size: 0.6em; text-transform: uppercase; letter-spacing: 2px; color: #8899a6; font-weight: bold; }}

        /* LOGS */
        .log-card {{ background: rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 4px solid #555; }}
        .log-header {{ display: flex; justify-content: space-between; font-size: 0.8em; color: #aaa; margin-bottom: 5px; }}
        .log-body {{ font-size: 0.95em; color: #fff; margin-bottom: 5px; }}
        .log-reply {{ background: rgba(255, 255, 255, 0.05); padding: 8px; border-radius: 4px; font-size: 0.9em; color: var(--text-highlight); margin-top: 8px; border-left: 2px solid var(--primary-color); }}

        /* MEDIA QUERIES */
        @media (max-width: 768px) {{
            .profile-container {{ margin-top: 50px; }}
            .profile-avatar-wrapper {{ width: 130px; height: 130px; top: -65px; }}
            .profile-name {{ font-size: 1.8em; }}
            .hud-grid {{ gap: 5px; }}
            .hud-card {{ padding: 8px 2px; }}
            .hud-icon {{ width: 30px; height: 30px; margin-bottom: 2px; }}
            .epic-number {{ font-size: 1.6em; margin: 2px 0; }}
            .hud-label {{ font-size: 0.55em; letter-spacing: 1px; }}
        }}
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE SOPORTE ---
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
    W, H = 1080, 1920
    bg_color = '#010204'
    img = Image.new('RGB', (W, H), color=bg_color)
    draw = ImageDraw.Draw(img)
    return io.BytesIO() 

def actualizar_ultima_conexion(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    chile_tz = pytz.timezone('America/Santiago')
    now_iso = datetime.now(chile_tz).isoformat()
    try: requests.patch(url, headers=headers, json={"properties": {"Ultima Conexion": {"date": {"start": now_iso}}}})
    except: pass

def es_anuncio_relevante(anuncio, user_uni, user_year, is_alumni):
    target_uni = anuncio.get("universidad", "Todas")
    match_uni = False
    if isinstance(target_uni, list):
        if "Todas" in target_uni or user_uni in target_uni: match_uni = True
    elif target_uni == "Todas" or target_uni == user_uni: match_uni = True
    if not match_uni: return False

    target_year = anuncio.get("año", "Todas")
    match_year = False
    if not target_year: target_year = "Todas"
    if isinstance(target_year, list):
        if "Todas" in target_year or user_year in target_year: match_year = True
    elif target_year == "Todas" or target_year == user_year: match_year = True
    return match_year

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

# --- CARGADORES DE DATOS ---
@st.cache_data(ttl=3600)
def cargar_habilidades_rol(rol_jugador):
    if not rol_jugador: return []
    return cargar_habilidades(rol_jugador)

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
                    nombre = nom_list[0]["text"]["content"] if nom_list else "Recurso"
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
                    es_dinero_real = props.get("Dinero Real", {}).get("checkbox", False)
                    items.append({"id": r["id"], "nombre": nombre, "costo": costo, "desc": desc, "icon": icon, "es_dinero_real": es_dinero_real})
                except: pass
        return items
    except: return []

def obtener_mis_solicitudes(jugador_nombre):
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {"filter": {"property": "Remitente", "title": {"equals": jugador_nombre}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}], "page_size": 20}
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
                tipo_obj = props.get("Tipo", {}).get("select")
                tipo = tipo_obj["name"] if tipo_obj else "General"
                obs_list = props.get("Observaciones", {}).get("rich_text", [])
                obs = obs_list[0]["text"]["content"] if obs_list else None
                created = r["created_time"]
                fecha_resp = None
                if "Fecha respuesta" in props and props["Fecha respuesta"]["date"]:
                    fecha_resp = props["Fecha respuesta"]["date"]["start"]
                historial.append({"mensaje": mensaje, "status": status, "tipo": tipo, "obs": obs, "fecha": created, "fecha_respuesta": fecha_resp})
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
                    try: nn.append(f"💠 {n['properties']['Mensaje']['title'][0]['text']['content']}")
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

    # ==========================================
    # 🧬 FASE 2: LABORATORIO DE GÉNESIS (SETUP)
    # ==========================================
    props_jugador = st.session_state.jugador.get("properties", {})
    setup_listo = props_jugador.get("Setup_Completo", {}).get("checkbox", False)

    if not setup_listo:
        st.markdown("""
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #00e5ff; font-family: 'Orbitron';">🧬 LABORATORIO DE GÉNESIS</h1>
            <p style="color: #aaa;">"Antes de entrar al Universo AngioMasters, debes forjar tu identidad."</p>
        </div>
        """, unsafe_allow_html=True)

        with st.container(border=True):
            c_config, c_preview = st.columns([1.5, 1])
            with c_config:
                st.subheader("1. Configuración Biométrica")
                nuevo_nick = st.text_input("Nombre en Clave (Nick):", placeholder="Ej: Dr. Strange", key="gen_nick")
                nueva_pass = st.text_input("Crear Contraseña Segura:", type="password", help="Será tu llave de acceso futura.", key="gen_pass")
                st.markdown("---")
                st.subheader("2. Diseño de Avatar")
                estilo_avatar = st.selectbox("Arquetipo Visual:", ["bottts", "avataaars", "lorelei", "notionists", "micah", "identicon"], format_func=lambda x: x.upper(), key="gen_style")
                semilla_base = nuevo_nick if nuevo_nick else "UAM2026"
                semilla = st.text_input("Semilla Genética (Escribe para variar):", value=semilla_base, key="gen_seed")

            avatar_url = f"https://api.dicebear.com/7.x/{estilo_avatar}/svg?seed={semilla}&backgroundColor=b6e3f4,c0aede,d1d4f9"
            
            with c_preview:
                st.markdown("<div style='text-align:center; color:#00e5ff; font-weight:bold;'>VISTA PREVIA</div>", unsafe_allow_html=True)
                st.image(avatar_url, width=250)
                st.caption("👆 Así te verán tus compañeros.")

            st.markdown("---")
            if st.button("💾 FORJAR IDENTIDAD Y ENTRAR", type="primary", use_container_width=True):
                if not nuevo_nick or not nueva_pass:
                    st.error("⚠️ Debes definir tu Nombre y Contraseña.")
                else:
                    with st.spinner("Sincronizando con la Matriz..."):
                        # --- CORRECCIÓN AQUÍ: USAMOS player_page_id ---
                        page_id = st.session_state.player_page_id
                        exito, msg = registrar_setup_inicial(page_id, nuevo_nick, avatar_url, nueva_pass)
                        if exito:
                            st.balloons()
                            st.session_state.jugador["properties"]["Setup_Completo"] = {"checkbox": True}
                            st.session_state.nombre = nuevo_nick 
                            st.success("✅ ¡Identidad Forjada! Bienvenido al servicio.")
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(msg)
        
        st.stop() # DETENER EJECUCIÓN SI NO HAY SETUP

    # ==========================================
    # 🖥️ APP PRINCIPAL
    # ==========================================

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
                if "T" in raw_prev: dt_prev = datetime.fromisoformat(raw_prev.replace('Z', '+00:00'))
                else: dt_prev = chile_tz.localize(datetime.strptime(raw_prev, "%Y-%m-%d"))
                fecha_corte = dt_prev.astimezone(chile_tz)
            except: pass
        if fecha_corte and historial_reciente:
            for req in historial_reciente:
                if req.get('fecha_respuesta'): 
                    try:
                        resp_iso = req['fecha_respuesta']
                        dt_resp = datetime.fromisoformat(resp_iso.replace('Z', '+00:00')).astimezone(pytz.timezone('America/Santiago'))
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

    # --- POPUP ANUNCIO ---
    if not st.session_state.popup_shown and st.session_state.anuncios_data:
        if not is_alumni:
            anuncio_para_mostrar = None
            for anuncio in st.session_state.anuncios_data:
                if es_anuncio_relevante(anuncio, uni_label, ano_label, is_alumni):
                    anuncio_para_mostrar = anuncio
                    break
            if anuncio_para_mostrar:
                st.session_state.popup_shown = True
                fecha_popup = parsear_fecha_chile(anuncio_para_mostrar['fecha'], "%d/%m/%Y")
                with st.expander("🚨 TRANSMISIÓN PRIORITARIA ENTRANTE", expanded=True):
                    st.markdown(f"""<div class="popup-container"><div class="popup-title">{anuncio_para_mostrar['titulo']}</div><div class="popup-body">{anuncio_para_mostrar['contenido']}</div><div class="popup-date">FECHA ESTELAR: {fecha_popup}</div></div>""", unsafe_allow_html=True)
                    if st.button("ENTENDIDO, CERRAR ENLACE"): st.rerun()

    news_text = obtener_noticias()
    st.markdown(f"""<div class="ticker-wrap"><div class="ticker"><div class="ticker-item">{news_text}</div></div></div>""", unsafe_allow_html=True)

    c_head1, c_head2 = st.columns([1.2, 4.8])
    with c_head1: 
        if os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=100)
    with c_head2:
        st.markdown(f"<h2 style='margin:0; font-size:1.8em; line-height:1.2; text-shadow: 0 0 10px {THEME['glow']};'>Hola, {st.session_state.nombre}</h2>", unsafe_allow_html=True)
        st.markdown(textwrap.dedent(f"""<div style="margin-top: 10px; background: rgba(0, 20, 40, 0.5); border-left: 3px solid {THEME['primary']}; padding: 10px; border-radius: 0 10px 10px 0;"><div style="font-family: 'Orbitron', sans-serif; color: {THEME['text_highlight']}; font-size: 0.8em; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 0 0 5px {THEME['glow']};">🌌 MULTIVERSO DETECTADO</div><div style="font-family: 'Orbitron', sans-serif; color: #e0f7fa; font-size: 1.3em; font-weight: bold; text-shadow: 0 0 15px {THEME['glow']}; line-height: 1.1; margin-bottom: 8px;">{uni_label.upper()}</div><div style="display: flex; align-items: center; gap: 10px;"><span style="font-family: 'Orbitron', sans-serif; color: #FFD700; font-size: 1em; font-weight: bold; text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);">⚡ BATALLA {ano_label}</span><span style="border: 1px solid {status_color}; background-color: {status_color}20; padding: 2px 8px; border-radius: 4px; color: {status_color}; font-size: 0.7em; font-weight: bold; letter-spacing: 1px;">{estado_label.upper()}</span></div></div>""").replace('\n', ''), unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    b64_ap = get_img_as_base64("assets/icon_ap.png")

    tab_perfil, tab_ranking, tab_habilidades, tab_misiones, tab_codice, tab_mercado, tab_trivia, tab_codes, tab_comms = st.tabs(["👤 PERFIL", "🏆 RANKING", "⚡ HABILIDADES", "🚀 MISIONES", "📜 CÓDICE", "🛒 MERCADO", "🔮 ORÁCULO", "🔐 CÓDIGOS", "📡 COMUNICACIONES"])    
    
    with tab_perfil:
        if not is_alumni:
            supply_active, supply_filter = cargar_estado_suministros() 
            mi_uni = st.session_state.uni_actual
            puede_farmear = (supply_active and (supply_filter == "Todas" or supply_filter == mi_uni))
            status_t = f"🟢 ENLACE DE SUMINISTROS: ON ({supply_filter})" if puede_farmear else (f"🟡 ENLACE ACTIVO (Solo {supply_filter})" if supply_active else "🔴 ENLACE DE SUMINISTROS: OFF")
            st.caption(status_t)
        
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
        
        progress_html = f"""<div class="level-progress-wrapper"><div class="level-progress-bg"><div class="level-progress-fill" style="width: 100%; background: #FFD700; box-shadow: 0 0 15px #FFD700;"></div></div><div class="level-progress-text" style="color: #FFD700;"><strong>¡NIVEL MÁXIMO ALCANZADO!</strong></div></div>""" if is_max else f"""<div class="level-progress-wrapper"><div class="level-progress-bg"><div class="level-progress-fill" style="width: {prog_pct}%;"></div></div><div class="level-progress-text">Faltan <strong>{faltantes} MP</strong> para el siguiente rango</div></div>"""
        squad_html = f"""<div style="margin-top:25px; border-top:1px solid #1c2e3e; padding-top:20px;"><div style="color:#FFD700; font-size:0.7em; letter-spacing:2px; font-weight:bold; margin-bottom:10px; font-family:'Orbitron';">PERTENECIENTE AL ESCUADRÓN</div><img src="data:image/png;base64,{b64_badge}" style="width:130px; filter:drop-shadow(0 0 15px rgba(0,0,0,0.6));"><div style="color:{THEME['text_highlight']}; font-size:1.2em; letter-spacing:3px; font-weight:bold; margin-top:10px; font-family:'Orbitron';">{skuad.upper()}</div></div>""" if b64_badge else ""
        avatar_div = f'<img src="{avatar_url}" class="profile-avatar">' if avatar_url else '<div style="font-size:80px; line-height:140px;">👤</div>'
        st.markdown(f"""<div class="profile-container"><div class="profile-avatar-wrapper">{avatar_div}</div><div class="profile-content"><div class="profile-name">{st.session_state.nombre}</div><div class="profile-role">Perteneciente a la orden de los <strong>{rol}</strong></div><div class="level-badge">NIVEL {nivel_num}: {nombre_rango.upper()}</div>{progress_html}{squad_html}</div></div>""".replace('\n', ''), unsafe_allow_html=True)
        
        if not is_alumni:
            chile_tz = pytz.timezone('America/Santiago')
            today_chile = datetime.now(chile_tz).date()
            claimed_today = False
            try:
                ls = p.get("Ultimo Suministro", {}).get("date", {}).get("start")
                if ls:
                    dt = datetime.fromisoformat(ls.replace('Z', '+00:00'))
                    if dt.tzinfo is None: dt = pytz.utc.localize(dt)
                    if dt.astimezone(chile_tz).date() == today_chile: claimed_today = True
            except: pass
            if st.session_state.supply_claimed_session: claimed_today = True

            if supply_active and puede_farmear:
                if claimed_today: st.info("✅ Suministros diarios ya reclamados.")
                else:
                    cont = st.empty()
                    with cont.container():
                        st.markdown("""<div class="supply-box"><div class="supply-title">📡 SEÑAL DE SUMINISTROS DETECTADA</div><div class="supply-desc">El Sumo Cartógrafo ha liberado un paquete de ayuda.</div></div>""", unsafe_allow_html=True)
                        if st.button("📦 RECLAMAR SUMINISTROS", use_container_width=True):
                            cont.empty()
                            tier, rewards, icon = generar_loot()
                            if procesar_suministro(tier, rewards):
                                st.session_state.supply_claimed_session = True
                                anim = st.empty()
                                with anim:
                                    ani = cargar_lottie_seguro(ASSETS_LOTTIE.get("loot_legendary" if tier=="Legendario" else "loot_epic", ""))
                                    if ani: st_lottie(ani, height=300, key=f"l_{time.time()}")
                                st.toast(f"SUMINISTRO {tier.upper()}: +{rewards['AP']} AP", icon=icon)
                                time.sleep(2.5)
                                anim.empty()
                                st.info("✅ Suministros reclamados.")
                                if "jugador" in st.session_state:
                                    if "Ultimo Suministro" not in st.session_state.jugador: st.session_state.jugador["Ultimo Suministro"] = {}
                                    st.session_state.jugador["Ultimo Suministro"]["date"] = {"start": datetime.now(chile_tz).isoformat()}
                                time.sleep(1)
                                actualizar_datos_sesion()
                            else: st.error("Error de conexión.")

        c_egg1, c_egg2, c_egg3 = st.columns([1.5, 1, 1.5]) 
        with c_egg2:
            if is_alumni: st.button("⛔ SISTEMA OFFLINE", disabled=True, key="status_alumni", use_container_width=True)
            else:
                if st.button("💠 STATUS DEL SISTEMA", use_container_width=True):
                    now = time.time()
                    if now - st.session_state.last_easter_egg > 60:
                        st.session_state.last_easter_egg = now
                        st.toast(random.choice(SYSTEM_MESSAGES), icon="🤖")
                        if random.random() < 0.1: enviar_solicitud("SISTEMA", "EASTER EGG", f"Usuario {st.session_state.nombre} encontró secreto.", "Sistema")
                    else: st.toast("⚠️ Sistemas de enfriamiento activos.", icon="❄️")
        
        b64_mp = get_img_as_base64("assets/icon_mp.png")
        b64_vp = get_img_as_base64("assets/icon_vp.png")
        st.markdown(textwrap.dedent(f"""<div class="hud-grid"><div class="hud-card" style="border-bottom: 3px solid #FFD700;"><img src="data:image/png;base64,{b64_mp}" class="hud-icon"><div class="epic-number" style="color:#FFD700;">{mp}</div><div class="hud-label">MasterPoints</div></div><div class="hud-card" style="border-bottom: 3px solid #00e5ff;"><img src="data:image/png;base64,{b64_ap}" class="hud-icon"><div class="epic-number" style="color:#00e5ff;">{ap}</div><div class="hud-label">AngioPoints</div></div><div class="hud-card" style="border-bottom: 3px solid #ff4b4b;"><img src="data:image/png;base64,{b64_vp}" class="hud-icon"><div class="epic-number" style="color:#ff4b4b;">{vp}%</div><div class="hud-label">VitaPoints</div></div></div>""").replace('\n', ''), unsafe_allow_html=True)
        
        st.markdown("### 🏅 SALÓN DE LA FAMA")
        try: mis_insignias = [t["name"] for t in p.get("Insignias", {}).get("multi_select", [])]
        except: mis_insignias = []
        if not mis_insignias: st.caption("Aún no tienes insignias.")
        else:
            badge_html = '<div class="badge-grid">'
            for i, bn in enumerate(mis_insignias):
                mid = f"b-{i}"
                ip = BADGE_MAP.get(bn, DEFAULT_BADGE)
                b64 = get_img_as_base64(ip) if os.path.exists(ip) else ""
                cnt = f'<img src="data:image/png;base64,{b64}" class="badge-img">' if b64 else '<div style="font-size:40px;">🏅</div>'
                badge_html += f'<div class="badge-wrapper"><div class="badge-card"><div class="badge-img-container">{cnt}</div><div class="badge-name">{bn}</div></div></div>'
            st.markdown(badge_html + '</div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

    with tab_ranking:
        st.markdown(f"### ⚔️ TOP ASPIRANTES")
        df = st.session_state.ranking_data
        if df is not None and not df.empty:
            max_mp = int(df["MasterPoints"].max()) if df["MasterPoints"].max() > 0 else 1
            tr = ""
            for i, (idx, row) in enumerate(df.head(10).iterrows()):
                pct = (row["MasterPoints"] / max_mp) * 100
                tr += f"""<tr class="rank-row"><td class="rank-cell rank-cell-rank">{i+1}</td><td class="rank-cell"><div style="font-weight:bold; font-size:1.1em; color:#fff;">{row["Aspirante"]}</div><div style="color:#aaa; font-size:0.8em;">{row["Escuadrón"]}</div></td><td class="rank-cell rank-cell-last"><div style="display:flex; flex-direction:column; gap:5px;"><div style="text-align:right; font-family:'Orbitron'; color:#FFD700; font-weight:bold;">{row["MasterPoints"]}</div><div class="bar-bg"><div class="bar-fill" style="width:{pct}%;"></div></div></div></td></tr>"""
            st.markdown(f"""<table class="rank-table">{tr}</table>""", unsafe_allow_html=True)
        else:
            st.info(f"Sin datos.")
            if st.button("🔄 Refrescar"): actualizar_datos_sesion()

    with tab_habilidades:
        st.markdown("""<style>.skill-card-container { display: flex; align-items: stretch; min-height: 120px; background: #0a141f; border: 1px solid #1c2e3e; border-radius: 12px; margin-bottom: 15px; overflow: hidden; transition: 0.3s; margin-top: 5px; } .skill-banner-col { width: 130px; flex-shrink: 0; background: #050810; display: flex; align-items: center; justify-content: center; border-right: 1px solid #1c2e3e; } .skill-content-col { flex-grow: 1; padding: 15px; display: flex; flex-direction: column; justify-content: center; } .skill-cost-col { width: 100px; flex-shrink: 0; background: rgba(255, 255, 255, 0.03); border-left: 1px solid #1c2e3e; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; } .skill-cost-val { font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: #fff; line-height: 1; } .skill-cost-icon { width: 35px; height: 35px; margin-bottom: 5px; filter: drop-shadow(0 0 5px #00e5ff); } @media (max-width: 768px) { .skill-card-container { flex-direction: column !important; height: auto !important; } .skill-banner-col { width: 100% !important; height: 100px !important; border-right: none !important; border-bottom: 1px solid #1c2e3e; } .skill-banner-col img { width: 100%; height: 100%; object-fit: cover; opacity: 0.8; } .skill-content-col { width: 100% !important; padding: 15px !important; } .skill-cost-col { width: 100% !important; border-left: none !important; border-top: 1px solid #1c2e3e; flex-direction: row !important; justify-content: space-between !important; padding: 10px 20px !important; background: rgba(0,0,0,0.4) !important; min-height: 60px !important; } .skill-cost-icon { margin-bottom: 0 !important; margin-right: 10px; } .skill-cost-val { font-size: 1.5em !important; } .skill-cost-col::before { content: "REQUISITO:"; color: #aaa; font-size: 0.8em; letter-spacing: 2px; } }</style>""", unsafe_allow_html=True)
        
        rol_jugador_actual = p.get("Rol", {}).get("select", {}).get("name")
        st.markdown(f"### ⚡ HABILIDADES DE: {rol_jugador_actual.upper() if rol_jugador_actual else 'RECLUTA'}")
        st.markdown(f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">ANGIOPOINTS<br>DISPONIBLES</div></div><div class="energy-val" style="color: #00e5ff; text-shadow: 0 0 15px #00e5ff;">{ap}</div></div>""", unsafe_allow_html=True)

        if is_alumni: st.info("⛔ Mercado cerrado para agentes retirados.")
        elif not rol_jugador_actual: st.warning("⚠️ Sin rol asignado.")
        else:
            skills = cargar_habilidades(rol_jugador_actual)
            if not skills: st.info(f"No hay habilidades para {rol_jugador_actual}.")
            else:
                for item in skills:
                    bloq = nivel_num < item['nivel_req']
                    sin_saldo = ap < item['costo']
                    col = THEME.get('primary', '#00ff9d')
                    bord = col if not bloq else "#444"
                    opac = "1.0" if not bloq else "0.7"
                    gray = "" if not bloq else "filter: grayscale(100%);"
                    img = item['icon_url'] or "https://cdn-icons-png.flaticon.com/512/2646/2646067.png"
                    
                    st.markdown(f"""<div class="skill-card-container" style="border-left: 4px solid {bord}; opacity: {opac}; {gray}"><div class="skill-banner-col"><img src="{img}" style="width: 100%; height: 100%; object-fit: cover; opacity: 0.9;"></div><div class="skill-content-col"><div style="font-family: 'Orbitron'; font-weight: bold; color: #fff; font-size: 1.3em;">{item['nombre']}</div><div style="font-size: 0.95em; color: #b0bec5;">{item['desc']}</div><div style="font-size: 0.8em; color: {bord}; margin-top: 10px; font-weight: bold;">🔒 NIVEL REQUERIDO: {item['nivel_req']}</div></div><div class="skill-cost-col"><img src="data:image/png;base64,{b64_ap}" class="skill-cost-icon"><div class="skill-cost-val" style="text-shadow: 0 0 10px #00e5ff;">{item['costo']}</div></div></div>""", unsafe_allow_html=True)
                    
                    c_f, c_b = st.columns([1.5, 1.5])
                    with c_b:
                        if bloq: st.button(f"🔒 NVL {item['nivel_req']}", disabled=True, key=f"lk_{item['id']}", use_container_width=True)
                        elif sin_saldo: st.button(f"💸 FALTA AP", disabled=True, key=f"noap_{item['id']}", use_container_width=True)
                        else:
                            with st.popover("⚡ ACTIVAR", use_container_width=True):
                                st.markdown(f"**{item['nombre']}** - Costo: {item['costo']} AP")
                                if st.button("🚀 EJECUTAR", key=f"btn_{item['id']}", type="primary", use_container_width=True):
                                    with st.spinner("Procesando..."):
                                        ok, msg = procesar_compra_habilidad(item['nombre'], item['costo'], 0, item['id'])
                                        if ok:
                                            st.toast("SOLICITUD ENVIADA", icon="✅")
                                            time.sleep(2)
                                            st.rerun()
                                        else: st.error(msg)

    with tab_misiones:
        # --- CSS TÁCTICO MISIONES ---
        st.markdown("""<style>.mission-card { background: linear-gradient(135deg, #0f1520 0%, #050810 100%); border: 1px solid #333; border-radius: 12px; padding: 0; margin-bottom: 20px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.3); } .mission-header { padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); background: rgba(0,0,0,0.2); } .mission-title { font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 1.2em; color: #fff; text-transform: uppercase; display: flex; align-items: center; gap: 10px; } .mission-narrative { background: rgba(0, 229, 255, 0.05); color: #00e5ff; font-style: italic; font-size: 0.85em; padding: 8px 20px; border-bottom: 1px dashed rgba(0, 229, 255, 0.2); } .mission-body { padding: 15px 20px; color: #b0bec5; font-size: 0.95em; line-height: 1.5; } .rewards-box { background: rgba(0,0,0,0.3); margin: 0 20px 15px 20px; padding: 10px; border-radius: 8px; border: 1px solid #333; display: flex; align-items: center; gap: 15px; } .reward-badge-img { width: 50px; height: 50px; object-fit: contain; filter: drop-shadow(0 0 5px #FFD700); } .reward-text { font-size: 0.9em; color: #e0e0e0; font-family: monospace; letter-spacing: 0.5px; } .mission-footer { background: rgba(0, 0, 0, 0.4); padding: 10px 20px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid rgba(255,255,255,0.05); } .mission-timer { font-family: monospace; font-size: 0.85em; color: #aaa; display: flex; align-items: center; gap: 5px; } .mission-status { font-weight: bold; font-size: 0.8em; letter-spacing: 1px; text-transform: uppercase; } .sync-bar-bg { width: 100%; height: 10px; background: #2a2a2a; border-radius: 5px; margin-top: 8px; overflow: hidden; border: 1px solid #444; } .sync-bar-fill { height: 100%; background: #e040fb; box-shadow: 0 0 15px #e040fb; transition: width 0.5s ease; } .sync-label { font-family: 'Orbitron'; font-size: 0.85em; color: #e040fb; margin-top: 5px; display: flex; justify-content: space-between; font-weight: bold; text-shadow: 0 0 5px rgba(224, 64, 251, 0.3); }</style>""", unsafe_allow_html=True)

        st.markdown("### 🚀 CENTRO DE OPERACIONES")
        if is_alumni: st.info("⛔ Acceso restringido.")
        else:
            misiones = cargar_misiones_activas()
            mi_escuadron = []
            if any(m['tipo'] == "Misión" for m in misiones):
                mi_escuadron = obtener_miembros_escuadron(st.session_state.squad_name, st.session_state.uni_actual, st.session_state.ano_actual)
            
            chile_tz = pytz.timezone('America/Santiago')
            now_chile = datetime.now(chile_tz)

            if not misiones: st.info("📡 Radar vacío.")
            else:
                for m in misiones:
                    tg = m.get("target_unis", ["Todas"])
                    if "Todas" not in tg and st.session_state.uni_actual not in tg: continue
                    
                    dt_ap = None
                    if m['f_apertura']: dt_ap = datetime.fromisoformat(m['f_apertura'].replace('Z', '+00:00')).astimezone(chile_tz)
                    dt_ci = None
                    if m['f_cierre']: dt_ci = datetime.fromisoformat(m['f_cierre'].replace('Z', '+00:00')).astimezone(chile_tz)
                    dt_lz = None
                    if m['f_lanzamiento']: dt_lz = datetime.fromisoformat(m['f_lanzamiento'].replace('Z', '+00:00')).astimezone(chile_tz)

                    insc = [x.strip() for x in m['inscritos'].split(",") if x.strip()]
                    joined = st.session_state.nombre in insc
                    
                    is_group = (m['tipo'] == "Misión")
                    icon = "🧬" if is_group else ("🌋" if m['tipo'] == "Expedición" else "⚔️")
                    bor = "#e040fb" if is_group else ("#bf360c" if m['tipo']=="Expedición" else "#FFD700")
                    
                    st.markdown(f"""<div class="mission-card" style="border-left: 5px solid {bor};"><div class="mission-header"><div class="mission-title">{icon} {m['nombre']}</div></div><div class="mission-narrative">"{m['narrativa']}"</div><div class="mission-body">{m['descripcion']}</div><div class="rewards-box"><div><div class="reward-text">{m['recompensas_txt']}</div></div></div><div class="mission-footer"><div class="mission-timer">⏳ {dt_lz.strftime('%d/%m %H:%M') if dt_lz else 'TBA'}</div></div></div>""", unsafe_allow_html=True)
                    
                    if is_group:
                        conf = [p for p in insc if p in mi_escuadron]
                        tot = len(mi_escuadron) if mi_escuadron else 1
                        pct = int((len(conf)/tot)*100)
                        st.markdown(f"""<div class="sync-bar-bg"><div class="sync-bar-fill" style="width: {pct}%;"></div></div><div class="sync-label"><span>SINCRONIZACIÓN {pct}%</span><span>({len(conf)}/{tot})</span></div><br>""", unsafe_allow_html=True)
                        c1, c2 = st.columns([2,1])
                        with c1:
                            if pct >= 100: 
                                st.success("✅ SINCRONIZADO")
                                with st.expander("🔓 ACCESO"):
                                    st.write(f"Clave: {m['password']}")
                                    st.write(f"[Link]({m['link']})")
                            else: st.info("⏳ Esperando...")
                        with c2:
                            if not joined:
                                if st.button("🫡 CONFIRMAR", key=f"s_{m['id']}", type="primary", use_container_width=True):
                                    inscribir_jugador_mision(m['id'], m['inscritos'], st.session_state.nombre, m['nombre'])
                                    cargar_misiones_activas.clear()
                                    st.rerun()
                            else: st.button("✅ LISTO", disabled=True, key=f"r_{m['id']}", use_container_width=True)
                    else:
                        if not joined:
                            with st.popover("📝 INSCRIBIRME", use_container_width=True):
                                st.warning(m['advertencia'])
                                if st.button("🚀 ACEPTAR", key=f"j_{m['id']}", type="primary"):
                                    inscribir_jugador_mision(m['id'], m['inscritos'], st.session_state.nombre, m['nombre'])
                                    cargar_misiones_activas.clear()
                                    st.rerun()
                        else:
                            if dt_lz and now_chile >= dt_lz:
                                st.success("🟢 EN CURSO")
                                with st.expander("📂 ACCESO"):
                                    st.write(f"Clave: {m['password']}")
                                    st.write(f"[Link]({m['link']})")
                            else: st.info("✅ INSCRITO")

    with tab_codice:
        st.markdown("### 📜 ARCHIVOS")
        if is_alumni: st.error("⛔ Acceso denegado.")
        else:
            q = st.text_input("🔍 Buscar:", label_visibility="collapsed")
            fil = []
            for i in st.session_state.codice_data:
                if q.lower() in i["nombre"].lower(): fil.append(i)
            
            if not fil: st.info("Sin registros.")
            else:
                for i in fil:
                    locked = nivel_num < i["nivel"]
                    col = "#666" if locked else "#00e5ff"
                    op = "0.6" if locked else "1"
                    txt = f"🔒 NIVEL {i['nivel']}" if locked else "ACCEDER"
                    
                    html = f"""<div style="background:#0a141f; border:1px solid #333; border-left:4px solid {col}; opacity:{op}; padding:15px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;"><div><div style="font-family:'Orbitron'; color:#fff; font-size:1.1em;">{i['nombre']}</div><div style="color:#aaa; font-size:0.9em;">{i['descripcion']}</div></div><div><a href="{i['url']}" target="_blank" style="padding:8px 15px; background:{col}; color:#000; text-decoration:none; font-weight:bold; border-radius:4px;">{txt}</a></div></div>"""
                    st.markdown(html, unsafe_allow_html=True)

    with tab_mercado:
        st.markdown("""<style>.market-card-responsive { display: flex; align-items: stretch; min-height: 100px; background: linear-gradient(90deg, #0f1520 0%, #050810 100%); border: 1px solid #333; border-radius: 12px; margin-bottom: 15px; overflow: hidden; transition: 0.3s; box-shadow: 0 4px 10px rgba(0,0,0,0.3); } .market-icon-col { width: 100px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; background: rgba(0,0,0,0.2); font-size: 2.5em; border-right: 1px solid #333; } .market-info-col { flex-grow: 1; padding: 15px; display: flex; flex-direction: column; justify-content: center; } .market-cost-col { width: 120px; flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; border-left: 1px solid #333; background: rgba(0,0,0,0.2); } .inventory-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 15px; margin-top: 20px; } .inventory-item { background: #0a1018; border: 1px solid #333; border-radius: 8px; padding: 10px; text-align: center; position: relative; overflow: hidden; } .inv-icon { font-size: 2em; margin-bottom: 5px; } .inv-name { font-family: 'Orbitron'; font-size: 0.8em; color: #fff; line-height: 1.2; max-height: 40px; overflow: hidden; } .inv-date { font-size: 0.6em; color: #666; margin-top: 5px; } @media (max-width: 768px) { .market-card-responsive { flex-direction: column; height: auto; } .market-icon-col { width: 100%; height: 80px; border-right: none; border-bottom: 1px solid #333; } .market-info-col { width: 100%; padding: 15px; } .market-cost-col { width: 100%; border-left: none; border-top: 1px solid #333; flex-direction: row; justify-content: space-between; padding: 10px 20px; min-height: 50px; background: rgba(0,0,0,0.4); } .market-cost-col::before { content: "VALOR:"; color: #aaa; font-size: 0.8em; letter-spacing: 2px; } }</style>""", unsafe_allow_html=True)
        st.markdown("### 🛒 MERCADO")
        st.markdown(f"""<div class="energy-core"><div class="energy-left"><img src="data:image/png;base64,{b64_ap}" class="energy-icon-large"><div class="energy-label">ENERGÍA<br>DISPONIBLE</div></div><div class="energy-val" style="color: #00e5ff; text-shadow: 0 0 15px #00e5ff;">{ap}</div></div>""", unsafe_allow_html=True)
        
        mkt = st.session_state.market_data
        if not mkt: st.info("Mercado vacío.")
        else:
            for item in mkt:
                real = item.get("es_dinero_real", False)
                excl = "[EX]" in item['nombre'] or "[ALUMNI]" in item['nombre']
                show = True
                if is_alumni and not (excl or real): show = False
                elif not is_alumni and excl: show = False
                
                if show:
                    col = "#FFD700" if real else "#00e5ff"
                    cost_txt = f"${item['costo']:,}" if real else str(item['costo'])
                    mon = "CLP" if real else "AP"
                    can_buy = True if real else (ap >= item['costo'])
                    
                    st.markdown(f"""<div class="market-card-responsive" style="border-left: 4px solid {col};"><div class="market-icon-col" style="color:{col};">{item['icon']}</div><div class="market-info-col"><div style="font-family:'Orbitron'; font-size:1.1em; color:#fff;">{item['nombre']}</div><div style="font-size:0.9em; color:#aaa;">{item['desc']}</div></div><div class="market-cost-col"><div style="font-family:'Orbitron'; font-weight:bold; font-size:1.4em; color:{col};">{cost_txt}</div><div style="font-size:0.7em; color:#888;">{mon}</div></div></div>""", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns([2,1])
                    with c2:
                        if not can_buy: st.button("💸 FALTA SALDO", disabled=True, key=f"nf_{item['id']}", use_container_width=True)
                        else:
                            with st.popover("ADQUIRIR", use_container_width=True):
                                st.write(f"¿Comprar {item['nombre']}?")
                                if st.button("🚀 CONFIRMAR", key=f"bm_{item['id']}", type="primary"):
                                    ok, msg = procesar_compra_mercado(item['nombre'], item['costo'], real)
                                    if ok: 
                                        st.toast("ENVIADO", icon="✅")
                                        time.sleep(1)
                                        actualizar_datos_sesion()
                                    else: st.error(msg)
            
            st.markdown("---")
            st.markdown("### 🎒 INVENTARIO")
            inv = []
            hist = obtener_mis_solicitudes(st.session_state.nombre)
            for h in hist:
                if h['status'] in ["Aprobado", "Entregado"]:
                    msg = h['mensaje'].lower()
                    if "compra" in msg or "mercado" in msg:
                        name = h['mensaje'].split(":")[1].strip() if ":" in h['mensaje'] else h['mensaje']
                        inv.append({"n": name, "f": parsear_fecha_chile(h['fecha']), "i": "📦"})
            
            if not inv: st.info("Vacío.")
            else:
                html = '<div class="inventory-grid">'
                for x in inv: html += f'<div class="inventory-item"><div class="inv-icon">{x["i"]}</div><div class="inv-name">{x["n"]}</div><div class="inv-date">{x["f"]}</div></div>'
                st.markdown(html + '</div>', unsafe_allow_html=True)

    with tab_trivia:
        st.markdown("### 🔮 ORÁCULO")
        if is_alumni: st.error("⛔ Acceso denegado.")
        else:
            can_play = True
            try:
                lr = p.get("Ultima Recalibracion", {}).get("date", {}).get("start")
                if lr:
                    ld = datetime.fromisoformat(lr.replace('Z', '+00:00')).astimezone(pytz.timezone('America/Santiago')).date()
                    if ld == datetime.now(pytz.timezone('America/Santiago')).date(): can_play = False
            except: pass
            
            if st.session_state.trivia_feedback_mode:
                res = st.session_state.trivia_last_result
                if res['correct']: st.success(f"✅ CORRECTO (+{res['reward']} AP)")
                else: st.error(f"❌ INCORRECTO. Era: {res['correct_option']}")
                st.write(res['explanation_correct'] if res['correct'] else res['explanation_wrong'])
                if st.button("CERRAR"):
                    st.session_state.trivia_feedback_mode = False
                    st.session_state.trivia_question = None
                    if "jugador" in st.session_state:
                        if "Ultima Recalibracion" not in st.session_state.jugador: st.session_state.jugador["Ultima Recalibracion"] = {}
                        st.session_state.jugador["Ultima Recalibracion"]["date"] = {"start": datetime.now(pytz.timezone('America/Santiago')).isoformat()}
                    st.rerun()
            elif not can_play: st.info("❄️ Vuelve mañana.")
            else:
                if not st.session_state.trivia_question:
                    q = cargar_pregunta_aleatoria()
                    if q: st.session_state.trivia_question = q
                    else: st.info("Sin preguntas.")
                
                if st.session_state.trivia_question:
                    q = st.session_state.trivia_question
                    st.markdown(f"**{q['pregunta']}**")
                    c1, c2, c3 = st.columns(3)
                    def ans(opt):
                        cor = (opt == q['correcta'])
                        rw = q['recompensa'] if cor else 0
                        st.session_state.trivia_feedback_mode = True
                        st.session_state.trivia_last_result = {"correct": cor, "reward": rw, "correct_option": q['correcta'], "explanation_correct": q.get("exp_correcta",""), "explanation_wrong": q.get("exp_incorrecta","")}
                        procesar_recalibracion(rw, cor, q['ref_id'], q.get('public_id'))
                        st.rerun()
                    with c1: st.button(f"A) {q['opcion_a']}", on_click=ans, args=("A",), use_container_width=True)
                    with c2: st.button(f"B) {q['opcion_b']}", on_click=ans, args=("B",), use_container_width=True)
                    with c3: st.button(f"C) {q['opcion_c']}", on_click=ans, args=("C",), use_container_width=True)

    with tab_codes:
        st.markdown("### 🔐 CÓDIGOS")
        if is_alumni: st.error("⛔ Acceso denegado.")
        else:
            k = st.text_input("CLAVE:", key=f"k_{st.session_state.redeem_key_id}")
            if st.button("DESENCRIPTAR", use_container_width=True):
                if k:
                    ok, msg, rw = procesar_codigo_canje(k.strip())
                    if ok:
                        txt = f"✅ ÉXITO. +{rw.get('AP',0)} AP."
                        if rw.get("Insignia"):
                            txt += f" 🎖️ Insignia: {rw['Insignia']}"
                            st.balloons()
                        st.success(txt)
                        st.session_state.redeem_key_id += 1
                        time.sleep(2)
                        actualizar_datos_sesion()
                    else: st.error(msg)

    with tab_comms:
        st.markdown("### 📡 COMUNICACIONES")
        av = [a for a in st.session_state.anuncios_data if es_anuncio_relevante(a, uni_label, ano_label, is_alumni)]
        if not av: st.info("Sin transmisiones.")
        else:
            for a in av:
                st.markdown(f"""<div style="background: rgba(0, 50, 50, 0.3); border-left: 4px solid {THEME['primary']}; padding: 15px; border-radius: 5px; margin-bottom: 10px;"><div style="color: {THEME['primary']}; font-weight: bold; font-family: 'Orbitron';">{a['titulo']}</div><div style="color: #aaa; font-size: 0.8em;">{parsear_fecha_chile(a['fecha'], '%d/%m/%Y')}</div><div style="color: #fff;">{a['contenido']}</div></div>""", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 📨 ENVIAR MENSAJE")
        if is_alumni: st.warning("Modo lectura.")
        else:
            with st.form("msg_f", clear_on_submit=True):
                sub = st.text_input("Asunto:")
                bod = st.text_area("Mensaje:")
                if st.form_submit_button("ENVIAR"):
                    if sub and bod:
                        if enviar_solicitud("MENSAJE", sub, bod, st.session_state.nombre): st.toast("✅ Enviado"); st.rerun()
                        else: st.error("Error.")
        
        st.markdown("---")
        st.markdown("#### 📂 BITÁCORA")
        mh = obtener_mis_solicitudes(st.session_state.nombre)
        if not mh: st.caption("Vacío.")
        else:
            with st.container(height=500, border=True):
                for i in mh:
                    col, ic = ("#00e676", "✅") if i['status']=="Aprobado" else (("#ff1744", "❌") if i['status']=="Rechazado" else ("#00e5ff", "📩") if i['status']=="Respondido" else ("#999", "⏳"))
                    st.markdown(f"""<div class="log-card" style="border-left-color: {col};"><div class="log-header"><span>{parsear_fecha_chile(i['fecha'])}</span><span style="color:{col}; font-weight:bold;">{ic} {i['status'].upper()}</span></div><div class="log-body">{i['mensaje']}</div>{f'<div class="log-reply">🗣️ <strong>COMANDO:</strong> {i["obs"]}</div>' if i["obs"] else ''}</div>""", unsafe_allow_html=True)

    # --- ZONA DE CONTROL (SOLO VISIBLE SI HAY SESIÓN) ---
    st.markdown("<br>", unsafe_allow_html=True)
    c_refresh, c_logout = st.columns([1, 1])
    
    with c_refresh:
        if st.button("🔄 ACTUALIZAR", use_container_width=True, key="btn_refresh_bottom"):
            actualizar_datos_sesion()
            
    with c_logout:
        if st.button("🚪 SALIR", type="primary", use_container_width=True, key="btn_logout_bottom"):
            cerrar_sesion()

# --- FOOTER UNIVERSAL (SIEMPRE VISIBLE AL FINAL) ---
st.markdown("""
    <div class="footer">
        PRAXIS PRIMORIS SYSTEM v1.0 <br> OPERADO POR SUMO CARTÓGRAFO - VALERIUS
    </div>
""", unsafe_allow_html=True)
