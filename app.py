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
        
        /* FUENTES */
        h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

        /* LIMPIEZA */
        .block-container { padding-top: 2rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { display: none !important; }
        
        /* TARJETA DE PERFIL */
        .profile-card {
            background: linear-gradient(145deg, #1e1e1e, #2d2d2d);
            border: 2px solid #990000;
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        }
        
        /* AVATAR */
        .avatar-img {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            object-fit: cover;
            border: 4px solid #FF4B4B;
            margin-bottom: 10px;
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
col_head_1, col_head_2 = st.columns([1,5])
with col_head_1:
    st.markdown("# 🛡️")
with col_head_2:
    st.markdown("# ANGIOMASTERS")
    st.caption("Sistema de Gestión RPG - Hemodinamia IV")
st.divider()

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state:
    st.session_state.jugador = None
if "team_stats" not in st.session_state:
    st.session_state.team_stats = 0

# --- FUNCIÓN: OBTENER PUNTAJE EQUIPO ---
def obtener_puntaje_equipo(nombre_escuadron, propiedad_escuadron_exacta):
    if not nombre_escuadron or nombre_escuadron == "Sin Escuadrón": return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    
    # Usamos el nombre exacto de la columna que encontramos en el login
    payload = {"filter": {"property": propiedad_escuadron_exacta, "select": {"equals": nombre_escuadron}}}
    
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

# --- LOGIN ---
if not st.session_state.jugador:
    usuario_input = st.text_input("Codename:", placeholder="Ej: Neo")
    clave_input = st.text_input("Password:", type="password")
    
    if st.button("INICIAR SISTEMA"):
        url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
        payload = {"filter": {"property": "Jugador", "title": {"equals": usuario_input}}}
        
        try:
            with st.spinner("Conectando con la base..."):
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if len(data["results"]) > 0:
                        props = data["results"][0]["properties"]
                        # Validar Clave
                        try:
                            clave_obj = props.get("Clave", {}).get("rich_text", [])
                            clave_real = clave_obj[0]["text"]["content"] if clave_obj else ""
                            
                            if clave_input == clave_real:
                                st.session_state.jugador = props
                                st.session_state.nombre = usuario_input
                                
                                # --- BÚSQUEDA INTELIGENTE DE ESCUADRÓN ---
                                # Buscamos en 3 posibles nombres de columna
                                nombre_columna_escuadron = "Escuadron" # Default
                                esc_data = None
                                
                                if "Escuadron" in props: 
                                    esc_data = props["Escuadron"].get("select")
                                    nombre_columna_escuadron = "Escuadron"
                                elif "Escuadrón" in props: 
                                    esc_data = props["Escuadrón"].get("select")
                                    nombre_columna_escuadron = "Escuadrón"
                                elif "Nombre Escuadrón" in props:
                                    esc_data = props["Nombre Escuadrón"].get("select")
                                    nombre_columna_escuadron = "Nombre Escuadrón"
                                
                                nombre_esc = esc_data["name"] if esc_data else "Sin Escuadrón"
                                st.session_state.nombre_escuadron = nombre_esc
                                
                                # Calculamos puntaje del equipo usando la columna correcta
                                st.session_state.team_stats = obtener_puntaje_equipo(nombre_esc, nombre_columna_escuadron)
                                
                                st.rerun()
                            else:
                                st.error("❌ CLAVE INCORRECTA")
                        except Exception as e:
                            st.error(f"Error procesando clave: {e}")
                    else:
                        st.error("❌ USUARIO NO ENCONTRADO")
        except Exception as e:
            st.error(f"Error técnico: {e}")

# --- DASHBOARD ---
else:
    p = st.session_state.jugador
    
    # 1. EXTRACCIÓN DE DATOS
    
    # --- AVATAR ---
    avatar_url = None
    try:
        # Busca en la propiedad "Avatar". Soporta subida directa (file) o enlace (external)
        files_list = p.get("Avatar", {}).get("files", [])
        if files_list:
            if "file" in files_list[0]:
                avatar_url = files_list[0]["file"]["url"]
            elif "external" in files_list[0]:
                avatar_url = files_list[0]["external"]["url"]
    except: pass

    # --- DATOS DE TEXTO ---
    try:
        nivel_data = p.get("Nivel", {}).get("select")
        nivel = nivel_data["name"] if nivel_data else "Iniciado"
    except: nivel = "Nivel Desconocido"

    try:
        rol_data = p.get("Rol", {}).get("select")
        rol = rol_data["name"] if rol_data else "Recluta"
    except: rol = "Sin Rol"
    
    skuad = st.session_state.nombre_escuadron

    # --- DATOS NUMÉRICOS (CORRECCIÓN VP) ---
    try: mp = p.get("MP", {}).get("number", 0) or 0
    except: mp = 0
    
    try: ap = p.get("AP", {}).get("number", 0) or 0
    except: ap = 0
    
    try: 
        vp_raw = p.get("VP", {}).get("number", 1) or 0
        # CORRECCIÓN PORCENTAJE: Si Notion manda 0.8 o 1, lo convertimos a 80 o 100
        if vp_raw <= 1 and vp_raw > 0:
            vp = int(vp_raw * 100)
        else:
            vp = int(vp_raw)
    except: vp = 0

    # 2. INTERFAZ VISUAL
    
    # Contenedor de Perfil
    with st.container():
        # HTML personalizado para centrar imagen y datos
        html_avatar = f"""
        <div class="profile-card">
            {'<img src="' + avatar_url + '" class="avatar-img">' if avatar_url else '<div style="font-size:80px;">👤</div>'}
            <h2 style="margin:0; color:#FF4B4B;">{st.session_state.nombre}</h2>
            <h3 style="margin:5px 0; color:white;">{skuad} | {rol}</h3>
            <p style="color:#aaa; font-style:italic;">Rango: {nivel}</p>
        </div>
        """
        st.markdown(html_avatar, unsafe_allow_html=True)

    # Métricas Personales
    c1, c2, c3 = st.columns(3)
    c1.metric("⭐ MP (XP)", mp)
    c2.metric("⚡ AP (Poder)", ap)
    c3.metric("❤️ VP (Salud)", f"{vp}%") # Agregamos el signo % visualmente
    
    st.divider()
    
    # Métricas de Equipo
    st.subheader(f"🏆 Escuadrón {skuad}")
    st.metric("Puntaje Colectivo", st.session_state.team_stats, delta="Total Equipo")
    
    st.divider()
    if st.button("CERRAR SESIÓN"):
        st.session_state.jugador = None
        st.rerun()
