import streamlit as st
import requests
import pandas as pd

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

st.set_page_config(page_title="Universo AngioMasters", page_icon="🫀", layout="centered")

# --- DICCIONARIO DE NIVELES (LORE) ---
NOMBRES_NIVELES = {
    1: "🧪 Aprendiz",
    2: "🚀 Navegante",
    3: "🎯 Caza Arterias",
    4: "🔍 Clarividente",
    5: "👑 AngioMaster"
}

# --- CSS: ESTÉTICA CYBER-MEDICAL ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        
        /* FUENTES Y COLORES GLOBALES */
        h1, h2, h3, [data-testid="stMetricLabel"] { font-family: 'Orbitron', sans-serif !important; letter-spacing: 1px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #0E1117; }
        
        /* LIMPIEZA DE INTERFAZ */
        .block-container { padding-top: 1.5rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { display: none !important; }
        
        /* TARJETA DE PERFIL (GLASSMORPHISM) */
        .profile-card {
            background: linear-gradient(135deg, rgba(30,30,30,0.9), rgba(20,20,20,0.9));
            border: 1px solid #444;
            border-top: 4px solid #990000;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        .avatar-img {
            width: 130px; height: 130px; border-radius: 50%; object-fit: cover;
            border: 3px solid #FF4B4B; margin-bottom: 15px;
            box-shadow: 0 0 15px rgba(255, 75, 75, 0.5);
        }
        
        /* MÉTRICAS (HUD) */
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2.2rem !important; color: #fff; }
        [data-testid="stMetricLabel"] { color: #aaa; font-size: 0.9rem !important; }
        div[data-testid="metric-container"] {
            background-color: #161920;
            border: 1px solid #333;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            transition: transform 0.2s;
        }
        div[data-testid="metric-container"]:hover {
            border-color: #990000;
            transform: translateY(-3px);
            box-shadow: 0 4px 10px rgba(153, 0, 0, 0.2);
        }
        
        /* TARJETAS DE HABILIDAD */
        .skill-card {
            background-color: #1A1A1A; border: 1px solid #333;
            border-radius: 10px; padding: 20px; margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        .skill-card:hover { border-color: #990000; box-shadow: 0 0 15px rgba(153,0,0,0.2); transform: translateX(5px); }
        .skill-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .skill-cost { background-color: #222; color: #FFD700; padding: 5px 10px; border-radius: 20px; font-family: 'Orbitron', sans-serif; font-size: 0.8em; border: 1px solid #555; }
        
        /* PESTAÑAS PERSONALIZADAS */
        .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
        .stTabs [data-baseweb="tab"] {
            background-color: #1E1E1E; border-radius: 4px; color: #aaa; border: 1px solid #333; flex-grow: 1; justify-content: center;
        }
        .stTabs [aria-selected="true"] {
            background-color: #990000 !important; color: white !important; border-color: #FF4B4B !important;
        }
        
        /* BOTONES */
        .stButton>button { width: 100%; border-radius: 6px; background: linear-gradient(90deg, #800000, #990000); color: white; border: none; padding: 12px 24px; font-weight: bold; font-family: 'Orbitron', sans-serif; transition: all 0.3s; }
        .stButton>button:hover { background: linear-gradient(90deg, #990000, #BB0000); box-shadow: 0 0 20px rgba(187, 0, 0, 0.4); }
        .stButton button:disabled { background: #222; color: #555; cursor: not-allowed; border: 1px solid #333; }
        
        /* ALERTA */
        .stAlert { background-color: #1E1E1E; border: 1px solid #333; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- CABECERA DE MARCA ---
c_logo, c_texto = st.columns([1, 6])
with c_logo:
    st.markdown("# 🛡️") # Si tienes un logo.png, usa st.image("logo.png")
with c_texto:
    st.markdown("<h1 style='margin-bottom:0; padding-bottom:0;'>UNIVERSO ANGIOMASTERS</h1>", unsafe_allow_html=True)
    st.caption("PLATAFORMA DE GAMIFICACIÓN CLÍNICA | HEMODINAMIA IV")

st.divider()

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "login_error" not in st.session_state: st.session_state.login_error = None
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None
if "habilidades_data" not in st.session_state: st.session_state.habilidades_data = []

if "uni_actual" not in st.session_state: st.session_state.uni_actual = None
if "ano_actual" not in st.session_state: st.session_state.ano_actual = None

# --- FUNCIONES LÓGICAS (MISMAS QUE ANTES) ---

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
                    nombre = props["Habilidad"]["title"][0]["text"]["content"]
                    costo = props["Costo AP"]["number"]
                    nivel_req = props["Nivel Requerido"]["number"]
                    desc_obj = props.get("Descripcion", {}).get("rich_text", [])
                    descripcion = desc_obj[0]["text"]["content"] if desc_obj else "Sin descripción"
                    habilidades.append({
                        "id": item["id"], "nombre": nombre, "costo": costo,
                        "nivel_req": nivel_req, "descripcion": descripcion
                    })
                except: pass
        return habilidades
    except: return []

def solicitar_activacion_habilidad(nombre_habilidad, costo, jugador_nombre):
    url = "https://api.notion.com/v1/pages"
    nuevo_mensaje = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Remitente": {"title": [{"text": {"content": f"SOLICITUD: {jugador_nombre}"}}]},
            "Mensaje": {"rich_text": [{"text": {"content": f"Desea activar: '{nombre_habilidad}' (Costo: {costo} AP). Contexto: {st.session_state.uni_actual} {st.session_state.ano_actual}"}}]}
        }
    }
    res = requests.post(url, headers=headers, json=nuevo_mensaje)
    return res.status_code == 200

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
                try:
                    val = miembro["properties"]["MP"]["number"]
                    if val: total_mp += val
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
                    lista.append({"Agente": nombre, "Escuadrón": escuadron, "MasterPoints": mp})
                except: pass
            
            df = pd.DataFrame(lista)
            if not df.empty:
                df = df.sort_values(by="MasterPoints", ascending=False).reset_index(drop=True)
                df.index += 1 
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
                        except: 
                            st.session_state.uni_actual = None; st.session_state.ano_actual = None

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

# ================= UI PRINCIPAL =================

if not st.session_state.jugador:
    with st.container():
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("login_form"):
            st.markdown("### 🔐 INICIO DE SESIÓN")
            st.text_input("Codename (Usuario):", placeholder="Ej: Neo", key="input_user")
            st.text_input("Password:", type="password", key="input_pass")
            st.form_submit_button("CONECTAR AL SISTEMA", on_click=validar_login)
    
    if st.session_state.login_error:
        st.error(st.session_state.login_error)

else:
    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Sin Asignar"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "????"

    # --- BARRA DE ESTADO SUPERIOR ---
    st.markdown(f"""
    <div style="display:flex; justify-content:space-between; color:#666; font-size:0.8em; margin-bottom:10px;">
        <span>📍 UBICACIÓN: {uni_label}</span>
        <span>📅 CICLO: {ano_label}</span>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.uni_actual or not st.session_state.ano_actual:
        st.warning("⚠️ Tu perfil no tiene Universidad o Año asignado. El ranking no funcionará.")

    # --- PESTAÑAS DE NAVEGACIÓN ---
    tab_perfil, tab_ranking, tab_habilidades = st.tabs(["👤 PERFIL", "🏆 RANKING", "⚡ HABILIDADES"])
    
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
        try: vp = int(p.get("VP", {}).get("number", 1))
        except: vp = 0
        
        # Tarjeta de Perfil
        st.markdown(f"""
        <div class="profile-card">
            {'<img src="' + avatar_url + '" class="avatar-img">' if avatar_url else '<div style="font-size:80px;">👤</div>'}
            <h2 style="margin:0; color:#FF4B4B; text-transform: uppercase;">{st.session_state.nombre}</h2>
            <h3 style="margin:5px 0; color:white; font-size:1.1em;">{skuad} | {rol}</h3>
            <div style="margin-top:10px; display:inline-block; background:#333; padding:5px 15px; border-radius:20px; border:1px solid #FFD700; color:#FFD700;">
                Nivel {nivel_num}: {nombre_rango}
            </div>
        </div>
        """, unsafe_allow_html=True)
            
        # HUD Stats
        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ MP (XP)", mp)
        c2.metric("⚡ AP (Poder)", ap)
        c3.metric("❤️ VP (Salud)", f"{vp}%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("CERRAR SESIÓN", on_click=cerrar_sesion)

    # --- TAB 2: RANKING ---
    with tab_ranking:
        st.markdown(f"### ⚔️ TOP AGENTES")
        df = st.session_state.ranking_data
        
        if df is not None and not df.empty:
            st.dataframe(
                df.head(10), 
                use_container_width=True,
                column_config={
                    "MasterPoints": st.column_config.ProgressColumn(
                        "XP Total", format="%d", min_value=0, max_value=int(df["MasterPoints"].max())
                    ),
                }
            )
            st.markdown("### 🛡️ GUERRA DE ESCUADRONES")
            df_squads = df.groupby("Escuadrón")["MasterPoints"].sum().reset_index().sort_values(by="MasterPoints", ascending=False)
            st.bar_chart(df_squads, x="Escuadrón", y="MasterPoints", color="#990000")
        else:
            st.info(f"No hay datos registrados en {uni_label} ({ano_label}).")
            if st.button("🔄 Refrescar"):
                st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                st.rerun()

    # --- TAB 3: HABILIDADES ---
    with tab_habilidades:
        st.markdown(f"### 📜 Grimorio del {rol}")
        st.caption(f"Tus AP disponibles: **{ap}**")
        habilidades = st.session_state.habilidades_data
        
        if not habilidades:
            st.info("No hay habilidades disponibles para tu Rol.")
        else:
            for hab in habilidades:
                nombre = hab["nombre"]
                costo = hab["costo"]
                nivel_req = hab["nivel_req"]
                desc = hab["descripcion"]
                
                desbloqueada = nivel_num >= nivel_req
                puede_pagar = ap >= costo
                
                with st.container():
                    # Lógica visual de bloqueado/desbloqueado
                    border_color = "#990000" if desbloqueada else "#444"
                    opacity = "1" if desbloqueada else "0.5"
                    grayscale = "" if desbloqueada else "filter: grayscale(100%);"
                    
                    st.markdown(f"""
                    <div class="skill-card" style="border-left: 5px solid {border_color}; opacity: {opacity}; {grayscale}">
                        <div class="skill-header">
                            <h3 style="margin:0; color:white; font-size:1.1em;">{nombre}</h3>
                            <span class="skill-cost">⚡ {costo} AP</span>
                        </div>
                        <p style="color:#ccc; font-size:0.9em; margin:0;">{desc}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_btn, col_msg = st.columns([1, 2])
                    with col_btn:
                        if desbloqueada:
                            if st.button(f"ACTIVAR", key=f"btn_{hab['id']}"):
                                if puede_pagar:
                                    exito = solicitar_activacion_habilidad(nombre, costo, st.session_state.nombre)
                                    if exito:
                                        st.toast(f"✅ Solicitud enviada.", icon="🔥")
                                        st.balloons()
                                    else: st.error("Error de comunicación")
                                else: st.toast("❌ AP Insuficientes", icon="⚠️")
                        else:
                            nombre_req = NOMBRES_NIVELES.get(nivel_req, f"Nivel {nivel_req}")
                            st.button(f"🔒 Req: {nombre_req}", disabled=True, key=f"lk_{hab['id']}")
