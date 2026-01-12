import streamlit as st
import requests
import pandas as pd
import time

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except FileNotFoundError:
    st.error("⚠️ Error: Faltan secretos. Configura ADMIN_PASSWORD en secrets.toml")
    st.stop()

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Centro de Mando | Praxis", page_icon="🎛️", layout="wide")

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- CSS TÁCTICO (DARK MODE) ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Roboto:wght@300;400;700&display=swap');
        
        h1, h2, h3 { font-family: 'Orbitron', sans-serif; color: #00e5ff; }
        .stApp { background-color: #050810; color: #e0f7fa; }
        
        /* TARJETAS DE SOLICITUD */
        .req-card {
            background: #0f1520; border: 1px solid #1c2e3e; border-left: 4px solid #FFD700;
            padding: 15px; border-radius: 8px; margin-bottom: 10px;
        }
        .req-player { font-family: 'Orbitron'; font-size: 1.1em; color: #FFD700; font-weight: bold; }
        .req-detail { color: #b0bec5; font-size: 0.9em; margin-bottom: 10px; }
        
        /* BOTONES DE ACCIÓN */
        .stButton>button { border-radius: 4px; font-weight: bold; text-transform: uppercase; }
        /* Aprobar (Verde Táctico) */
        div[data-testid="column"] > div > div > div > button:first-child { 
            border: 1px solid #00e676; color: #00e676; background: transparent; 
        }
        div[data-testid="column"] > div > div > div > button:first-child:hover { 
            background: #00e676; color: black; 
        }
        
        /* KPI BOXES */
        .kpi-box {
            background: rgba(0, 229, 255, 0.05); border: 1px solid #004d66;
            padding: 15px; text-align: center; border-radius: 10px;
        }
        .kpi-val { font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: white; }
        .kpi-label { font-size: 0.8em; color: #4dd0e1; letter-spacing: 2px; text-transform: uppercase; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES NOTION ---

def get_players():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    res = requests.post(url, headers=headers)
    if res.status_code == 200:
        players = []
        for p in res.json()["results"]:
            props = p["properties"]
            try:
                name = props["Jugador"]["title"][0]["text"]["content"]
                mp = props.get("MP", {}).get("number", 0)
                ap = props.get("AP", {}).get("number", 0)
                vp = props.get("VP", {}).get("number", 0)
                squad_list = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                squad = squad_list[0]["text"]["content"] if squad_list else "Sin Escuadrón"
                players.append({"id": p["id"], "Agente": name, "Escuadrón": squad, "MP": mp, "AP": ap, "VP": vp})
            except: pass
        return pd.DataFrame(players)
    return pd.DataFrame()

def get_pending_requests():
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    # Filtrar solo donde "Estado" no sea "Completado" (asumiendo que tienes una prop Estado o checkbox)
    # Por simplicidad, traeremos las últimas 50 y filtraremos visualmente o asumiremos que borras las hechas.
    # Idealmente: Agregar propiedad "Estado" (Select: Pendiente, Aprobado, Rechazado) en Notion.
    res = requests.post(url, headers=headers) 
    reqs = []
    if res.status_code == 200:
        for r in res.json()["results"]:
            props = r["properties"]
            try:
                # Asumiendo que usas un checkbox "Procesado" o similar. Si no, traemos todo.
                procesado = props.get("Procesado", {}).get("checkbox", False)
                if not procesado:
                    title_list = props["Remitente"]["title"]
                    remitente = title_list[0]["text"]["content"] if title_list else "Desconocido"
                    msg_list = props["Mensaje"]["rich_text"]
                    mensaje = msg_list[0]["text"]["content"] if msg_list else ""
                    reqs.append({"id": r["id"], "remitente": remitente, "mensaje": mensaje})
            except: pass
    return reqs

def update_player_ap(player_name, cost):
    # 1. Buscar ID del jugador
    url_query = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Jugador", "title": {"equals": player_name}}}
    res = requests.post(url_query, headers=headers, json=payload)
    if res.status_code == 200 and res.json()["results"]:
        player_page = res.json()["results"][0]
        player_id = player_page["id"]
        current_ap = player_page["properties"]["AP"]["number"]
        
        # 2. Restar AP
        new_ap = max(0, current_ap - cost)
        
        # 3. Actualizar
        url_patch = f"https://api.notion.com/v1/pages/{player_id}"
        patch_data = {"properties": {"AP": {"number": new_ap}}}
        requests.patch(url_patch, headers=headers, json=patch_data)
        return True
    return False

def mark_request_processed(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    # Necesitas crear una propiedad Checkbox llamada "Procesado" en la base de Solicitudes
    data = {"properties": {"Procesado": {"checkbox": True}}}
    requests.patch(url, headers=headers, json=data)

# --- LOGIN SYSTEM ---
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ ACCESO CLASIFICADO</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Código de Acceso:", type="password")
        if st.button("AUTENTICAR"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("⛔ ACCESO DENEGADO")
    st.stop()

# --- DASHBOARD PRINCIPAL ---

# Sidebar
with st.sidebar:
    st.title("🎛️ COMANDO")
    menu = st.radio("Sistemas:", ["📡 Solicitudes", "👥 Lista de Agentes", "⚙️ Ajustes Globales"])
    if st.button("Cerrar Sesión"):
        st.session_state.admin_logged_in = False
        st.rerun()

# LÓGICA DE PESTAÑAS
if menu == "📡 Solicitudes":
    st.markdown("### 📡 TRANSMISIONES ENTRANTES (SOLICITUDES)")
    st.info("ℹ️ Para que esto funcione automático, asegúrate de tener una propiedad 'checkbox' llamada **'Procesado'** en tu base de datos de Solicitudes en Notion.")
    
    reqs = get_pending_requests()
    
    if not reqs:
        st.success("✅ Todo despejado, Comandante. No hay solicitudes pendientes.")
    else:
        for r in reqs:
            # Intentar parsear el mensaje para sacar costo
            # Formato esperado: "Desea activar: 'Nombre' (Costo: 5 AP)..."
            costo = 0
            skill_name = "Habilidad"
            try:
                # Logica simple de extracción
                if "Costo:" in r['mensaje']:
                    part = r['mensaje'].split("Costo:")[1]
                    costo_str = part.split("AP")[0].strip()
                    costo = int(costo_str)
                if "activar:" in r['mensaje']:
                    skill_name = r['mensaje'].split("activar:")[1].split("(")[0].replace("'","").strip()
            except: pass
            
            # Limpiar nombre jugador (viene como "SOLICITUD: Nombre")
            player_name = r['remitente'].replace("SOLICITUD: ", "").strip()

            with st.container():
                c_card, c_act = st.columns([3, 1])
                with c_card:
                    st.markdown(f"""
                    <div class="req-card">
                        <div class="req-player">{player_name}</div>
                        <div class="req-detail">Solicita: <strong>{skill_name}</strong></div>
                        <div class="req-detail" style="color:#00e5ff;">Coste: ⚡ {costo} AP</div>
                        <div style="font-size:0.8em; color:#666;">{r['mensaje']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with c_act:
                    if st.button(f"✅ APROBAR", key=f"ap_{r['id']}"):
                        with st.spinner("Procesando enlace neural..."):
                            # 1. Descontar AP
                            ok = update_player_ap(player_name, costo)
                            if ok:
                                # 2. Marcar como procesado
                                mark_request_processed(r['id'])
                                st.success("Autorizado")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Error al descontar AP")
                    
                    if st.button(f"❌ DENEGAR", key=f"den_{r['id']}"):
                        mark_request_processed(r['id'])
                        st.warning("Denegado")
                        time.sleep(1)
                        st.rerun()

elif menu == "👥 Lista de Agentes":
    st.markdown("### 👥 NÓMINA DE AGENTES ACTIVOS")
    
    df_players = get_players()
    if not df_players.empty:
        # Métricas Rápidas
        k1, k2, k3 = st.columns(3)
        k1.markdown(f"<div class='kpi-box'><div class='kpi-val'>{len(df_players)}</div><div class='kpi-label'>Total Agentes</div></div>", unsafe_allow_html=True)
        k2.markdown(f"<div class='kpi-box'><div class='kpi-val'>{df_players['MP'].sum()}</div><div class='kpi-label'>Total MP Global</div></div>", unsafe_allow_html=True)
        k3.markdown(f"<div class='kpi-box'><div class='kpi-val'>{int(df_players['VP'].mean())}%</div><div class='kpi-label'>Salud Promedio</div></div>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Tabla interactiva (Solo lectura por ahora para evitar accidentes, pero ordenable)
        st.dataframe(
            df_players,
            column_config={
                "Agente": st.column_config.TextColumn("Agente", width="medium"),
                "MP": st.column_config.ProgressColumn("MasterPoints", format="%d", min_value=0, max_value=1000),
                "VP": st.column_config.NumberColumn("VitaPoints", format="%d%%"),
            },
            use_container_width=True,
            hide_index=True
        )
        
        st.caption("⚠️ Para editar valores masivos, se recomienda usar Notion directamente por seguridad de la base de datos.")
    else:
        st.warning("No se encontraron agentes en la base de datos.")

elif menu == "⚙️ Ajustes Globales":
    st.markdown("### ⚙️ CONTROL DE MISIÓN")
    st.info("Aquí podrás cambiar el estado del juego (En Curso / Finalizado) y gestionar variables globales. (Próximamente)")
    
    # Aquí podríamos agregar lógica para editar una base de datos de "Configuración" si creas una en Notion.
