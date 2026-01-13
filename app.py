import streamlit as st
import requests
import pandas as pd
import os
import base64
import textwrap
import time 
from datetime import datetime
import pytz

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_HABILIDADES_ID = st.secrets["DB_HABILIDADES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
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

# --- CSS: ESTÉTICA BLUE NEON (RESPONSIVE) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Roboto:wght@300;400;700&display=swap');
        
        /* GENERAL */
        h1, h2, h3, h4, h5 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 1px; color: #00e5ff !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #050810; color: #e0f7fa; }
        .block-container { padding-top: 1rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
        
        .stButton>button { width: 100%; border-radius: 8px; background: linear-gradient(90deg, #006064, #00bcd4); color: white; border: none; font-family: 'Orbitron'; font-weight:bold; text-transform: uppercase; letter-spacing: 1px; transition: 0.3s; }
        .stButton>button:hover { transform: scale(1.02); box-shadow: 0 0 15px #00e5ff; }
        .stTabs [aria-selected="true"] { background-color: rgba(0, 229, 255, 0.1) !important; color: #00e5ff !important; border: 1px solid #00e5ff !important; }
        
        /* ESTILOS RESPONSIVE */
        .profile-container { background: linear-gradient(180deg, rgba(6, 22, 38, 0.95), rgba(4, 12, 20, 0.98)); border: 1px solid #004d66; border-radius: 20px; padding: 20px; margin-top: 70px; margin-bottom: 30px; position: relative; box-shadow: 0 0 50px rgba(0, 229, 255, 0.05); text-align: center; }
        .profile-avatar-wrapper { position: absolute; top: -70px; left: 50%; transform: translateX(-50%); width: 160px; height: 160px; border-radius: 50%; padding: 5px; background: #050810; border: 2px solid #00e5ff; box-shadow: 0 0 25px rgba(0, 229, 255, 0.7); z-index: 10; }
        .profile-avatar { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
        .profile-content { margin-top: 90px; }
        .profile-name { font-family: 'Orbitron'; font-size: 2.2em; font-weight: 900; color: #fff; text-transform: uppercase; margin-bottom: 5px; }
        .profile-role { color: #4dd0e1; font-size: 1em; margin-bottom: 15px; }
        
        .hud-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px; margin-bottom: 30px; }
        .hud-card { background: rgba(10, 25, 40, 0.7); border: 1px solid #1c2e3e; border-radius: 15px; padding: 15px; text-align: center; position: relative; overflow: hidden; }
        .hud-icon { width: 40px; height: 40px; object-fit: contain; margin-bottom: 5px; opacity: 0.9; }
        .epic-number { font-family: 'Orbitron'; font-size: 2.5em; font-weight: 900; line-height: 1; margin: 5px 0; text-shadow: 0 0 20px currentColor; }
        .hud-label { font-size: 0.6em; text-transform: uppercase; letter-spacing: 2px; color: #8899a6; font-weight: bold; }

        .skill-card-container { display: flex; align-items: stretch; min-height: 120px; background: #0a141f; border: 1px solid #1c2e3e; border-radius: 12px; margin-bottom: 15px; overflow: hidden; transition: 0.3s; }
        .skill-banner-col { width: 130px; flex-shrink: 0; background: #050810; display: flex; align-items: center; justify-content: center; border-right: 1px solid #1c2e3e; }
        .skill-banner-img { width: 100%; height: 100%; object-fit: cover; }
        .skill-content-col { flex-grow: 1; padding: 15px; display: flex; flex-direction: column; justify-content: center; }
        .skill-cost-col { width: 100px; flex-shrink: 0; background: rgba(0, 229, 255, 0.05); border-left: 1px solid #1c2e3e; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px; }
        .skill-cost-icon { width: 35px; height: 35px; margin-bottom: 5px; }
        .skill-cost-val { font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: #fff; line-height: 1; }
        
        .rank-table { width: 100%; border-collapse: separate; border-spacing: 0 8px; }
        .rank-row { background: linear-gradient(90deg, rgba(15,30,50,0.8), rgba(10,20,30,0.6)); }
        .rank-cell { padding: 12px 15px; color: #e0f7fa; vertical-align: middle; border-top: 1px solid #1c2e3e; border-bottom: 1px solid #1c2e3e; }
        .rank-cell-rank { border-left: 1px solid #1c2e3e; border-top-left-radius: 8px; border-bottom-left-radius: 8px; font-weight: bold; color: #00e5ff; font-family: 'Orbitron'; font-size: 1.2em; width: 50px; text-align: center; }
        .rank-cell-last { border-right: 1px solid #1c2e3e; border-top-right-radius: 8px; border-bottom-right-radius: 8px; width: 40%; }
        .bar-bg { background: #0f1520; height: 8px; border-radius: 4px; width: 100%; margin-right: 10px; overflow: hidden; }
        .bar-fill { height: 100%; background-color: #FFD700; border-radius: 4px; box-shadow: 0 0 10px #FFD700; }

        /* LOG DE COMUNICACIONES */
        .log-card {
            background: rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; margin-bottom: 10px; border-left: 4px solid #555;
        }
        .log-header { display: flex; justify-content: space-between; font-size: 0.8em; color: #aaa; margin-bottom: 5px; }
        .log-body { font-size: 0.95em; color: #fff; margin-bottom: 5px; }
        .log-reply { background: rgba(0, 229, 255, 0.1); padding: 8px; border-radius: 4px; font-size: 0.9em; color: #4dd0e1; margin-top: 8px; border-left: 2px solid #00e5ff; }

        @media (max-width: 768px) {
            .profile-container { margin-top: 50px; }
            .profile-avatar-wrapper { width: 130px; height: 130px; top: -65px; }
            .profile-name { font-size: 1.8em; }
            .hud-grid { gap: 5px; }
            .hud-card { padding: 8px 2px; }
            .hud-icon { width: 30px; height: 30px; margin-bottom: 2px; }
            .epic-number { font-size: 1.6em; margin: 2px 0; }
            .hud-label { font-size: 0.55em; letter-spacing: 1px; }
            .skill-card-container { min-height: 100px; }
            .skill-banner-col { width: 60px; }
            .skill-content-col { padding: 10px; }
            .skill-cost-col { width: 70px; padding: 5px; }
            .skill-cost-icon { width: 25px; height: 25px; }
            .skill-cost-val { font-size: 1.4em; }
            .rank-cell { padding: 8px 5px; font-size: 0.9em; }
            .rank-cell-rank { width: 30px; font-size: 1em; }
        }
    </style>
""", unsafe_allow_html=True)

# --- SISTEMA DE LOGOUT AUTOMÁTICO ---
if "last_active" not in st.session_state:
    st.session_state.last_active = time.time()

if st.session_state.get("jugador") is not None:
    if time.time() - st.session_state.last_active > SESSION_TIMEOUT:
        st.session_state.jugador = None
        st.session_state.clear()
        st.rerun()
    else:
        st.session_state.last_active = time.time()

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "login_error" not in st.session_state: st.session_state.login_error = None
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None
if "habilidades_data" not in st.session_state: st.session_state.habilidades_data = []
if "uni_actual" not in st.session_state: st.session_state.uni_actual = None
if "ano_actual" not in st.session_state: st.session_state.ano_actual = None
if "estado_uam" not in st.session_state: st.session_state.estado_uam = None

# --- HELPERS ---
def get_img_as_base64(file_path):
    if not os.path.exists(file_path): return ""
    with open(file_path, "rb") as f: data = f.read()
    return base64.b64encode(data).decode()

def find_squad_image(squad_name):
    if not squad_name: return None
    clean_name = squad_name.lower().strip().replace(" ", "_")
    candidates = [
        f"assets/{clean_name}_team.png", f"assets/{clean_name}.png", f"assets/{clean_name}.jpg",
        f"{clean_name}_team.png", f"{clean_name}.png"
    ]
    for path in candidates:
        if os.path.exists(path): return path
    return None

# --- FUNCIONES LÓGICAS ---
def calcular_nivel_usuario(mp):
    if mp <= 50: return 1
    elif mp <= 150: return 2
    elif mp <= 300: return 3
    elif mp <= 500: return 4
    else: return 5

def cargar_habilidades_rol(rol_jugador):
    if not rol_jugador: return []
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
                        if files:
                            icon_url = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")

                    habilidades.append({
                        "id": item["id"], "nombre": nombre, "costo": costo,
                        "nivel_req": nivel_req, "descripcion": descripcion, "icon_url": icon_url
                    })
                except Exception as e: pass
        return habilidades
    except: return []

# --- FUNCIÓN UNIFICADA DE MENSAJERÍA ---
def enviar_solicitud(tipo, titulo_msg, cuerpo_msg, jugador_nombre):
    url = "https://api.notion.com/v1/pages"
    
    if tipo == "HABILIDAD":
        texto_final = f"{titulo_msg} | Costo: {cuerpo_msg}"
        tipo_select = "Poder"
    else:
        texto_final = f"{titulo_msg} - {cuerpo_msg}"
        tipo_select = "Mensaje"

    # Manejo seguro de contexto (por si no está logueado)
    if "uni_actual" in st.session_state and st.session_state.uni_actual:
        uni = st.session_state.uni_actual
    else:
        uni = "Sin Asignar"
        
    if "ano_actual" in st.session_state and st.session_state.ano_actual:
        ano = st.session_state.ano_actual
    else:
        ano = "Sin Año"

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

# --- NUEVA FUNCIÓN: OBTENER HISTORIAL DE MIS SOLICITUDES ---
def obtener_mis_solicitudes(jugador_nombre):
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {
        "filter": {"property": "Remitente", "title": {"equals": jugador_nombre}},
        "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        "page_size": 15 
    }
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
                
                historial.append({
                    "mensaje": mensaje,
                    "status": status,
                    "obs": obs,
                    "fecha": created
                })
            except: pass
    return historial

def obtener_puntaje_equipo_filtrado(nombre_escuadron, uni, ano):
    if not nombre_escuadron or not uni or not ano: return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Nombre Escuadrón", "rich_text": {"equals": nombre_escuadron}},
                {"property": "Universidad", "select": {"equals": uni}},
                {"property": "Año", "select": {"equals": ano}}
            ]
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        total_mp = 0
        if res.status_code == 200:
            for miembro in res.json()["results"]:
                try: val = miembro["properties"]["MP"]["number"]; total_mp += val if val else 0
                except: pass
        return total_mp
    except: return 0

def cargar_ranking_filtrado(uni, ano):
    if not uni or not ano: return pd.DataFrame()
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Universidad", "select": {"equals": uni}},
                {"property": "Año", "select": {"equals": ano}}
            ]
        }
    }
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
            if not df.empty:
                df = df.sort_values(by="MasterPoints", ascending=False).reset_index(drop=True)
            return df
    except: return pd.DataFrame()
    return pd.DataFrame()

# --- LOGIN ---
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
                    c_obj = props.get("Clave", {}).get("rich_text", [])
                    c_real = c_obj[0]["text"]["content"] if c_obj else ""
                    if clave == c_real:
                        st.session_state.jugador = props
                        st.session_state.nombre = usuario
                        st.session_state.login_error = None
                        try:
                            uni_data = props.get("Universidad", {}).get("select")
                            st.session_state.uni_actual = uni_data["name"] if uni_data else None
                            ano_data = props.get("Año", {}).get("select")
                            st.session_state.ano_actual = ano_data["name"] if ano_data else None
                            estado_data = props.get("Estado UAM", {}).get("select")
                            st.session_state.estado_uam = estado_data["name"] if estado_data else "Desconocido"
                        except: 
                            st.session_state.uni_actual = None; st.session_state.ano_actual = None
                            st.session_state.estado_uam = "Desconocido"
                        sq_name = "Sin Escuadrón"
                        try:
                            sq_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                            if sq_obj: sq_name = sq_obj[0]["text"]["content"]
                        except: pass
                        st.session_state.squad_name = sq_name
                        st.session_state.team_stats = obtener_puntaje_equipo_filtrado(sq_name, st.session_state.uni_actual, st.session_state.ano_actual)
                        st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                        try:
                            rol_data = props.get("Rol", {}).get("select")
                            rol_usuario = rol_data["name"] if rol_data else None
                        except: rol_usuario = None
                        if rol_usuario:
                            st.session_state.habilidades_data = cargar_habilidades_rol(rol_usuario)
                    else: st.session_state.login_error = "❌ CLAVE INCORRECTA"
                except Exception as e: st.session_state.login_error = f"Error Credenciales: {e}"
            else: st.session_state.login_error = "❌ USUARIO NO ENCONTRADO"
        else: st.session_state.login_error = "⚠️ Error de conexión"
    except Exception as e: st.session_state.login_error = f"Error técnico: {e}"

def cerrar_sesion():
    st.session_state.jugador = None
    st.session_state.ranking_data = None
    st.session_state.habilidades_data = []
    st.session_state.uni_actual = None
    st.session_state.ano_actual = None
    st.session_state.estado_uam = None

# ================= UI PRINCIPAL =================

if not st.session_state.jugador:
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
        
        # --- BLOQUE DE RECUPERACIÓN (NUEVO) ---
        with st.expander("🆘 ¿Problemas de Acceso?"):
            st.caption("Si olvidaste tu clave, solicita un reinicio al comando.")
            with st.form("reset_form", clear_on_submit=True):
                reset_user = st.text_input("Ingresa tu Usuario (Aspirante):")
                if st.form_submit_button("SOLICITAR REINICIO DE CLAVE"):
                    if reset_user:
                        with st.spinner("Enviando señal de auxilio..."):
                            time.sleep(1)
                            # Enviar como mensaje general
                            ok = enviar_solicitud("MENSAJE", "SOLICITUD DE RESET", f"El usuario {reset_user} solicita cambio de clave.", reset_user)
                            if ok:
                                st.success("✅ Solicitud enviada. Contacta a tu profesor.")
                            else:
                                st.error("Error al conectar con la base de datos.")
                    else:
                        st.warning("Ingresa tu nombre de usuario.")

    if st.session_state.login_error: st.error(st.session_state.login_error)

else:
    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Ubicación Desconocida"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "Ciclo ?"
    estado_label = st.session_state.estado_uam if st.session_state.estado_uam else "Desconocido"
    
    status_color = "#00e5ff"
    if estado_label == "Finalizado": status_color = "#ff4b4b"
    elif estado_label == "Sin empezar": status_color = "#FFD700"

    # Header
    c_head1, c_head2 = st.columns([1.2, 4.8])
    with c_head1: 
        if os.path.exists("assets/logo.png"): st.image("assets/logo.png", width=100)
    with c_head2:
        st.markdown(f"<h2 style='margin:0; font-size:1.8em; line-height:1.2; text-shadow: 0 0 10px rgba(0, 229, 255, 0.3);'>Hola, {st.session_state.nombre}</h2>", unsafe_allow_html=True)
        
        header_html = textwrap.dedent(f"""
            <div style="margin-top: 10px; background: rgba(0, 20, 40, 0.5); border-left: 3px solid #00e5ff; padding: 10px; border-radius: 0 10px 10px 0;">
                <div style="font-family: 'Orbitron', sans-serif; color: #4dd0e1; font-size: 0.8em; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 5px; text-shadow: 0 0 5px rgba(0, 229, 255, 0.5);">🌌 MULTIVERSO DETECTADO</div>
                <div style="font-family: 'Orbitron', sans-serif; color: #e0f7fa; font-size: 1.3em; font-weight: bold; text-shadow: 0 0 15px rgba(0, 229, 255, 0.6); line-height: 1.1; margin-bottom: 8px;">
                    {uni_label.upper()}
                </div>
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-family: 'Orbitron', sans-serif; color: #FFD700; font-size: 1em; font-weight: bold; text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);">⚡ BATALLA {ano_label}</span>
                    <span style="border: 1px solid {status_color}; background-color: {status_color}20; padding: 2px 8px; border-radius: 4px; color: {status_color}; font-size: 0.7em; font-weight: bold; letter-spacing: 1px;">{estado_label.upper()}</span>
                </div>
            </div>
        """).replace('\n', '')
        st.markdown(header_html, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ASSETS
    b64_ap = get_img_as_base64("assets/icon_ap.png")

    tab_perfil, tab_ranking, tab_habilidades, tab_comms = st.tabs(["👤 PERFIL", "🏆 RANKING", "⚡ HABILIDADES", "📡 COMUNICACIONES"])
    
    # --- TAB 1: PERFIL ---
    with tab_perfil:
        avatar_url = None
        try:
            f_list = p.get("Avatar", {}).get("files", [])
            if f_list:
                if "file" in f_list[0]: avatar_url = f_list[0]["file"]["url"]
                elif "external" in f_list[0]: avatar_url = f_list[0]["external"]["url"]
        except: pass
        try: rol = p.get("Rol", {}).get("select")["name"]
        except: rol = "Sin Rol"
        skuad = st.session_state.squad_name
        
        img_path = find_squad_image(skuad)
        b64_badge = get_img_as_base64(img_path) if img_path else ""
        try: vp = int(p.get("VP", {}).get("number", 1))
        except: vp = 0
        
        squad_html = ""
        if b64_badge:
            squad_html = f"""<div style="margin-top:25px; border-top:1px solid #1c2e3e; padding-top:20px;"><div style="color:#FFD700; font-size:0.7em; letter-spacing:2px; font-weight:bold; margin-bottom:10px; font-family:'Orbitron';">PERTENECIENTE AL ESCUADRÓN</div><img src="data:image/png;base64,{b64_badge}" style="width:130px; filter:drop-shadow(0 0 15px rgba(0,229,255,0.6));"><div style="color:#4dd0e1; font-size:1.2em; letter-spacing:3px; font-weight:bold; margin-top:10px; font-family:'Orbitron';">{skuad.upper()}</div></div>"""
        
        avatar_div = f'<img src="{avatar_url}" class="profile-avatar">' if avatar_url else '<div style="font-size:80px; line-height:140px;">👤</div>'
        
        profile_html = f"""
        <div class="profile-container">
            <div class="profile-avatar-wrapper">{avatar_div}</div>
            <div class="profile-content">
                <div class="profile-name">{st.session_state.nombre}</div>
                <div class="profile-role">Perteneciente a la orden de los {rol}</div>
                <div class="level-badge">NIVEL {nivel_num}: {nombre_rango.upper()}</div>
                {squad_html}
            </div>
        </div>
        """.replace('\n', '')
        
        st.markdown(profile_html, unsafe_allow_html=True)
        
        b64_mp = get_img_as_base64("assets/icon_mp.png")
        b64_vp = get_img_as_base64("assets/icon_vp.png")
        
        hud_html = textwrap.dedent(f"""
            <div class="hud-grid">
                <div class="hud-card" style="border-bottom: 3px solid #FFD700;">
                    <img src="data:image/png;base64,{b64_mp}" class="hud-icon">
                    <div class="epic-number" style="color:#FFD700;">{mp}</div>
                    <div class="hud-label">MasterPoints</div>
                </div>
                <div class="hud-card" style="border-bottom: 3px solid #00e5ff;">
                    <img src="data:image/png;base64,{b64_ap}" class="hud-icon">
                    <div class="epic-number" style="color:#00e5ff;">{ap}</div>
                    <div class="hud-label">AngioPoints</div>
                </div>
                <div class="hud-card" style="border-bottom: 3px solid #ff4b4b;">
                    <img src="data:image/png;base64,{b64_vp}" class="hud-icon">
                    <div class="epic-number" style="color:#ff4b4b;">{vp}%</div>
                    <div class="hud-label">VitaPoints</div>
                </div>
            </div>
        """).replace('\n', '')
        st.markdown(hud_html, unsafe_allow_html=True)
        st.button("DESCONECTAR", on_click=cerrar_sesion)

    # --- TAB 2: RANKING ---
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
            else:
                st.info("Sin datos de escuadrones.")
        else:
            st.info(f"Sin datos en el sector {uni_label}.")
            if st.button("🔄 Refrescar Señal"):
                st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                st.rerun()

    # --- TAB 3: HABILIDADES ---
    with tab_habilidades:
        st.markdown(f"### 📜 HABILIDADES: {rol.upper()}")
        st.caption(f"ENERGÍA DISPONIBLE: **{ap} AP**")
        habilidades = st.session_state.habilidades_data
        if not habilidades:
            st.info("Sin datos en el Grimorio.")
        else:
            for hab in habilidades:
                nombre = hab["nombre"]
                costo = hab["costo"]
                nivel_req = hab["nivel_req"]
                desc = hab["descripcion"]
                icon_url = hab.get("icon_url")
                
                desbloqueada = nivel_num >= nivel_req
                puede_pagar = ap >= costo
                
                with st.container():
                    border_color = "#00e5ff" if desbloqueada else "#1c2630"
                    opacity = "1" if desbloqueada else "0.5"
                    grayscale = "" if desbloqueada else "filter: grayscale(100%);"
                    
                    banner_html = f'<img src="{icon_url}" class="skill-banner-img">' if icon_url else '<div class="skill-banner-placeholder">💠</div>'
                    
                    ap_icon_html = f'<img src="data:image/png;base64,{b64_ap}" class="skill-cost-icon">'

                    card_html = f"""<div class="skill-card-container" style="border-left: 4px solid {border_color}; opacity: {opacity}; {grayscale}"><div class="skill-banner-col">{banner_html}</div><div class="skill-content-col"><div class="skill-title">{nombre}</div><p class="skill-desc">{desc}</p></div><div class="skill-cost-col">{ap_icon_html}<div class="skill-cost-val">{costo}</div><div class="skill-cost-label">AP</div></div></div>"""
                    
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    c_btn, _ = st.columns([1, 2])
                    with c_btn:
                        if desbloqueada:
                            if st.button(f"ACTIVAR", key=f"btn_{hab['id']}"):
                                if puede_pagar:
                                    # UX: SPINNER
                                    with st.spinner("Conjurando habilidad..."):
                                        time.sleep(1.5)
                                        exito = enviar_solicitud("HABILIDAD", nombre, str(costo), st.session_state.nombre)
                                        if exito:
                                            st.toast(f"✅ Ejecutado: {nombre}", icon="💠")
                                        else: 
                                            st.error("Error de enlace. Verifica la base de Solicitudes.")
                                else: st.toast("❌ Energía Insuficiente", icon="⚠️")
                        else:
                            nombre_req = NOMBRES_NIVELES.get(nivel_req, f"Nivel {nivel_req}")
                            st.button(f"🔒 Req: {nombre_req}", disabled=True, key=f"lk_{hab['id']}")

    # --- TAB 4: COMUNICACIONES ---
    with tab_comms:
        st.markdown("### 📨 ENLACE DIRECTO AL COMANDO")
        st.info("Utiliza este canal para reportar problemas, solicitar revisiones o comunicarte con el alto mando.")
        
        # FIX: SPINNER + DELAY + CLEAN
        with st.form("comms_form_tab", clear_on_submit=True):
            msg_subject = st.text_input("Asunto / Razón:", placeholder="Ej: Duda sobre mi puntaje")
            msg_body = st.text_area("Mensaje:", placeholder="Escribe aquí tu reporte...")
            
            if st.form_submit_button("📡 TRANSMITIR MENSAJE"):
                if msg_subject and msg_body:
                    with st.spinner("Estableciendo enlace encriptado con la base..."):
                        time.sleep(1.5) 
                        ok = enviar_solicitud("MENSAJE", msg_subject, msg_body, st.session_state.nombre)
                        if ok:
                            st.toast("✅ Transmisión Enviada y recibida en la Central.", icon="📡")
                            time.sleep(1) # Esperar indexado
                            st.rerun() # Refrescar para ver el mensaje abajo
                        else:
                            st.error("❌ Error de señal. Verifica las columnas en Notion.")
                else:
                    st.warning("⚠️ Debes llenar Asunto y Mensaje.")
        
        st.markdown("---")
        st.markdown("#### 📂 BITÁCORA DE COMUNICACIONES")
        
        mi_historial = obtener_mis_solicitudes(st.session_state.nombre)
        
        if not mi_historial:
            st.caption("No hay registros de comunicaciones previas.")
        else:
            for item in mi_historial:
                status_color = "#999"
                icon = "⏳"
                if item["status"] == "Aprobado":
                    status_color = "#00e676"; icon = "✅"
                elif item["status"] == "Rechazado":
                    status_color = "#ff1744"; icon = "❌"
                elif item["status"] == "Respuesta":
                    status_color = "#00e5ff"; icon = "📩"
                
                try:
                    utc_dt = datetime.fromisoformat(item['fecha'].replace('Z', '+00:00'))
                    chile_tz = pytz.timezone('America/Santiago')
                    local_dt = utc_dt.astimezone(chile_tz)
                    fecha_str = local_dt.strftime("%d/%m/%Y %H:%M")
                except: fecha_str = "Fecha desc."

                log_html = f"""
                <div class="log-card" style="border-left-color: {status_color};">
                    <div class="log-header">
                        <span>{fecha_str}</span>
                        <span style="color:{status_color}; font-weight:bold;">{icon} {item['status'].upper()}</span>
                    </div>
                    <div class="log-body">{item['mensaje']}</div>
                    {f'<div class="log-reply">🗣️ <strong>COMANDO:</strong> {item["obs"]}</div>' if item["obs"] else ''}
                </div>
                """
                st.markdown(log_html, unsafe_allow_html=True)
