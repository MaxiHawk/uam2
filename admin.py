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

# --- CSS: ESTÉTICA GAMER ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
        .block-container { padding-top: 2rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { display: none !important; }
        
        /* PERFIL */
        .profile-card {
            background: linear-gradient(145deg, #1e1e1e, #2d2d2d);
            border: 2px solid #990000; border-radius: 15px; padding: 20px;
            text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        .avatar-img {
            width: 120px; height: 120px; border-radius: 50%; object-fit: cover;
            border: 4px solid #FF4B4B; margin-bottom: 10px;
        }
        /* HABILIDADES */
        .skill-card {
            background-color: #1A1A1A; border: 1px solid #333;
            border-radius: 10px; padding: 15px; margin-bottom: 15px;
            transition: transform 0.2s;
        }
        .skill-card:hover { border-color: #990000; transform: translateY(-2px); }
        .skill-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .skill-cost { background-color: #333; color: #FFD700; padding: 4px 8px; border-radius: 5px; font-family: 'Orbitron', sans-serif; font-size: 0.9em; }
        
        /* GENERAL */
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem !important; }
        .stButton>button { width: 100%; border-radius: 8px; background-color: #990000; color: white; border: none; padding: 10px 24px; font-weight: bold; font-family: 'Orbitron', sans-serif; }
        .stButton>button:hover { background-color: #FF0000; }
        .stButton button:disabled { background-color: #333333; color: #666666; cursor: not-allowed; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
c1, c2 = st.columns([1,5])
with c1: st.markdown("# 🛡️")
with c2: 
    st.markdown("# ANGIOMASTERS")
    st.caption("Sistema de Gestión RPG - Hemodinamia IV")
st.divider()

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "login_error" not in st.session_state: st.session_state.login_error = None
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None
if "habilidades_data" not in st.session_state: st.session_state.habilidades_data = []

# Variables de Contexto (Universo)
if "uni_actual" not in st.session_state: st.session_state.uni_actual = None
if "ano_actual" not in st.session_state: st.session_state.ano_actual = None

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

# --- FUNCIONES DE FILTRADO POR UNIVERSO (NUEVO) ---

def obtener_puntaje_equipo_filtrado(nombre_escuadron, uni, ano):
    """Suma puntos SOLO del escuadrón en esa Universidad y Año"""
    if not nombre_escuadron or not uni or not ano: return 0
    
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    # Filtro Compuesto (AND)
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
    """Carga ranking SOLO de la Universidad y Año del jugador"""
    if not uni or not ano: return pd.DataFrame()
    
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    # Filtro Compuesto (AND)
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
                        
                        # --- DETECTAR UNIVERSO (UNI + AÑO) ---
                        try:
                            uni_data = props.get("Universidad", {}).get("select")
                            st.session_state.uni_actual = uni_data["name"] if uni_data else None
                            
                            ano_data = props.get("Año", {}).get("select")
                            st.session_state.ano_actual = ano_data["name"] if ano_data else None
                        except: 
                            st.session_state.uni_actual = None
                            st.session_state.ano_actual = None

                        # Validar si tiene contexto asignado
                        if not st.session_state.uni_actual or not st.session_state.ano_actual:
                            st.warning("⚠️ Tu perfil no tiene asignada Universidad o Año en la Base de Datos. Contacta al profesor.")
                        
                        # Datos Escuadrón (Filtrado por contexto)
                        sq_name = "Sin Escuadrón"
                        try:
                            sq_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                            if sq_obj: sq_name = sq_obj[0]["text"]["content"]
                        except: pass
                        st.session_state.squad_name = sq_name
                        
                        # Cargar Stats de Equipo (FILTRADO)
                        st.session_state.team_stats = obtener_puntaje_equipo_filtrado(
                            sq_name, st.session_state.uni_actual, st.session_state.ano_actual
                        )
                        
                        # Cargar Ranking Global (FILTRADO)
                        st.session_state.ranking_data = cargar_ranking_filtrado(
                            st.session_state.uni_actual, st.session_state.ano_actual
                        )
                        
                        # Cargar Habilidades
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

# ================= UI =================

if not st.session_state.jugador:
    with st.form("login_form"):
        st.markdown("### 🔐 ACCESO A LA MATRIX")
        st.text_input("Codename:", placeholder="Ej: Neo", key="input_user")
        st.text_input("Password:", type="password", key="input_pass")
        st.form_submit_button("INICIAR SISTEMA", on_click=validar_login)
    if st.session_state.login_error: st.error(st.session_state.login_error)

else:
    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    
    # Header con contexto
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Sin Uni"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "????"
    st.caption(f"📍 Conectado a: **{uni_label} - Generación {ano_label}**")

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
        
        try:
            r_data = p.get("Rol", {}).get("select")
            rol = r_data["name"] if r_data else "Sin Rol"
        except: rol = "Sin Rol"
        
        skuad = st.session_state.squad_name
        try: 
            vp_raw = p.get("VP", {}).get("number", 1) or 0
            vp = int(vp_raw) # Asumimos entero puro ya
        except: vp = 0
        
        with st.container():
            html_avatar = f"""
            <div class="profile-card">
                {'<img src="' + avatar_url + '" class="avatar-img">' if avatar_url else '<div style="font-size:80px;">👤</div>'}
                <h2 style="margin:0; color:#FF4B4B;">{st.session_state.nombre}</h2>
                <h3 style="margin:5px 0; color:white;">{skuad} | {rol}</h3>
                <p style="color:#aaa;">Nivel {nivel_num}: {nombre_rango}</p>
            </div>
            """
            st.markdown(html_avatar, unsafe_allow_html=True)
            
        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ MP", mp)
        c2.metric("⚡ AP", ap)
        c3.metric("❤️ VP", f"{vp}%")
        
        st.divider()
        st.button("CERRAR SESIÓN", on_click=cerrar_sesion)

    # --- TAB 2: RANKING (FILTRADO) ---
# --- TAB 2: RANKING (FILTRADO) ---
    with tab_ranking:
        # --- CÓDIGO DE DIAGNÓSTICO (BORRAR LUEGO) ---
        with st.expander("🕵️‍♂️ Inspector de Filtros"):
            st.write(f"Tu Universidad detectada: **{st.session_state.uni_actual}**")
            st.write(f"Tu Año detectado: **{st.session_state.ano_actual}**")
            st.info("La tabla de abajo solo debería mostrar jugadores que coincidan EXACTAMENTE con estos dos valores.")
        # ---------------------------------------------

        st.markdown(f"### ⚔️ TOP AGENTES ({uni_label} {ano_label})")
        # ... (sigue el resto del código igual)        st.markdown(f"### ⚔️ TOP AGENTES ({uni_label} {ano_label})")
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
            st.info("No hay datos para este Universo (Universidad/Año).")
            if st.button("🔄 Refrescar"):
                st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                st.rerun()

    # --- TAB 3: HABILIDADES ---
    with tab_habilidades:
        st.markdown(f"### 📜 Grimorio del {rol}")
        st.caption(f"Tus AP disponibles: **{ap}**")
        habilidades = st.session_state.habilidades_data
        
        if not habilidades:
            st.info("No se encontraron habilidades para tu Rol.")
        else:
            for hab in habilidades:
                nombre = hab["nombre"]
                costo = hab["costo"]
                nivel_req = hab["nivel_req"]
                desc = hab["descripcion"]
                
                desbloqueada = nivel_num >= nivel_req
                puede_pagar = ap >= costo
                
                with st.container():
                    border_color = "#990000" if desbloqueada else "#555"
                    opacity = "1" if desbloqueada else "0.6"
                    
                    st.markdown(f"""
                    <div class="skill-card" style="border-left: 5px solid {border_color}; opacity: {opacity};">
                        <div class="skill-header">
                            <h3 style="margin:0; color:white;">{nombre}</h3>
                            <span class="skill-cost">⚡ {costo} AP</span>
                        </div>
                        <p style="color:#ccc; font-size:0.9em;">{desc}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_btn, col_msg = st.columns([1, 3])
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
