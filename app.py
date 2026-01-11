import streamlit as st
import requests
import pandas as pd # Necesitamos pandas para ordenar tablas y gráficos fácil

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
except FileNotFoundError:
    st.error("⚠️ Configura los secretos en Streamlit Cloud.")
    st.stop()

# --- CONFIGURACIÓN GLOBAL ---
headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

st.set_page_config(page_title="Universo AngioMasters", page_icon="🫀", layout="centered")

# --- CSS: ESTÉTICA GAMER & DISEÑO ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        
        /* FUENTES */
        h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
        
        /* LIMPIEZA */
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
        
        /* RANKING (DISEÑO ESPECÍFICO PASO A PASO) */
        .ranking-card {
            background-color: #0E1117;
            border-left: 5px solid #FFD700; /* Borde Dorado */
            padding: 10px;
            margin-bottom: 5px;
            border-radius: 5px;
        }
        
        /* MÉTRICAS Y BOTONES */
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem !important; }
        .stButton>button {
            width: 100%; border-radius: 8px; background-color: #990000; 
            color: white; border: none; padding: 10px 24px; font-weight: bold;
            font-family: 'Orbitron', sans-serif;
        }
        .stButton>button:hover { background-color: #FF0000; }
        
        /* PESTAÑAS (TABS) */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            background-color: #1E1E1E; border-radius: 5px; color: white;
        }
        .stTabs [aria-selected="true"] {
            background-color: #990000 !important; color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
c1, c2 = st.columns([1,5])
with c1: st.markdown("# 🛡️")
with c2: 
    st.markdown("# ANGIOMASTERS")
    st.caption("Sistema de Gestión RPG - Hemodinamia IV")
st.divider()

# --- ESTADO ---
if "jugador" not in st.session_state: st.session_state.jugador = None
if "team_stats" not in st.session_state: st.session_state.team_stats = 0
if "squad_name" not in st.session_state: st.session_state.squad_name = None
if "login_error" not in st.session_state: st.session_state.login_error = None
# Cache para el ranking (para no cargarlo a cada segundo)
if "ranking_data" not in st.session_state: st.session_state.ranking_data = None

# --- FUNCIONES AUXILIARES ---

# 1. Obtener puntaje de MI equipo (Texto)
def obtener_puntaje_equipo_texto(nombre_escuadron):
    if not nombre_escuadron: return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Nombre Escuadrón", "rich_text": {"equals": nombre_escuadron}}}
    try:
        res = requests.post(url, headers=headers, json=payload)
        total_mp = 0
        if res.status_code == 200:
            data = res.json()
            for miembro in data["results"]:
                try:
                    val = miembro["properties"]["MP"]["number"]
                    if val: total_mp += val
                except: pass
        return total_mp
    except: return 0

# 2. OBTENER RANKING GLOBAL (NUEVO 🏆)
# Esta función descarga TODA la base de datos para armar la tabla de líderes
def cargar_ranking_global():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    # Sin filtro = Trae a todos
    try:
        res = requests.post(url, headers=headers, json={})
        if res.status_code == 200:
            data = res.json()
            lista_jugadores = []
            
            for p in data["results"]:
                props = p["properties"]
                try:
                    # Nombre
                    nombre = props["Jugador"]["title"][0]["text"]["content"]
                    # MP
                    mp = props["MP"]["number"] or 0
                    # Escuadrón (Buscamos como texto)
                    esc_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                    escuadron = esc_obj[0]["text"]["content"] if esc_obj else "Sin Escuadrón"
                    
                    lista_jugadores.append({
                        "Agente": nombre,
                        "Escuadrón": escuadron,
                        "MasterPoints": mp
                    })
                except: pass # Si falta algún dato, saltamos al siguiente
            
            # Convertimos a DataFrame para ordenar fácil
            df = pd.DataFrame(lista_jugadores)
            if not df.empty:
                # Ordenar por MP descendente
                df = df.sort_values(by="MasterPoints", ascending=False).reset_index(drop=True)
                # El índice empieza en 0, le sumamos 1 para que sea Ranking 1, 2, 3...
                df.index += 1 
            return df
    except Exception as e:
        return pd.DataFrame() # Retorna tabla vacía si falla
    return pd.DataFrame()

# 3. LOGIN CALLBACK
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
                        
                        # Datos Escuadrón
                        sq_name = "Sin Escuadrón"
                        try:
                            sq_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                            if sq_obj: sq_name = sq_obj[0]["text"]["content"]
                        except: pass
                        st.session_state.squad_name = sq_name
                        st.session_state.team_stats = obtener_puntaje_equipo_texto(sq_name)
                        
                        # Cargamos el Ranking Global al entrar
                        st.session_state.ranking_data = cargar_ranking_global()
                        
                    else: st.session_state.login_error = "❌ CLAVE INCORRECTA"
                except: st.session_state.login_error = "❌ ERROR DE CREDENCIALES"
            else: st.session_state.login_error = "❌ USUARIO NO ENCONTRADO"
        else: st.session_state.login_error = "⚠️ Error de conexión"
    except Exception as e: st.session_state.login_error = f"Error técnico: {e}"

def cerrar_sesion():
    st.session_state.jugador = None
    st.session_state.ranking_data = None # Limpiamos ranking al salir

# ================= UI =================

if not st.session_state.jugador:
    # PANTALLA LOGIN
    with st.form("login_form"):
        st.markdown("### 🔐 ACCESO A LA MATRIX")
        st.text_input("Codename:", placeholder="Ej: Neo", key="input_user")
        st.text_input("Password:", type="password", key="input_pass")
        st.form_submit_button("INICIAR SISTEMA", on_click=validar_login)
    
    if st.session_state.login_error:
        st.error(st.session_state.login_error)

else:
    # PANTALLA PRINCIPAL (CON TABS)
    p = st.session_state.jugador
    
    # --- PESTAÑAS DE NAVEGACIÓN ---
    tab_perfil, tab_ranking = st.tabs(["👤 MI PERFIL", "🏆 HALL OF FAME"])
    
    # ==========================================
    # TAB 1: MI PERFIL (Lo que ya teníamos)
    # ==========================================
    with tab_perfil:
        # Procesar datos
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
        
        try:
            n_data = p.get("Nivel", {}).get("select")
            nivel = n_data["name"] if n_data else "Iniciado"
        except: nivel = "Iniciado"
        
        skuad = st.session_state.squad_name
        
        try: mp = p.get("MP", {}).get("number", 0) or 0
        except: mp = 0
        try: ap = p.get("AP", {}).get("number", 0) or 0
        except: ap = 0
        try: 
            vp_raw = p.get("VP", {}).get("number", 1) or 0
            vp = int(vp_raw * 100) if vp_raw <= 1 and vp_raw > 0 else int(vp_raw)
        except: vp = 0
        
        # Render Perfil
        with st.container():
            html_avatar = f"""
            <div class="profile-card">
                {'<img src="' + avatar_url + '" class="avatar-img">' if avatar_url else '<div style="font-size:80px;">👤</div>'}
                <h2 style="margin:0; color:#FF4B4B;">{st.session_state.nombre}</h2>
                <h3 style="margin:5px 0; color:white;">{skuad} | {rol}</h3>
                <p style="color:#aaa;">Rango: {nivel}</p>
            </div>
            """
            st.markdown(html_avatar, unsafe_allow_html=True)
            
        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ MP (XP)", mp)
        c2.metric("⚡ AP (Poder)", ap)
        c3.metric("❤️ VP (Salud)", f"{vp}%")
        
        st.divider()
        st.button("CERRAR SESIÓN", on_click=cerrar_sesion)

    # ==========================================
    # TAB 2: HALL OF FAME (NUEVO)
    # ==========================================
    with tab_ranking:
        st.markdown("### ⚔️ TOP AGENTES (Global)")
        
        df = st.session_state.ranking_data
        
        if df is not None and not df.empty:
            # 1. TABLA DE LÍDERES
            # Mostramos el Top 10
            st.dataframe(
                df.head(10), 
                use_container_width=True,
                column_config={
                    "Agente": st.column_config.TextColumn("Agente", help="Nombre clave"),
                    "Escuadrón": st.column_config.TextColumn("Escuadrón"),
                    "MasterPoints": st.column_config.ProgressColumn(
                        "MasterPoints (XP)", 
                        format="%d", 
                        min_value=0, 
                        max_value=int(df["MasterPoints"].max()) # La barra se ajusta al mejor jugador
                    ),
                }
            )
            
            st.divider()
            
            # 2. GUERRA DE ESCUADRONES (GRÁFICO)
            st.markdown("### 🛡️ GUERRA DE ESCUADRONES")
            
            # Agrupar por escuadrón y sumar MP
            df_squads = df.groupby("Escuadrón")["MasterPoints"].sum().reset_index()
            df_squads = df_squads.sort_values(by="MasterPoints", ascending=False)
            
            # Gráfico de Barras Simple
            st.bar_chart(
                df_squads, 
                x="Escuadrón", 
                y="MasterPoints",
                color="#990000" # Color Rojo AngioMasters
            )
            
        else:
            st.warning("No hay datos de clasificación disponibles.")
            
        if st.button("🔄 Actualizar Ranking"):
             st.session_state.ranking_data = cargar_ranking_global()
             st.rerun()
