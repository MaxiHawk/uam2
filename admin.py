import streamlit as st
import requests
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Torre de Control", page_icon="⚡", layout="wide")

# --- GESTIÓN DE SECRETOS ---
try:
    NOTION_TOKEN = st.secrets["NOTION_TOKEN"]
    DB_JUGADORES_ID = st.secrets["DB_JUGADORES_ID"]
    DB_SOLICITUDES_ID = st.secrets["DB_SOLICITUDES_ID"]
    # Si no configuraste la clave, usa 'admin123' por defecto
    ADMIN_PASS = st.secrets.get("ADMIN_PASSWORD", "admin123") 
except:
    st.error("⚠️ Error Crítico: Faltan configurar los secretos en Streamlit Cloud.")
    st.stop()

headers = {
    "Authorization": "Bearer " + NOTION_TOKEN,
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# --- ESTILOS CSS (MODO DARK) ---
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
        /* Ajuste para inputs numéricos */
        input[type=number]::-webkit-inner-spin-button, 
        input[type=number]::-webkit-outer-spin-button { 
            -webkit-appearance: none; margin: 0; 
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
                st.error("❌ Acceso Denegado")
    st.stop()

# --- FUNCIONES DE NOTION ---
def get_all_players():
    """Descarga todos los jugadores para la lista de selección"""
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
    """Actualiza un valor numérico en Notion"""
    url = f"https://api.notion.com/v1/pages/{page_id}"
    # Convertimos a entero para asegurar compatibilidad
    data = {"properties": {prop: {"number": int(new_value)}}}
    requests.patch(url, headers=headers, json=data)

def delete_message(page_id):
    """Archiva un mensaje/solicitud (Soft Delete)"""
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
    
    df = get_all_players()
    
    if not df.empty:
        # Selector de alumno
        alumno_selec = st.selectbox("Seleccionar Agente:", df["Nombre"].tolist())
        
        # Obtener datos del seleccionado (Fila completa)
        datos = df[df["Nombre"] == alumno_selec].iloc[0]
        pid = datos["id"]
        
        # --- VISUALIZACIÓN DE MÉTRICAS ---
        c1, c2, c3 = st.columns(3)
        c1.metric("⭐ MasterPoints (MP)", int(datos["MP"]))
        c2.metric("⚡ AngioPoints (AP)", int(datos["AP"]))
        # VP formateado como Entero + %
        c3.metric("❤️ VitaPoints (VP)", f"{int(datos['VP'])}%")
        
        st.divider()
        
        # --- PANEL DE ACCIONES ---
        col_mp, col_ap, col_vp = st.columns(3)
        
        # COLUMNA MP
        with col_mp:
            st.markdown("#### ⭐ Ajustar MP")
            if st.button("+10 MP (Participación)", key="mp10"):
                update_notion_stat(pid, "MP", datos["MP"] + 10)
                st.success("✅ +10 MP")
                st.rerun()
            if st.button("+50 MP (Gran Logro)", key="mp50"):
                update_notion_stat(pid, "MP", datos["MP"] + 50)
                st.success("✅ +50 MP")
                st.rerun()
            
            # Input Manual MP
            val_mp = st.number_input("Manual MP", value=int(datos["MP"]), step=1, key="n_mp")
            if st.button("Guardar MP", key="s_mp"):
                update_notion_stat(pid, "MP", val_mp)
                st.rerun()

        # COLUMNA AP
        with col_ap:
            st.markdown("#### ⚡ Ajustar AP")
            if st.button("+5 AP (Bonus)", key="ap5"):
                update_notion_stat(pid, "AP", datos["AP"] + 5)
                st.success("✅ +5 AP")
                st.rerun()
            
            # Input Manual AP
            val_ap = st.number_input("Manual AP", value=int(datos["AP"]), step=1, key="n_ap")
            if st.button("Guardar AP", key="s_ap"):
                update_notion_stat(pid, "AP", val_ap)
                st.rerun()

        # COLUMNA VP (CORREGIDA)
        with col_vp:
            st.markdown("#### ❤️ Ajustar VP")
            if st.button("💔 -10 VP (Daño)", key="vp_minus"):
                nuevo_vp = max(0, int(datos["VP"]) - 10)
                update_notion_stat(pid, "VP", nuevo_vp)
                st.warning("⚠️ -10 VP Aplicado")
                st.rerun()
            if st.button("❤️ Curar Total (100%)", key="vp_full"):
                update_notion_stat(pid, "VP", 100)
                st.success("✅ Salud Restaurada")
                st.rerun()
            
            # Input Manual VP (Solo Enteros)
            val_vp = st.number_input("Manual VP (0-100)", value=int(datos["VP"]), step=1, key="n_vp")
            if st.button("Guardar VP", key="s_vp"):
                update_notion_stat(pid, "VP", val_vp)
                st.rerun()

# ==========================================
# 2. SOLICITUDES
# ==========================================
with tab_solicitudes:
    st.markdown("### Buzón de Habilidades y Mensajes")
    if st.button("🔄 Actualizar Buzón"): st.rerun()
    
    # Consultar DB Solicitudes
    url_req = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    res_req = requests.post(url_req, headers=headers, json={})
    
    if res_req.status_code == 200:
        msgs = res_req.json()["results"]
        if not msgs:
            st.info("📭 No hay solicitudes pendientes.")
        
        for m in msgs:
            try:
                mid = m["id"]
                props = m["properties"]
                
                # Extracción segura de datos
                remitente = "Anónimo"
                texto = "Sin contenido"
                
                # Ajusta estos nombres si tus columnas se llaman diferente en Notion
                if "Remitente" in props:
                    t = props["Remitente"].get("title", [])
                    if t: remitente = t[0]["text"]["content"]
                
                if "Mensaje" in props:
                    r = props["Mensaje"].get("rich_text", [])
                    if r: texto = r[0]["text"]["content"]
                
                # Renderizar Tarjeta
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
                        # Detectar costo en el texto (Formato esperado: "Costo: X AP")
                        es_compra = "Costo:" in texto
                        costo = 0
                        if es_compra:
                            try:
                                part = texto.split("Costo:")[1]
                                costo = int(part.split("AP")[0].strip())
                            except: pass
                        
                        if es_compra and costo > 0:
                            if st.button(f"✅ Aprobar (-{costo} AP)", key=f"ok_{mid}"):
                                # 1. Recargar datos actuales para evitar restar sobre saldo viejo
                                df_p = get_all_players()
                                nombre_clean = remitente.replace("SOLICITUD: ", "").strip()
                                jugador_row = df_p[df_p["Nombre"] == nombre_clean]
                                
                                if not jugador_row.empty:
                                    pid_jugador = jugador_row.iloc[0]["id"]
                                    ap_actual = jugador_row.iloc[0]["AP"]
                                    
                                    if ap_actual >= costo:
                                        # Restar y Borrar
                                        update_notion_stat(pid_jugador, "AP", ap_actual - costo)
                                        delete_message(mid)
                                        st.success(f"Cobrado. Nuevo saldo: {ap_actual-costo} AP.")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Saldo insuficiente ({ap_actual} AP).")
                                else:
                                    st.error("Jugador no encontrado en DB.")
                                    
                        if st.button("🗑️ Borrar", key=f"del_{mid}"):
                            delete_message(mid)
                            st.rerun()
            except Exception as e:
                st.error(f"Error leyendo mensaje: {e}")
