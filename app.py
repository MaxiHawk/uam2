import streamlit as st
import requests

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
        /* MÉTRICAS */
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem !important; }
        /* BOTONES */
        .stButton>button {
            width: 100%; border-radius: 8px; background-color: #990000; 
            color: white; border: none; padding: 10px 24px; font-weight: bold;
            font-family: 'Orbitron', sans-serif;
        }
        .stButton>button:hover { background-color: #FF0000; }
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

# --- FUNCIÓN: OBTENER PUNTAJE EQUIPO ---
def obtener_puntaje_equipo_texto(nombre_escuadron):
    if not nombre_escuadron: return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    
    # Filtro de texto (Rich Text)
    payload = {
        "filter": {
            "property": "Nombre Escuadrón", 
            "rich_text": {"equals": nombre_escuadron}
        }
    }
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

# --- LOGIN (AHORA CON FORMULARIO) ---
if not st.session_state.jugador:
    # ⚠️ AQUÍ ESTÁ EL CAMBIO CLAVE: st.form
    with st.form("login_form"):
        st.markdown("### 🔐 ACCESO A LA MATRIX")
        usuario = st.text_input("Codename:", placeholder="Ej: Neo")
        clave = st.text_input("Password:", type="password")
        
        # El botón ahora es un "submit_button" vinculado al formulario
        submitted = st.form_submit_button("INICIAR SISTEMA")
    
    if submitted:
        if not usuario or not clave:
            st.warning("⚠️ Ingresa usuario y contraseña.")
        else:
            url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
            payload = {"filter": {"property": "Jugador", "title": {"equals": usuario}}}
            
            try:
                with st.spinner("Conectando..."):
                    res = requests.post(url, headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        if len(data["results"]) > 0:
                            props = data["results"][0]["properties"]
                            # Validar Clave
                            try:
                                c_obj = props.get("Clave", {}).get("rich_text", [])
                                c_real = c_obj[0]["text"]["content"] if c_obj else ""
                                
                                if clave == c_real:
                                    st.session_state.jugador = props
                                    st.session_state.nombre = usuario
                                    
                                    # Extraer Escuadrón
                                    sq_name = "Sin Escuadrón"
                                    try:
                                        sq_obj = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                                        if sq_obj: sq_name = sq_obj[0]["text"]["content"]
                                    except: pass
                                    
                                    st.session_state.squad_name = sq_name
                                    st.session_state.team_stats = obtener_puntaje_equipo_texto(sq_name)
                                    st.rerun()
                                else: st.error("❌ CLAVE INCORRECTA")
                            except: st.error("❌ ERROR DE CREDENCIALES")
                        else: st.error("❌ USUARIO NO ENCONTRADO")
            except Exception as e: st.error(f"Error: {e}")

# --- DASHBOARD ---
else:
    p = st.session_state.jugador
    
    # AVATAR
    avatar_url = None
    try:
        f_list = p.get("Avatar", {}).get("files", [])
        if f_list:
            if "file" in f_list[0]: avatar_url = f_list[0]["file"]["url"]
            elif "external" in f_list[0]: avatar_url = f_list[0]["external"]["url"]
    except: pass

    # DATOS
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

    # UI DASHBOARD
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
    st.subheader(f"🏆 Escuadrón: {skuad}")
    st.metric("Puntaje Colectivo", st.session_state.team_stats)
    
    if st.button("CERRAR SESIÓN"):
        st.session_state.jugador = None
        st.rerun()
