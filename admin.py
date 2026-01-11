import streamlit as st
import requests
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Torre de Control", page_icon="⚡", layout="wide")

# --- SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    # Define una contraseña simple para ti en los secrets luego
    ADMIN_PASS = st.secrets.get("ADMIN_PASSWORD", "admin123") 
except:
    st.error("⚠️ Configura los secretos (incluyendo ADMIN_PASSWORD).")
    st.stop()

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- ESTILOS ---
st.markdown("""
    <style>
        .stat-box {
            background-color: #262730; padding: 10px; border-radius: 5px;
            border: 1px solid #444; text-align: center;
        }
        .req-card {
            background-color: #1E1E1E; border-left: 5px solid #FFD700;
            padding: 15px; margin-bottom: 10px; border-radius: 5px;
        }
    </style>
""", unsafe_allow_html=True)

# --- LOGIN DE PROFESOR ---
if "admin_logged" not in st.session_state: st.session_state.admin_logged = False

if not st.session_state.admin_logged:
    c1, c2, c3 = st.columns([1,1,1])
    with c2:
        st.markdown("### 🛡️ Acceso Restringido")
        pwd = st.text_input("Clave Maestra:", type="password")
        if st.button("Entrar"):
            if pwd == ADMIN_PASS:
                st.session_state.admin_logged = True
                st.rerun()
            else:
                st.error("Acceso Denegado")
    st.stop()

# --- FUNCIONES NOTION ---
def get_all_players():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    res = requests.post(url, headers=headers, json={})
    players = []
    if res.status_code == 200:
        for p in res.json()["results"]:
            props = p["properties"]
            try:
                nombre = props["Jugador"]["title"][0]["text"]["content"]
                players.append({
                    "id": p["id"],
                    "Nombre": nombre,
                    "MP": props["MP"]["number"] or 0,
                    "AP": props["AP"]["number"] or 0,
                    "VP": props["VP"]["number"] or 0
                })
            except: pass
    return pd.DataFrame(players).sort_values("Nombre")

def update_notion_stat(page_id, prop, new_value):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    data = {"properties": {prop: {"number": int(new_value)}}}
    requests.patch(url, headers=headers, json=data)

def delete_message(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    requests.patch(url, headers=headers, json={"archived": True})

# --- INTERFAZ PRINCIPAL ---
st.title("⚡ Torre de Control - AngioMasters")

tab_jugadores, tab_solicitudes = st.tabs(["👥 GESTIÓN JUGADORES", "📩 SOLICITUDES"])

# ==========================================
# 1. GESTIÓN JUGADORES
# ==========================================
with tab_jugadores:
    st.markdown("### Modificar Estadísticas")
    
    # Cargar jugadores
    df = get_all_players()
    
    if not df.empty:
        # Selector de alumno
        alumno_selec = st.selectbox("Seleccionar Agente:", df["Nombre"].tolist())
        
        # Obtener datos del seleccionado
        datos = df[df["Nombre"] == alumno_selec].iloc[0]
        pid = datos["id"]
        
       # Mostrar stats actuales (AQUÍ ESTÁ EL CAMBIO)
        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ MasterPoints (MP)", datos["MP"])
        c2.metric("⚡ AngioPoints (AP)", datos["AP"])
        
        # Agregamos la f-string f"{...}%" para que se vea el porcentaje
        c3.metric("❤️ VitaPoints (VP)", f"{datos['VP']}%") 
        
        st.divider()
        
        # --- ACCIONES RÁPIDAS ---
        col_mp, col_ap, col_vp = st.columns(3)
        
        with col_mp:
            st.markdown("#### ⭐ Ajustar MP")
            if st.button("+10 MP (Participación)", key="mp10"):
                update_notion_stat(pid, "MP", datos["MP"] + 10)
                st.success("Añadidos 10 MP")
                st.rerun()
            if st.button("+50 MP (Gran Logro)", key="mp50"):
                update_notion_stat(pid, "MP", datos["MP"] + 50)
                st.success("Añadidos 50 MP")
                st.rerun()
            
            val_mp = st.number_input("Manual MP", value=datos["MP"], key="n_mp")
            if st.button("Guardar MP", key="s_mp"):
                update_notion_stat(pid, "MP", val_mp)
                st.rerun()

        with col_ap:
            st.markdown("#### ⚡ Ajustar AP")
            if st.button("+5 AP (Bonus)", key="ap5"):
                update_notion_stat(pid, "AP", datos["AP"] + 5)
                st.rerun()
            val_ap = st.number_input("Manual AP", value=datos["AP"], key="n_ap")
            if st.button("Guardar AP", key="s_ap"):
                update_notion_stat(pid, "AP", val_ap)
                st.rerun()

        with col_vp:
            st.markdown("#### ❤️ Ajustar VP")
            if st.button("💔 -10 VP (Daño)", key="vp_minus"):
                update_notion_stat(pid, "VP", max(0, datos["VP"] - 10))
                st.rerun()
            if st.button("❤️ Curar Total (100)", key="vp_full"):
                update_notion_stat(pid, "VP", 100)
                st.rerun()
            val_vp = st.number_input("Manual VP", value=datos["VP"], key="n_vp")
            if st.button("Guardar VP", key="s_vp"):
                update_notion_stat(pid, "VP", val_vp)
                st.rerun()

# ==========================================
# 2. SOLICITUDES
# ==========================================
with tab_solicitudes:
    st.markdown("### Buzón de Habilidades y Mensajes")
    if st.button("🔄 Actualizar Buzón"): st.rerun()
    
    # Leer Solicitudes
    url_req = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    # Filtro: Solo las NO archivadas (Notion API trae activas por defecto)
    res_req = requests.post(url_req, headers=headers, json={})
    
    if res_req.status_code == 200:
        msgs = res_req.json()["results"]
        if not msgs:
            st.info("📭 No hay solicitudes pendientes.")
        
        for m in msgs:
            try:
                mid = m["id"]
                props = m["properties"]
                
                # Intentar leer remitente y mensaje
                remitente = "Anónimo"
                texto = "Sin contenido"
                
                # Ajusta esto según tus columnas reales de DB Solicitudes/Mensajes
                if "Remitente" in props:
                    t = props["Remitente"].get("title", [])
                    if t: remitente = t[0]["text"]["content"]
                
                if "Mensaje" in props:
                    r = props["Mensaje"].get("rich_text", [])
                    if r: texto = r[0]["text"]["content"]
                
                # Tarjeta
                with st.container():
                    col_txt, col_act = st.columns([3, 1])
                    with col_txt:
                        st.markdown(f"""
                        <div class="req-card">
                            <strong>👤 {remitente}</strong><br>
                            {texto}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_act:
                        # Detectar si es compra (busca la palabra 'Costo:' en el texto)
                        es_compra = "Costo:" in texto
                        costo = 0
                        if es_compra:
                            try:
                                # Extraer numero "Costo: 5 AP" -> 5
                                part = texto.split("Costo:")[1]
                                costo = int(part.split("AP")[0].strip())
                            except: pass
                        
                        if es_compra and costo > 0:
                            if st.button(f"✅ Aprobar (-{costo} AP)", key=f"ok_{mid}"):
                                # 1. Buscar jugador para restar puntos
                                df_p = get_all_players() # Recargamos para tener dato fresco
                                # Limpiamos nombre remitente (quitamos "SOLICITUD: ")
                                nombre_clean = remitente.replace("SOLICITUD: ", "").strip()
                                
                                jugador_row = df_p[df_p["Nombre"] == nombre_clean]
                                
                                if not jugador_row.empty:
                                    pid_jugador = jugador_row.iloc[0]["id"]
                                    ap_actual = jugador_row.iloc[0]["AP"]
                                    
                                    if ap_actual >= costo:
                                        # Restar Puntos
                                        update_notion_stat(pid_jugador, "AP", ap_actual - costo)
                                        # Borrar Mensaje
                                        delete_message(mid)
                                        st.success(f"Cobrado y Aprobado. {nombre_clean} tiene ahora {ap_actual-costo} AP.")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {nombre_clean} no tiene suficientes AP ({ap_actual}).")
                                else:
                                    st.error("No encontré al jugador en la base de datos.")
                                    
                        if st.button("🗑️ Borrar/Archivar", key=f"del_{mid}"):
                            delete_message(mid)
                            st.rerun()
            except Exception as e:
                st.error(f"Error leyendo mensaje: {e}")
