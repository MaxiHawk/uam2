import streamlit as st
import requests
import pandas as pd
import os

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

st.set_page_config(page_title="Praxis Primoris", page_icon="💠", layout="centered")

# --- DICCIONARIO DE NIVELES ---
NOMBRES_NIVELES = {
    1: "🧪 Aprendiz",
    2: "🚀 Navegante",
    3: "🎯 Caza Arterias",
    4: "🔍 Clarividente",
    5: "👑 AngioMaster"
}

# --- CSS: ESTÉTICA BLUE NEON / PRAXIS PRIMORIS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        
        /* FUENTES Y FONDO */
        h1, h2, h3, h4, h5 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 1px; color: #00e5ff !important; text-shadow: 0 0 10px rgba(0, 229, 255, 0.3); }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; background-color: #050810; color: #e0f7fa; }
        
        /* LIMPIEZA */
        .block-container { padding-top: 0rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"] { display: none !important; }
        
        /* TARJETA DE PERFIL (BLUE GLASS) */
        .profile-card {
            background: linear-gradient(135deg, rgba(5, 20, 40, 0.9), rgba(0, 10, 20, 0.95));
            border: 1px solid #004d66;
            border-top: 3px solid #00e5ff;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.1);
        }
        .avatar-img {
            width: 120px; height: 120px; border-radius: 50%; object-fit: cover;
            border: 3px solid #00e5ff; margin-bottom: 10px;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.6);
        }
        
        /* CUSTOM METRICS (IMÁGENES) */
        .metric-container {
            background: rgba(0, 20, 30, 0.6);
            border: 1px solid #004d66;
            border-radius: 10px;
            padding: 10px;
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100%;
            transition: transform 0.2s;
        }
        .metric-container:hover { transform: translateY(-5px); border-color: #00e5ff; box-shadow: 0 0 15px rgba(0, 229, 255, 0.2); }
        .metric-icon { width: 50px; height: 50px; object-fit: contain; margin-bottom: 5px; filter: drop-shadow(0 0 5px rgba(0,229,255,0.5)); }
        .metric-value { font-family: 'Orbitron'; font-size: 1.5rem; color: #fff; font-weight: bold; }
        .metric-label { font-size: 0.8rem; color: #00bcd4; text-transform: uppercase; letter-spacing: 1px; }

        /* EMBLEMA ESCUADRÓN */
        .squad-emblem { width: 80px; height: 80px; object-fit: contain; margin-top: 10px; filter: drop-shadow(0 0 8px rgba(0,229,255,0.4)); }

        /* BOTONES NEON BLUE */
        .stButton>button { 
            width: 100%; border-radius: 6px; 
            background: linear-gradient(90deg, #006064, #00bcd4); 
            color: white; border: none; padding: 12px 24px; 
            font-weight: bold; font-family: 'Orbitron', sans-serif; 
            text-transform: uppercase; letter-spacing: 1px;
            transition: all 0.3s; 
        }
        .stButton>button:hover { 
            background: linear-gradient(90deg, #00bcd4, #00e5ff); 
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.6); 
            color: #000;
        }
        .stButton button:disabled { background: #0f1520; color: #444; border: 1px solid #333; }
        
        /* TABS Y DATAFRAME */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { background-color: #0a101a; border: 1px solid #004d66; color: #00bcd4; }
        .stTabs [aria-selected="true"] { background-color: #00bcd4 !important; color: black !important; font-weight: bold; box-shadow: 0 0 10px #00bcd4; }
        
        /* SKILL CARDS */
        .skill-card { background-color: #0a141f; border: 1px solid #004d66; border-radius: 8px; padding: 15px; margin-bottom: 10px; }
        .skill-card:hover { border-color: #00e5ff; box-shadow: 0 0 10px rgba(0, 229, 255, 0.1); }
        .skill-cost { background: #002d38; color: #00e5ff; padding: 2px 8px; border-radius: 4px; border: 1px solid #006064; font-size: 0.8em; }

        /* ALERTA */
        .stAlert { background-color: #05101a; border: 1px solid #00bcd4; color: #e0f7fa; }
    </style>
""", unsafe_allow_html=True)

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
                        except: st.session_state.uni_actual = None; st.session_state.ano_actual = None

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

# HELPER: Función para verificar si existe imagen, si no devuelve una transparente o placeholder
def get_image_path(filename):
    if os.path.exists(f"assets/{filename}"):
        return f"assets/{filename}"
    return "https://via.placeholder.com/150?text=IMG" # Placeholder si falla

if not st.session_state.jugador:
    # --- PANTALLA LOGIN ---
    st.image(get_image_path("cover.png"), use_container_width=True)
    
    with st.container():
        # Logo y Título
        c_l, c_r = st.columns([1, 4])
        with c_l:
            st.image(get_image_path("logo.png"), width=80)
        with c_r:
            st.markdown("<h3 style='margin-bottom:0;'>PRAXIS PRIMORIS</h3>", unsafe_allow_html=True)
            st.caption("PLATAFORMA COMPUTADORA CENTRAL")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.markdown("##### 🔐 IDENTIFICACIÓN REQUERIDA")
            st.text_input("Nickname (Usuario):", placeholder="Ingresa tu codename...", key="input_user")
            st.text_input("Password:", type="password", key="input_pass")
            st.form_submit_button("INICIAR ENLACE NEURAL", on_click=validar_login)
    
    if st.session_state.login_error:
        st.error(st.session_state.login_error)

else:
    # --- DASHBOARD USUARIO ---
    p = st.session_state.jugador
    mp = p.get("MP", {}).get("number", 0) or 0
    ap = p.get("AP", {}).get("number", 0) or 0
    nivel_num = calcular_nivel_usuario(mp)
    nombre_rango = NOMBRES_NIVELES.get(nivel_num, "Desconocido")
    
    uni_label = st.session_state.uni_actual if st.session_state.uni_actual else "Ubicación Desconocida"
    ano_label = st.session_state.ano_actual if st.session_state.ano_actual else "Ciclo ?"

    # Header Dashboard
    c_head1, c_head2 = st.columns([1, 5])
    with c_head1: st.image(get_image_path("logo.png"), width=60)
    with c_head2:
        st.markdown(f"<h2 style='margin:0;'>HOLA, {st.session_state.nombre}</h2>", unsafe_allow_html=True)
        st.caption(f"📍 {uni_label} | 📅 {ano_label}")

    # Pestañas
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
        # Intento de cargar emblema del escuadrón (basado en nombre archivo = nombre escuadron minusculas y guiones bajos)
        emblema_filename = skuad.lower().replace(" ", "_") + ".png" if skuad else "none.png"
        
        try: vp = int(p.get("VP", {}).get("number", 1))
        except: vp = 0
        
        # Tarjeta Perfil
        st.markdown(f"""
        <div class="profile-card">
            {'<img src="' + avatar_url + '" class="avatar-img">' if avatar_url else '<div style="font-size:80px;">👤</div>'}
            <h2 style="margin:0; color:#00e5ff; text-transform: uppercase;">{st.session_state.nombre}</h2>
            <h3 style="margin:5px 0; color:#e0f7fa; font-size:1.1em;">{rol}</h3>
            <p style="color:#00bcd4; letter-spacing:2px;">NIVEL {nivel_num}: {nombre_rango.upper()}</p>
        </div>
        """, unsafe_allow_html=True)

        # Emblema Squad (Visualización extra)
        if os.path.exists(f"assets/{emblema_filename}"):
             st.markdown(f"""
             <div style="text-align:center; margin-bottom:20px;">
                <img src="app/static/{emblema_filename}" style="width:60px; opacity:0.8;">
                <div style="color:#00bcd4; font-size:0.8em;">{skuad}</div>
             </div>
             """, unsafe_allow_html=True)
            
        # HUD Stats con IMÁGENES
        # Nota: Streamlit no sirve imagenes locales en HTML puro facil sin base64, 
        # pero usaremos st.image dentro de columnas para simular el componente.
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.image(get_image_path("icon_mp.png"), width=50)
            st.markdown(f"""
                <div class="metric-value">{mp}</div>
                <div class="metric-label">MasterPoints</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.image(get_image_path("icon_ap.png"), width=50)
            st.markdown(f"""
                <div class="metric-value">{ap}</div>
                <div class="metric-label">AngioPoints</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown('<div class="metric-container">', unsafe_allow_html=True)
            st.image(get_image_path("icon_vp.png"), width=50)
            st.markdown(f"""
                <div class="metric-value">{vp}%</div>
                <div class="metric-label">VitaPoints</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("DESCONECTAR", on_click=cerrar_sesion)

    # --- TAB 2: RANKING ---
    with tab_ranking:
        st.markdown(f"### ⚔️ TOP ASPIRANTES")
        df = st.session_state.ranking_data
        
        if df is not None and not df.empty:
            st.dataframe(
                df.head(10), 
                use_container_width=True,
                column_config={
                    "MasterPoints": st.column_config.ProgressColumn(
                        "Progreso MP", format="%d", min_value=0, max_value=int(df["MasterPoints"].max())
                    ),
                    "Escuadrón": st.column_config.TextColumn("Escuadrón"),
                }
            )
            
            st.markdown("### 🛡️ DOMINIO DE ESCUADRONES")
            # Gráfico con color Cyan
            df_squads = df.groupby("Escuadrón")["MasterPoints"].sum().reset_index().sort_values(by="MasterPoints", ascending=False)
            st.bar_chart(df_squads, x="Escuadrón", y="MasterPoints", color="#00bcd4")
        else:
            st.info(f"Sin datos en el sector {uni_label}.")
            if st.button("🔄 Refrescar Señal"):
                st.session_state.ranking_data = cargar_ranking_filtrado(st.session_state.uni_actual, st.session_state.ano_actual)
                st.rerun()

    # --- TAB 3: HABILIDADES ---
    with tab_habilidades:
        st.markdown(f"### 📜 GRIMORIO: {rol.upper()}")
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
                
                desbloqueada = nivel_num >= nivel_req
                puede_pagar = ap >= costo
                
                with st.container():
                    border_color = "#00e5ff" if desbloqueada else "#1c2630"
                    opacity = "1" if desbloqueada else "0.5"
                    grayscale = "" if desbloqueada else "filter: grayscale(100%);"
                    
                    st.markdown(f"""
                    <div class="skill-card" style="border-left: 4px solid {border_color}; opacity: {opacity}; {grayscale}">
                        <div class="skill-header">
                            <h4 style="margin:0; color:#e0f7fa; font-size:1em;">{nombre}</h4>
                            <span class="skill-cost">⚡ {costo} AP</span>
                        </div>
                        <p style="color:#b0bec5; font-size:0.85em; margin:0;">{desc}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_btn, _ = st.columns([1, 2])
                    with c_btn:
                        if desbloqueada:
                            if st.button(f"ACTIVAR", key=f"btn_{hab['id']}"):
                                if puede_pagar:
                                    exito = solicitar_activacion_habilidad(nombre, costo, st.session_state.nombre)
                                    if exito:
                                        st.toast(f"✅ Ejecutado: {nombre}", icon="💠")
                                        st.balloons()
                                    else: st.error("Error de enlace.")
                                else: st.toast("❌ Energía Insuficiente", icon="⚠️")
                        else:
                            nombre_req = NOMBRES_NIVELES.get(nivel_req, f"Nivel {nivel_req}")
                            st.button(f"🔒 Req: {nombre_req}", disabled=True, key=f"lk_{hab['id']}")
