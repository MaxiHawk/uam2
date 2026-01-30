import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime
import pytz 
from modules.notion_api import aprobar_solicitud_habilidad

# --- REEMPLAZA DESDE "GESTIÓN DE SECRETOS" HASTA LA DEFINICIÓN DE "headers" CON ESTO ---
from config import (
    NOTION_TOKEN, HEADERS, DB_JUGADORES_ID, DB_SOLICITUDES_ID,
    DB_LOGS_ID, NOTION_TOKEN # Importamos lo necesario
)
# Recuperamos la contraseña de admin directo de los secrets (esa no está en config.py usualmente)
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except FileNotFoundError:
    st.error("⚠️ Error: Falta ADMIN_PASSWORD en .streamlit/secrets.toml")
    st.stop()

st.set_page_config(page_title="Centro de Mando | Praxis", page_icon="🎛️", layout="wide")

# Usamos los headers que ya definiste en config.py
headers = HEADERS
# ---------------------------------------------------------------------------------------
# --- GENERACIÓN DE LISTA DE INSIGNIAS (Sincronizado con APP) ---
BADGE_OPTIONS = []
for i in range(1, 10): BADGE_OPTIONS.append(f"Misión {i}")
for i in range(1, 8): BADGE_OPTIONS.append(f"Hazaña {i}")
for i in range(1, 4): BADGE_OPTIONS.append(f"Expedición {i}")

# --- CSS TÁCTICO ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Roboto:wght@300;400;700&display=swap');
        
        h1, h2, h3 { font-family: 'Orbitron', sans-serif; color: #00e5ff; }
        .stApp { background-color: #050810; color: #e0f7fa; }
        
        .req-card {
            background: #0f1520; border: 1px solid #1c2e3e; border-left: 4px solid #FFD700;
            padding: 15px; border-radius: 8px; margin-bottom: 10px;
        }
        .req-card-msg {
            background: #0f1520; border: 1px solid #1c2e3e; border-left: 4px solid #00e5ff;
            padding: 15px; border-radius: 8px; margin-bottom: 10px;
        }
        .req-player { font-family: 'Orbitron'; font-size: 1.1em; color: #FFD700; font-weight: bold; display: flex; align-items: center; gap: 10px; }
        .req-gen-tag { font-family: 'Roboto'; font-size: 0.7em; color: #8899a6; border: 1px solid #333; padding: 2px 6px; border-radius: 4px; }
        .req-detail { color: #b0bec5; font-size: 0.9em; margin-bottom: 10px; }
        .stButton>button { border-radius: 4px; font-weight: bold; text-transform: uppercase; width: 100%; }
        
        .kpi-box {
            background: rgba(0, 229, 255, 0.05); border: 1px solid #004d66;
            padding: 15px; text-align: center; border-radius: 10px;
        }
        .kpi-val { font-family: 'Orbitron'; font-size: 2em; font-weight: 900; color: white; }
        .kpi-label { font-size: 0.8em; color: #4dd0e1; letter-spacing: 2px; text-transform: uppercase; }

        .kpi-mini {
            background: rgba(0, 0, 0, 0.3); border: 1px solid #1c2e3e;
            padding: 8px; text-align: center; border-radius: 6px; margin-bottom: 10px;
        }
        .kpi-mini-val { font-family: 'Orbitron'; font-size: 1.2em; font-weight: bold; color: white; }
        .kpi-mini-lbl { font-size: 0.6em; color: #aaa; letter-spacing: 1px; }
        
        .mass-ops-box {
            border: 2px dashed #ff9100;
            background: rgba(255, 145, 0, 0.05);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }

        .badge-ops-box {
            border: 2px dashed #D4AF37;
            background: rgba(212, 175, 55, 0.05);
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }
        
        .refresh-btn { margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIÓN DE LOGGING ---
def registrar_log_admin(usuario_afectado, tipo_evento, detalle, universidad="Admin", año="Admin"):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    chile_tz = pytz.timezone('America/Santiago')
    now_iso = datetime.now(chile_tz).isoformat()

    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Evento": {"title": [{"text": {"content": tipo_evento}}]},
            "Jugador": {"rich_text": [{"text": {"content": usuario_afectado}}]},
            "Tipo": {"select": {"name": "Sistema"}},
            "Detalle": {"rich_text": [{"text": {"content": detalle}}]},
            "Fecha": {"date": {"start": now_iso}},
            "Universidad": {"select": {"name": universidad}},
            "Año": {"select": {"name": año}}
        }
    }
    try: requests.post(url, headers=headers, json=payload)
    except: pass

# --- FUNCIONES NOTION ---
@st.cache_data(ttl=60)
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
                    name_list = props.get("Jugador", {}).get("title", [])
                    name = name_list[0]["text"]["content"] if name_list else "Sin Nombre"
                    
                    mp = props.get("MP", {}).get("number", 0)
                    ap = props.get("AP", {}).get("number", 0)
                    vp = props.get("VP", {}).get("number", 0)
                    
                    uni_obj = props.get("Universidad", {}).get("select")
                    uni = uni_obj["name"] if uni_obj else "Sin Asignar"
                    
                    ano_obj = props.get("Año", {}).get("select")
                    ano = ano_obj["name"] if ano_obj else "Sin Año"

                    squad_list = props.get("Nombre Escuadrón", {}).get("rich_text", [])
                    squad = squad_list[0]["text"]["content"] if squad_list else "Sin Escuadrón"
                    
                    # NUEVO: Obtener Insignias Actuales
                    insignias_objs = props.get("Insignias", {}).get("multi_select", [])
                    insignias_list = [x["name"] for x in insignias_objs]

                    players.append({
                        "id": p["id"], 
                        "Aspirante": name, 
                        "Escuadrón": squad, 
                        "Universidad": uni,
                        "Generación": ano,
                        "MP": mp, "AP": ap, "VP": vp,
                        "Insignias": insignias_list # Guardamos la lista actual
                    })
                except: pass
            has_more = data["has_more"]
            next_cursor = data["next_cursor"]
        else:
            has_more = False
    return pd.DataFrame(players)

def get_pending_requests(debug_mode=False):
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {
        "page_size": 100,
        "sorts": [{"timestamp": "created_time", "direction": "descending"}]
    }
    res = requests.post(url, headers=headers, json=payload) 
    reqs = []
    if res.status_code == 200:
        data = res.json()["results"]
        for r in data:
            props = r["properties"]
            try:
                is_processed = props.get("Procesado", {}).get("checkbox", False)
                if not is_processed:
                    title_obj = props.get("Remitente", {}).get("title", [])
                    remitente = title_obj[0]["text"]["content"] if title_obj else "Desconocido"
                    msg_obj = props.get("Mensaje", {}).get("rich_text", [])
                    mensaje = msg_obj[0]["text"]["content"] if msg_obj else ""
                    tipo_obj = props.get("Tipo", {}).get("select")
                    tipo = tipo_obj["name"] if tipo_obj else "Mensaje"
                    uni_obj = props.get("Universidad", {}).get("select")
                    uni = uni_obj["name"] if uni_obj else "Sin Asignar"
                    ano_obj = props.get("Año", {}).get("select")
                    ano = ano_obj["name"] if ano_obj else "Sin Año"
                    created_time = r["created_time"]
                    
                    # Intentar obtener fecha respuesta si existe (para debug)
                    resp_date = None
                    if "Fecha respuesta" in props and props["Fecha respuesta"]["date"]:
                        resp_date = props["Fecha respuesta"]["date"]["start"]

                    reqs.append({
                        "id": r["id"], "remitente": remitente, "mensaje": mensaje, "tipo": tipo,
                        "universidad": uni, "año": ano, "created": created_time, "resp_date": resp_date
                    })
            except Exception as e: pass
    return reqs

def update_stat_batch(player_id, updates_dict):
    """
    Actualiza múltiples propiedades de un jugador en una sola llamada.
    updates_dict: {"MP": 100, "AP": 50, "VP": 100}
    """
    url = f"https://api.notion.com/v1/pages/{player_id}"
    props = {}
    for key, val in updates_dict.items():
        props[key] = {"number": val}
    
    data = {"properties": props}
    res = requests.patch(url, headers=headers, json=data)
    return res.status_code == 200

def update_badges_batch(player_id, new_badges_list):
    """
    Actualiza la lista de insignias de un jugador (Multi-select).
    new_badges_list: ["Misión 1", "Veterano"]
    """
    url = f"https://api.notion.com/v1/pages/{player_id}"
    
    # Formato Notion para Multi-select
    badges_payload = [{"name": b} for b in new_badges_list]
    
    data = {
        "properties": {
            "Insignias": {"multi_select": badges_payload}
        }
    }
    res = requests.patch(url, headers=headers, json=data)
    return res.status_code == 200

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

def finalize_request(page_id, status_label, observation_text=""):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    chile_tz = pytz.timezone('America/Santiago')
    now_iso = datetime.now(chile_tz).isoformat()
    data = {
        "properties": {
            "Procesado": {"checkbox": True},
            "Status": {"select": {"name": status_label}},
            "Fecha respuesta": {"date": {"start": now_iso}},
            "Observaciones": {"rich_text": [{"text": {"content": observation_text}}]}
        }
    }
    res = requests.patch(url, headers=headers, json=data)
    return res.status_code == 200

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
    st.title("🎛️ PANEL DE CONTROL")
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
    debug_mode = st.checkbox("🛠️ Modo Diagnóstico")
    st.divider()
    if st.button("🧹 Limpiar Caché Global"):
        st.cache_data.clear()
        st.toast("✅ Memoria del sistema purgada.")
        time.sleep(1)
        st.rerun()
    if st.button("Cerrar Sesión"):
        st.session_state.admin_logged_in = False
        st.rerun()

# --- TABS ---
tab_req, tab_ops, tab_list = st.tabs(["📡 SOLICITUDES", "⚡ OPERACIONES DE CAMPO", "👥 NÓMINA"])

# ================= TAB 1: SOLICITUDES =================
with tab_requests:
    st.markdown("### 📨 SOLICITUDES PENDIENTES")
    
    # Filtros de estado
    filtro_estado = st.radio("Estado:", ["Pendiente", "Respondido", "Rechazado", "Aprobado"], horizontal=True)
    
    # Cargar solicitudes (Lógica simplificada para admin)
    # Nota: Aquí deberías tener una función 'cargar_todas_solicitudes' en notion_api.py
    # Si no la tienes, usaremos una consulta directa rápida aquí:
    url_req = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload_req = {
        "filter": {"property": "Status", "select": {"equals": filtro_estado}},
        "sorts": [{"property": "Fecha de creación", "direction": "descending"}]
    }
    
    solicitudes = []
    try:
        res = requests.post(url_req, headers=headers, json=payload_req, timeout=10)
        if res.status_code == 200:
            for item in res.json()["results"]:
                props = item["properties"]
                # Extracción segura
                remitente_list = props.get("Remitente", {}).get("title", [])
                remitente = remitente_list[0]["text"]["content"] if remitente_list else "Anónimo"
                
                msg_list = props.get("Mensaje", {}).get("rich_text", [])
                mensaje = msg_list[0]["text"]["content"] if msg_list else ""
                
                fecha = props.get("Fecha de creación", {}).get("date", {}).get("start", "")
                
                solicitudes.append({
                    "id": item["id"],
                    "remitente": remitente,
                    "mensaje": mensaje,
                    "fecha": fecha
                })
    except: st.error("Error conectando con Notion")

    if not solicitudes:
        st.info("📭 No hay solicitudes en este estado.")
    else:
        for req in solicitudes:
            with st.container():
                st.markdown(f"""
                <div class="monitor-card">
                    <div style="display:flex; justify-content:space-between; color: #00e5ff; margin-bottom:5px;">
                        <strong>👤 {req['remitente']}</strong>
                        <small>{req['fecha']}</small>
                    </div>
                    <div style="color: #ccc; font-family: monospace; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 5px;">
                        {req['mensaje']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # --- BOTONERA DE ACCIÓN ---
                col_actions = st.columns([1, 1, 2])
                
                # 1. BOTÓN ACEPTAR (Cobrar y Aprobar)
                with col_actions[0]:
                    # Solo mostramos Aceptar si está Pendiente
                    if filtro_estado == "Pendiente":
                        if st.button("✅ ACEPTAR", key=f"btn_ok_{req['id']}", use_container_width=True):
                            with st.spinner("Procesando cobro..."):
                                exito, msg = aprobar_solicitud_habilidad(
                                    req['id'], 
                                    req['remitente'], 
                                    req['mensaje']
                                )
                                if exito:
                                    st.success(msg)
                                    time.sleep(1.5)
                                    st.rerun()
                                else:
                                    st.error(msg)
                
                # 2. BOTÓN RECHAZAR
                with col_actions[1]:
                    if filtro_estado == "Pendiente":
                        if st.button("❌ RECHAZAR", key=f"btn_no_{req['id']}", use_container_width=True):
                            url_update = f"https://api.notion.com/v1/pages/{req['id']}"
                            payload_rej = {
                                "properties": {
                                    "Status": {"select": {"name": "Rechazado"}},
                                    "Respuesta Comando": {"rich_text": [{"text": {"content": "Solicitud denegada por el Mando."}}]}
                                }
                            }
                            requests.patch(url_update, headers=headers, json=payload_rej)
                            st.rerun()

                # 3. RESPONDER (Solo texto)
                with col_actions[2]:
                    with st.popover("💬 RESPONDER", use_container_width=True):
                        txt_reply = st.text_area("Mensaje:", key=f"txt_{req['id']}")
                        if st.button("ENVIAR", key=f"send_{req['id']}"):
                            url_update = f"https://api.notion.com/v1/pages/{req['id']}"
                            payload_rep = {
                                "properties": {
                                    "Status": {"select": {"name": "Respuesta"}}, # O "Respondido"
                                    "Respuesta Comando": {"rich_text": [{"text": {"content": txt_reply}}]}
                                }
                            }
                            requests.patch(url_update, headers=headers, json=payload_rep)
                            st.success("Enviado")
                            time.sleep(1)
                            st.rerun()
                
                st.markdown("---")

# ================= TAB 2: OPERACIONES =================
with tab_ops:
    if df_filtered.empty:
        st.warning("No hay aspirantes visibles con los filtros actuales.")
    else:
        # --- SECCIÓN INDIVIDUAL ---
        st.markdown("### ⚡ GESTIÓN INDIVIDUAL")
        aspirante_list = df_filtered["Aspirante"].tolist()
        selected_aspirante_name = st.selectbox("Seleccionar Aspirante:", aspirante_list)
        player_data = df_filtered[df_filtered["Aspirante"] == selected_aspirante_name].iloc[0]
        pid, p_uni, p_gen = player_data["id"], player_data["Universidad"], player_data["Generación"]
        
        c_mp, c_ap, c_vp = st.columns(3)
        with c_mp:
            st.markdown(f"<div class='kpi-box' style='border-color:#FFD700;'><div class='kpi-val' style='color:#FFD700;'>{player_data['MP']}</div><div class='kpi-label'>MasterPoints</div></div>", unsafe_allow_html=True)
            mod_mp = st.number_input("MP", min_value=0, value=10, key="n_mp")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ MP", key="add_mp"):
                update_stat(pid, "MP", player_data['MP'] + mod_mp)
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual MP", f"Se sumaron {mod_mp} MP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ MP", key="sub_mp"):
                update_stat(pid, "MP", max(0, player_data['MP'] - mod_mp))
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual MP", f"Se restaron {mod_mp} MP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()
        
        with c_ap:
            st.markdown(f"<div class='kpi-box' style='border-color:#00e5ff;'><div class='kpi-val' style='color:#00e5ff;'>{player_data['AP']}</div><div class='kpi-label'>AngioPoints</div></div>", unsafe_allow_html=True)
            mod_ap = st.number_input("AP", min_value=0, value=5, key="n_ap")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ AP", key="add_ap"):
                update_stat(pid, "AP", player_data['AP'] + mod_ap)
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual AP", f"Se sumaron {mod_ap} AP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ AP", key="sub_ap"):
                update_stat(pid, "AP", max(0, player_data['AP'] - mod_ap))
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual AP", f"Se restaron {mod_ap} AP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()

        with c_vp:
            st.markdown(f"<div class='kpi-box' style='border-color:#ff4b4b;'><div class='kpi-val' style='color:#ff4b4b;'>{player_data['VP']}%</div><div class='kpi-label'>VitaPoints</div></div>", unsafe_allow_html=True)
            mod_vp = st.number_input("VP %", min_value=0, value=10, key="n_vp")
            c_add, c_sub = st.columns(2)
            if c_add.button("➕ VP", key="add_vp"):
                update_stat(pid, "VP", min(100, player_data['VP'] + mod_vp))
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual VP", f"Se sanaron {mod_vp}% VP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()
            if c_sub.button("➖ VP", key="sub_vp"):
                update_stat(pid, "VP", max(0, player_data['VP'] - mod_vp))
                registrar_log_admin(player_data['Aspirante'], "Ajuste Manual VP", f"Se dañaron {mod_vp}% VP", p_uni, p_gen)
                st.toast("Actualizado"); time.sleep(0.5); st.rerun()

        # --- SECCIÓN MASIVA (PUNTOS) ---
        st.markdown("---")
        st.markdown("<div class='mass-ops-box'>", unsafe_allow_html=True)
        st.markdown("### 💣 BOMBARDEO DE SUMINISTROS (MP/AP/VP)")
        
        # Filtro de escuadrones disponibles en el filtro actual
        available_squads = df_filtered["Escuadrón"].unique().tolist()
        target_squad = st.selectbox("🎯 Seleccionar Escuadrón Objetivo:", available_squads, key="squad_stat")
        
        c_m1, c_m2, c_m3 = st.columns(3)
        mass_mp = c_m1.number_input("MP a Asignar", value=0, step=5)
        mass_ap = c_m2.number_input("AP a Asignar", value=0, step=5)
        mass_vp = c_m3.number_input("VP a Asignar", value=0, step=5)
        
        mass_reason = st.text_input("📝 Motivo de la Operación (OBLIGATORIO):", placeholder="Ej: Bonificación Misión 1, Castigo por retraso, etc.")
        
        if st.button("🚀 EJECUTAR OPERACIÓN", use_container_width=True):
            if not mass_reason:
                st.error("⚠️ DEBES ESCRIBIR UN MOTIVO PARA LA OPERACIÓN.")
            else:
                targets = df_filtered[df_filtered["Escuadrón"] == target_squad]
                total_targets = len(targets)
                
                if total_targets > 0:
                    prog_bar = st.progress(0)
                    status_text = st.empty()
                    
                    count = 0
                    for index, soldier in targets.iterrows():
                        status_text.text(f"Procesando: {soldier['Aspirante']}...")
                        
                        # Calcular nuevos valores
                        new_mp = max(0, soldier["MP"] + mass_mp)
                        new_ap = max(0, soldier["AP"] + mass_ap)
                        new_vp = max(0, min(100, soldier["VP"] + mass_vp))
                        
                        # Actualizar Notion
                        updates = {}
                        if mass_mp != 0: updates["MP"] = new_mp
                        if mass_ap != 0: updates["AP"] = new_ap
                        if mass_vp != 0: updates["VP"] = new_vp
                        
                        if updates:
                            update_stat_batch(soldier["id"], updates)
                            
                            # Registrar Log
                            cambios_str = []
                            if mass_mp > 0: cambios_str.append(f"+{mass_mp} MP")
                            elif mass_mp < 0: cambios_str.append(f"{mass_mp} MP")
                            
                            if mass_ap > 0: cambios_str.append(f"+{mass_ap} AP")
                            elif mass_ap < 0: cambios_str.append(f"{mass_ap} AP")

                            if mass_vp > 0: cambios_str.append(f"+{mass_vp} VP")
                            elif mass_vp < 0: cambios_str.append(f"{mass_vp} VP")
                            
                            log_msg = f"[{mass_reason}] Ajuste Masivo: {', '.join(cambios_str)}"
                            registrar_log_admin(soldier["Aspirante"], "Operación Masiva", log_msg, soldier["Universidad"], soldier["Generación"])
                        
                        count += 1
                        prog_bar.progress(count / total_targets)
                        time.sleep(0.1) 
                        
                    st.success(f"✅ Operación completada. {count} aspirantes actualizados.")
                    time.sleep(2)
                    st.rerun()
                else:
                    st.warning("El escuadrón seleccionado no tiene miembros visibles.")
        
        st.markdown("</div>", unsafe_allow_html=True)

        # --- SECCIÓN MASIVA (INSIGNIAS) ---
        st.markdown("<div class='badge-ops-box'>", unsafe_allow_html=True)
        st.markdown("### 🎖️ CONDECORACIÓN DE CAMPO (INSIGNIAS)")
        
        badge_target_squad = st.selectbox("🎯 Seleccionar Escuadrón a Condecorar:", available_squads, key="squad_badge")
        selected_badge = st.selectbox("🏅 Seleccionar Insignia:", BADGE_OPTIONS)
        
        if st.button("🎖️ ASIGNAR INSIGNIA AL ESCUADRÓN", use_container_width=True):
            targets_b = df_filtered[df_filtered["Escuadrón"] == badge_target_squad]
            total_targets_b = len(targets_b)
            
            if total_targets_b > 0:
                prog_bar_b = st.progress(0)
                status_text_b = st.empty()
                
                count_b = 0
                for index, soldier in targets_b.iterrows():
                    status_text_b.text(f"Condecorando: {soldier['Aspirante']}...")
                    
                    # Obtener insignias actuales (Ya vienen en el DF gracias a la mejora en get_players)
                    current_badges = soldier["Insignias"]
                    
                    # Verificar si ya la tiene para no duplicar
                    if selected_badge not in current_badges:
                        new_badges_list = current_badges + [selected_badge]
                        update_badges_batch(soldier["id"], new_badges_list)
                        registrar_log_admin(soldier["Aspirante"], "Condecoración", f"Se otorgó insignia: {selected_badge}", soldier["Universidad"], soldier["Generación"])
                    
                    count_b += 1
                    prog_bar_b.progress(count_b / total_targets_b)
                    time.sleep(0.1)
                
                st.success(f"✅ Misión cumplida. {count_b} insignias asignadas.")
                time.sleep(2)
                st.rerun()
            else:
                st.warning("No hay aspirantes en este escuadrón.")

        st.markdown("</div>", unsafe_allow_html=True)


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
            "Insignias": st.column_config.ListColumn("Insignias")
        },
        use_container_width=True,
        hide_index=True
    )
