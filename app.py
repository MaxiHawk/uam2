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

# --- CSS ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }
        .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { display: none !important; }
        
        .rol-badge {
            background-color: #1E1E1E; border: 1px solid #990000;
            border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 20px;
        }
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem !important; }
        .stButton>button {
            width: 100%; border-radius: 8px; background-color: #990000; 
            color: white; border: none; padding: 10px 24px; font-weight: bold;
            font-family: 'Orbitron', sans-serif;
        }
        .stButton>button:hover { background-color: #FF0000; box-shadow: 0 0 15px #FF0000; }
    </style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.markdown("# 🛡️ UNIVERSO ANGIOMASTERS")
st.caption("Gamificación - Hemodinamia IV")
st.divider()

# --- STATE ---
if "jugador" not in st.session_state:
    st.session_state.jugador = None
if "team_stats" not in st.session_state:
    st.session_state.team_stats = 0

# --- FUNCIONES AUXILIARES ---
def safe_get(props, key, type_key, default):
    """Intenta obtener un dato, si falla devuelve el default sin romper la app"""
    try:
        if key in props:
            return props[key][type_key]
        else:
            return default # Retorna esto si la columna no existe
    except:
        return default

def obtener_puntaje_equipo(nombre_escuadron):
    if not nombre_escuadron or nombre_escuadron == "Sin Escuadrón": return 0
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    # IMPORTANTE: Aquí asumo que la columna en Notion se llama "Escuadron" (sin tilde) o "Escuadrón"
    # Si falla, intenta cambiar "Escuadron" por el nombre exacto que veas en Notion.
    payload = {"filter": {"property": "Escuadron", "select": {"equals": nombre_escuadron}}}
    
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
    except:
        return 0

# --- LOGIN ---
if not st.session_state.jugador:
    usuario_input = st.text_input("Codename:", placeholder="Ej: Neo")
    clave_input = st.text_input("Password:", type="password")
    
    if st.button("INICIAR SISTEMA"):
        url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
        payload = {"filter": {"property": "Jugador", "title": {"equals": usuario_input}}}
        
        try:
            with st.spinner("Desencriptando..."):
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if len(data["results"]) > 0:
                        props = data["results"][0]["properties"]
                        # Verificación de clave
                        try:
                            # Intento robusto de leer la clave
                            clave_obj = props.get("Clave", {}).get("rich_text", [])
                            clave_real = clave_obj[0]["text"]["content"] if clave_obj else ""
                            
                            if clave_input == clave_real:
                                st.session_state.jugador = props
                                st.session_state.nombre = usuario_input
                                
                                # Intentar leer Escuadrón para cargar puntos
                                try:
                                    esc_obj = props.get("Escuadron", {}).get("select")
                                    nombre_esc = esc_obj["name"] if esc_obj else None
                                except: 
                                    nombre_esc = None
                                    
                                st.session_state.nombre_escuadron = nombre_esc
                                st.session_state.team_stats = obtener_puntaje_equipo(nombre_esc)
                                st.rerun()
                            else:
                                st.error("❌ CLAVE INCORRECTA")
                        except Exception as e:
                            st.error(f"Error procesando credenciales: {e}")
                    else:
                        st.error("❌ USUARIO NO ENCONTRADO")
                else:
                    st.error("⚠️ Error de conexión.")
        except Exception as e:
            st.error(f"Error técnico: {e}")

# --- DASHBOARD ---
else:
    p = st.session_state.jugador
    
    # --- ZONA DE DEPURACIÓN (Solo tú verás esto para corregir nombres) ---
    with st.expander("🛠️ INSPECTOR DE DATOS (Abre esto si ves 'Error')"):
        st.write("Estos son los nombres exactos de tus columnas en Notion:")
        st.json(list(p.keys())) # Muestra solo los nombres de las columnas
        st.write("---")
        st.write("Datos completos recibidos:")
        st.json(p) # Muestra todo el JSON para detectar fallos

    # --- EXTRACCIÓN ROBUSTA DE DATOS ---
    # Usamos .get() para que no falle si el nombre está mal escrito
    
    # 1. Nivel
    try:
        nivel_data = p.get("Nivel", {}).get("select")
        nivel = nivel_data["name"] if nivel_data else "Iniciado"
    except: nivel = "Error Nivel"

    # 2. Rol
    try:
        rol_data = p.get("Rol", {}).get("select") # <--- OJO AQUÍ
        rol = rol_data["name"] if rol_data else "Sin Asignar"
    except: rol = "Error Rol"
    
    # 3. Escuadrón
    try:
        # Intenta con "Escuadron" (sin tilde) y "Escuadrón" (con tilde) por si acaso
        esc_data = p.get("Escuadron", {}).get("select") 
        if not esc_data: esc_data = p.get("Escuadrón", {}).get("select")
        skuad = esc_data["name"] if esc_data else "Sin Escuadrón"
    except: skuad = "Error Squad"

    # 4. Puntos
    try: mp = p.get("MP", {}).get("number", 0)
    except: mp = 0
    
    try: ap = p.get("AP", {}).get("number", 0)
    except: ap = 0
    
    try: vp = p.get("VP", {}).get("number", 100)
    except: vp = 0
    
    # Manejo de Nones (Si Notion devuelve 'null' en vez de 0)
    if mp is None: mp = 0
    if ap is None: ap = 0
    if vp is None: vp = 100

    # --- UI ---
    st.markdown(f"""
    <div class="rol-badge">
        <h2 style="margin:0; color:#FF4B4B;">{st.session_state.nombre}</h2>
        <h4 style="margin:0; color:white;">{skuad} | {rol}</h4>
        <p style="margin:0; color:gray;">Rango: {nivel}</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("⭐ MP", mp)
    c2.metric("⚡ AP", ap)
    c3.metric("❤️ VP", vp)
    
    st.divider()
    st.subheader(f"🏆 Progreso del {skuad}")
    st.metric("Puntaje de Equipo", st.session_state.team_stats)
    
    if st.button("CERRAR SESIÓN"):
        st.session_state.jugador = None
        st.rerun()
