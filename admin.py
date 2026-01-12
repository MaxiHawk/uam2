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
        .req-card-msg {
            background: #0f1520; border: 1px solid #1c2e3e; border-left: 4px solid #00e5ff;
            padding: 15px; border-radius: 8px; margin-bottom: 10px;
        }
        .req-player { font-family: 'Orbitron'; font-size: 1.1em; color: #FFD700; font-weight: bold; }
        .req-detail { color: #b0bec5; font-size: 0.9em; margin-bottom: 10px; }
        
        /* BOTONES DE ACCIÓN */
        .stButton>button { border-radius: 4px; font-weight: bold; text-transform: uppercase; width: 100%; }
        
        /* KPI BOXES */
        .kpi-box {
            background: rgba(0, 229, 255, 0.05); border: 1px solid #004d66;
            padding: 15px; text-align: center; border-radius: 10px;
        }
        .kpi-val { font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: white; }
        .kpi-label { font-size: 0.8em; color: #4dd0e1; letter-spacing: 2px; text-transform: uppercase; }
        
        /* CONTROL PANEL */
        .control-panel {
            background: #0a141f; padding: 20px; border-radius: 12px; border: 1px solid #1c2e3e; margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES NOTION ---

def get_players():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    has_more = True
    next_cursor = None
    players = []

    while has_more:
        payload = {}
        if next_cursor: payload["start_cursor"] = next_cursor
        
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            for p in data["results"]:
                props = p["properties"]
                try:
                    name = props["Jugador"]["title"][0]["text"]["content"]
                    mp = props.get("MP", {}).get("number", 0)
                    ap = props.get("AP", {}).get("number", 0)
                    vp = props.get("VP", {}).get("number", 0)
                    
                    uni_obj = props.get("Universidad", {}).get("select")
                    uni = uni_obj["name"] if uni_obj else "Sin Asignar"
                    
                    ano_obj = props.get("Año", {}).get("select")
                    ano = ano_obj["name"] if ano_obj else "Sin Año"

                    squad_list = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                    squad = squad_list[0]["text"]["content"] if squad_list else "Sin Escuadrón"
                    
                    players.append({
                        "id": p["id"], 
                        "Aspirante": name, 
                        "Escuadrón": squad, 
                        "Universidad": uni,
                        "Generación": ano,
                        "MP": mp, "AP": ap, "VP": vp
                    })
                except: pass
            has_more = data["has_more"]
            next_cursor = data["next_cursor"]
        else:
            has_more = False
            
    return pd.DataFrame(players)

def get_pending_requests():
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {
        "filter": {
            "property": "Procesado",
            "checkbox": {
                "equals": False
            }
        }
    }
    res = requests.post(url, headers=headers, json=payload) 
    reqs = []
    if res.status_code == 200:
        for r in res.json()["results"]:
            props = r["properties"]
            try:
                title_list = props["Remitente"]["title"]
                remitente = title_list[0]["text"]["content"] if title_list else "Desconocido"
                msg_list = props["Mensaje"]["rich_text"]
                mensaje = msg_list[0]["text"]["content"] if msg_list else ""
                reqs.append({"id": r["id"], "remitente": remitente, "mensaje": mensaje})
            except: pass
    return reqs

def update_stat(player_id, stat_name, new_value):
    val = int(new_value) 
    url = f"https://api.notion.com/v1/pages/{player_id}"
    data = {"properties": {stat_name: {"number": val}}}
    res = requests.patch(url, headers=headers, json=data)
    return res.status_code == 200

def update_player_ap_by_name(player_name, cost):
    url_query = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Jugador", "title": {"equals": player_name}}}
    res = requests.post(url_query, headers=headers, json=payload)
    if res.status_code == 200 and res.json()["results"]:
        player_page = res.json()["results"][0]
        player_id = player_page["id"]
        current_ap = player_page["properties"]["AP"]["number"]
        new_ap = max(0, current_ap - cost)
        return update_stat(player_id, "AP", new_ap)
    return False

def mark_request_processed(page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    data = {"properties": {"Procesado": {"checkbox": True}}}
    requests.patch(url, headers=headers, json=data)

# --- LOGIN SYSTEM ---
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ COMANDO CENTRAL</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Credencial de Acceso:", type="password")
        if st.button("INICIAR ENLACE"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("⛔ ACCESO DENEGADO")
    st.stop()

# --- CARGAR DATOS GLOBALES ---
df_players = get_players()

# --- SIDEBAR (FILTROS) ---
with st.sidebar:
    st.title("🎛️ FILTROS DE MISIÓN")
    
    uni_opts = ["Todas"] + list(df_players["Universidad"].unique()) if not df_players.empty else ["Todas"]
    gen_opts = ["Todas"] + list(df_players["Generación"].unique()) if not df_players.empty else ["Todas"]
    
    sel_uni = st.selectbox("📍 Universidad:", uni_opts)
    sel_gen = st.selectbox("📅 Generación:", gen_opts)
    
    df_filtered = df_players.copy()
    if not df_players.empty:
        if sel_uni != "Todas":
            df_filtered = df_filtered[df_filtered["Universidad"] == sel_uni]
        if sel_gen != "Todas":
            df_filtered = df_filtered[df_filtered["Generación"] == sel_gen]
        
    st.divider()
    st.metric("Aspirantes Activos", len(df_filtered))
    
    if st.button("Cerrar Sesión"):
        st.session_state.admin_logged_in = False
        st.rerun()

# --- TABS ---
tab_req, tab_ops, tab_list = st.tabs(["📡 SOLICITUDES", "⚡ OPERACIONES DE CAMPO", "👥 NÓMINA"])

# ================= TAB 1: SOLICITUDES =================
with tab_req:
    st.markdown("### 📡 TRANSMISIONES ENTRANTES")
    reqs = get_pending_requests()
    
    if not reqs:
        st.success("✅ Bandeja de entrada vacía, Comandante.")
    else:
        for r in reqs:
            costo = 0
            skill_name = ""
            is_skill_req = False
            
            # Análisis Inteligente del Mensaje
            if "Costo:" in r['mensaje'] and "activar:" in r['mensaje']:
                is_skill_req = True
                try:
                    costo = int(r['mensaje'].split("Costo:")[1].split("AP")[0].strip())
                    skill_name = r['mensaje'].split("activar:")[1].split("(")[0].replace("'","").strip()
                except: pass
            
            player_name = r['remitente'].replace("SOLICITUD: ", "").strip()

            with st.container():
                # Estilo Diferente si es Mensaje General (Azul) o Compra (Dorado)
                card_class = "req-card" if is_skill_req else "req-card-msg"
                cost_text = f"⚡ -{costo} AP" if is_skill_req else "💬 MENSAJE GENERAL"
                title_text = f"Solicita: <strong>{skill_name}</strong>" if is_skill_req else "📩 Nueva Comunicación"
                
                st.markdown(f"""
                <div class="{card_class}">
                    <div style="display:flex; justify-content:space-between;">
                        <div class="req-player">{player_name}</div>
                        <div style="color:{'#FFD700' if is_skill_req else '#00e5ff'}; font-weight:bold;">{cost_text}</div>
                    </div>
                    <div class="req-detail">{title_text}</div>
                    <div style="font-size:0.9em; color:#fff; font-style:italic;">"{r['mensaje']}"</div>
                </div>
                """, unsafe_allow_html=True)
                
                c_yes, c_no = st.columns(2)
                
                if is_skill_req:
                    # Botones para Habilidad (Cobrar AP)
                    if c_yes.button(f"✅ APROBAR", key=f"ap_{r['id']}"):
                        ok = update_player_ap_by_name(player_name, costo)
                        if ok:
                            mark_request_processed(r['id'])
                            st.toast(f"Solicitud de {player_name} Aprobada")
                            time.sleep(1); st.rerun()
                        else: st.error("Error al actualizar AP.")
                    
                    if c_no.button(f"❌ RECHAZAR", key=f"den_{r['id']}"):
                        mark_request_processed(r['id'])
                        st.toast("Solicitud Denegada")
                        time.sleep(1); st.rerun()
                else:
                    # Botón para Mensaje (Solo Archivar)
                    if c_yes.button(f"📥 MARCAR COMO LEÍDO / ARCHIVAR", key=f"read_{r['id']}"):
                        mark_request_processed(r['id'])
                        st.toast("Mensaje Archivado")
                        time.sleep(1); st.rerun()

# ================= TAB 2: OPERACIONES (MODIFICAR PUNTOS) =================
with tab_ops:
    st.markdown("### ⚡ GESTIÓN TÁCTICA DE ASPIRANTES")
    
    if df_filtered.empty:
        st.warning("No hay aspirantes visibles con los filtros actuales.")
    else:
        aspirante_list = df_filtered["Aspirante"].tolist()
        selected_aspirante_name = st.selectbox("Seleccionar Aspirante para Modificación:", aspirante_list)
        
        player_data = df_filtered[df_filtered["Aspirante"] == selected_aspirante_name].iloc[0]
        pid = player_data["id"]
        curr_mp = player_data["MP"]
        curr_ap = player_data["AP"]
        curr_vp = player_data["VP"]
        
        st.markdown("---")
        
        c_mp, c_ap, c_vp = st.columns(3)
        
        with c_mp:
            st.markdown(f"<div class='kpi-box' style='border-color:#FFD700;'><div class='kpi-val' style='color:#FFD700;'>{curr_mp}</div><div class='kpi-label'>MasterPoints</div></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            mod_mp = st.number_input("Cantidad MP", min_value=0, value=10, key="n_mp")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ Sumar MP"):
                update_stat(pid, "MP", curr_mp + mod_mp)
                st.toast(f"MP Actualizado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ Restar MP"):
                update_stat(pid, "MP", max(0, curr_mp - mod_mp))
                st.toast(f"MP Actualizado"); time.sleep(0.5); st.rerun()

        with c_ap:
            st.markdown(f"<div class='kpi-box' style='border-color:#00e5ff;'><div class='kpi-val' style='color:#00e5ff;'>{curr_ap}</div><div class='kpi-label'>AngioPoints</div></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            mod_ap = st.number_input("Cantidad AP", min_value=0, value=5, key="n_ap")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ Sumar AP"):
                update_stat(pid, "AP", curr_ap + mod_ap)
                st.toast(f"AP Actualizado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ Restar AP"):
                update_stat(pid, "AP", max(0, curr_ap - mod_ap))
                st.toast(f"AP Actualizado"); time.sleep(0.5); st.rerun()

        with c_vp:
            st.markdown(f"<div class='kpi-box' style='border-color:#ff4b4b;'><div class='kpi-val' style='color:#ff4b4b;'>{curr_vp}%</div><div class='kpi-label'>VitaPoints</div></div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            mod_vp = st.number_input("Cantidad VP %", min_value=0, value=10, key="n_vp")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ Sanar VP"):
                update_stat(pid, "VP", min(100, curr_vp + mod_vp))
                st.toast("Aspirante Sanado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ Dañar VP"):
                update_stat(pid, "VP", max(0, curr_vp - mod_vp))
                st.toast("Daño Aplicado"); time.sleep(0.5); st.rerun()

# ================= TAB 3: NÓMINA =================
with tab_list:
    st.markdown("### 👥 NÓMINA DE ASPIRANTES (LECTURA)")
    st.dataframe(
        df_filtered,
        column_config={
            "Aspirante": st.column_config.TextColumn("Aspirante", width="medium"),
            "Escuadrón": st.column_config.TextColumn("Escuadrón", width="small"),
            "MP": st.column_config.ProgressColumn("MasterPoints", format="%d", min_value=0, max_value=1000),
            "VP": st.column_config.NumberColumn("VitaPoints", format="%d%%"),
        },
        use_container_width=True,
        hide_index=True
    )
