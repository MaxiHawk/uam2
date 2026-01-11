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

# --- CSS: ESTÉTICA GAMER AVANZADA ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto:wght@300;400;700&display=swap');
        
        /* FUENTES */
        h1, h2, h3 { font-family: 'Orbitron', sans-serif !important; letter-spacing: 2px; }
        html, body, [class*="css"] { font-family: 'Roboto', sans-serif; }

        /* LIMPIEZA INTERFAZ */
        .block-container { padding-top: 2rem !important; padding-bottom: 2rem !important; }
        #MainMenu, header, footer, .stAppDeployButton { display: none !important; }
        [data-testid="stDecoration"], [data-testid="stStatusWidget"], [data-testid="stToolbar"] { display: none !important; }
        
        /* ESTILOS DE TARJETAS DE ROL */
        .rol-badge {
            background-color: #1E1E1E;
            border: 1px solid #990000;
            border-radius: 10px;
            padding: 15px;
            text-align: center;
            margin-bottom: 20px;
        }
        
        /* MÉTRICAS */
        [data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif; font-size: 2rem !important; }
        
        /* BOTONES */
        .stButton>button {
            width: 100%; border-radius: 8px; background-color: #990000; 
            color: white; border: none; padding: 10px 24px; font-weight: bold;
            font-family: 'Orbitron', sans-serif;
        }
        .stButton>button:hover { background-color: #FF0000; box-shadow: 0 0 15px #FF0000; }
    </style>
""", unsafe_allow_html=True)

# --- CABECERA ---
c_logo, c_title = st.columns([1, 5])
with c_logo:
    st.markdown("# 🛡️")
with c_title:
    st.markdown("# UNIVERSO ANGIOMASTERS")
    st.caption("Plataforma de Gamificación - Hemodinamia IV")
st.divider()

# --- ESTADO DE SESIÓN ---
if "jugador" not in st.session_state:
    st.session_state.jugador = None
if "team_stats" not in st.session_state:
    st.session_state.team_stats = 0

# --- FUNCIÓN PARA CALCULAR PUNTAJE DE EQUIPO ---
def obtener_puntaje_equipo(nombre_escuadron):
    if not nombre_escuadron: return 0
    
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    # Filtramos por el nombre del escuadrón exacto
    payload = {"filter": {"property": "Escuadron", "select": {"equals": nombre_escuadron}}}
    
    res = requests.post(url, headers=headers, json=payload)
    total_mp = 0
    if res.status_code == 200:
        data = res.json()
        # Recorremos a TODOS los miembros del equipo y sumamos sus MP
        for miembro in data["results"]:
            try:
                mp_miembro = miembro["properties"]["MP"]["number"]
                if mp_miembro: total_mp += mp_miembro
            except: pass
    return total_mp

# --- PANTALLA DE LOGIN ---
if not st.session_state.jugador:
    st.markdown("### 🔐 ACCESO A LA MATRIX")
    usuario_input = st.text_input("Codename (Usuario):", placeholder="Ej: Neo")
    clave_input = st.text_input("Password:", type="password")
    
    if st.button("INICIAR SISTEMA"):
        url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
        payload = {"filter": {"property": "Jugador", "title": {"equals": usuario_input}}}
        
        try:
            with st.spinner("Desencriptando datos..."):
                response = requests.post(url, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    if len(data["results"]) > 0:
                        props = data["results"][0]["properties"]
                        # Verificamos Clave
                        try:
                            clave_real = props["Clave"]["rich_text"][0]["text"]["content"]
                            if clave_input == clave_real:
                                st.session_state.jugador = props
                                st.session_state.nombre = usuario_input
                                
                                # --- NUEVO: OBTENER DATOS DE EQUIPO ---
                                escuadron = props["Escuadron"]["select"]["name"] if props["Escuadron"]["select"] else None
                                st.session_state.nombre_escuadron = escuadron
                                st.session_state.team_stats = obtener_puntaje_equipo(escuadron)
                                
                                st.rerun()
                            else:
                                st.error("❌ CLAVE INCORRECTA")
                        except: st.error("⚠️ Error en datos de credenciales.")
                    else:
                        st.error("❌ JUGADOR NO ENCONTRADO")
        except Exception as e:
            st.error(f"Error de conexión: {e}")

# --- PANTALLA DASHBOARD (HUD) ---
else:
    p = st.session_state.jugador
    
    # 1. Extracción de Datos
    try:
        nivel = p["Nivel"]["select"]["name"] if p["Nivel"]["select"] else "Iniciado"
        rol = p["Rol"]["select"]["name"] if p["Rol"]["select"] else "Sin Rol"
        skuad = st.session_state.nombre_escuadron if st.session_state.nombre_escuadron else "Lobo Solitario"
        
        mp = p["MP"]["number"] or 0
        ap = p["AP"]["number"] or 0
        vp = p["VP"]["number"] or 100
    except:
        nivel, rol, skuad = "Error", "Error", "Error"
        mp, ap, vp = 0, 0, 0

    # 2. Tarjeta de Identidad (NUEVO DISEÑO)
    st.markdown(f"""
    <div class="rol-badge">
        <h2 style="margin:0; color:#FF4B4B;">{st.session_state.nombre}</h2>
        <h4 style="margin:0; color:white;">{skuad} | {rol}</h4>
        <p style="margin:0; color:gray;">Rango: {nivel}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 3. Estadísticas Personales
    c1, c2, c3 = st.columns(3)
    c1.metric("⭐ Mis MasterPoints", mp)
    c2.metric("⚡ AngioPoints", ap)
    c3.metric("❤️ VitaPoints", vp)
    
    st.divider()
    
    # 4. Estadísticas DE EQUIPO (NUEVO)
    st.subheader(f"🏆 Progreso del {skuad}")
    
    # Barra de progreso simulada (puedes ajustar el 'max_value' según tu meta del juego)
    meta_juego = 1000 
    progreso = min(st.session_state.team_stats / meta_juego, 1.0)
    
    st.progress(progreso)
    col_team_a, col_team_b = st.columns(2)
    
    with col_team_a:
        st.metric("Puntaje Total del Equipo", st.session_state.team_stats)
    with col_team_b:
        st.caption(f"Meta para el siguiente hito: {meta_juego} MP")
        if progreso >= 1.0:
            st.success("¡META ALCANZADA! 🚀")

    st.divider()
    if st.button("CERRAR SESIÓN"):
        st.session_state.jugador = None
        st.rerun()
