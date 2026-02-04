import streamlit as st
import requests
import pandas as pd
import time
import re
from datetime import datetime
import pytz 

# --- IMPORTS Y CONFIGURACIÓN ---
from config import (
    NOTION_TOKEN, HEADERS, DB_JUGADORES_ID, DB_SOLICITUDES_ID,
    DB_LOGS_ID, DB_CONFIG_ID
)
# Incluimos todas las herramientas nuevas (Mercado, Misiones, etc.)
from modules.notion_api import aprobar_solicitud_habilidad, cargar_todas_misiones_admin, aprobar_solicitud_mercado

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except FileNotFoundError:
    st.error("⚠️ Error: Falta ADMIN_PASSWORD en .streamlit/secrets.toml")
    st.stop()

st.set_page_config(page_title="Centro de Mando | Praxis", page_icon="🎛️", layout="wide")
headers = HEADERS

# --- ESTILOS CSS ÉPICOS (V10 - SITREP ADAPTATIVO) ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        .stApp { background-color: #050810; color: #e0f7fa; }
        
        /* SITREP METRICS */
        div[data-testid="stMetricValue"] { font-family: 'Orbitron'; color: #00e5ff !important; font-size: 1.2rem !important; }
        div[data-testid="stMetricLabel"] { color: #888 !important; font-size: 0.8em !important; }

        .war-room-header {
            background: linear-gradient(90deg, rgba(0,229,255,0.1) 0%, rgba(0,0,0,0) 100%);
            border-left: 5px solid #00e5ff; padding: 15px;
            border-radius: 0 10px 10px 0; margin-bottom: 20px;
        }
        .war-room-title { font-family: 'Orbitron'; font-size: 1.5em; color: #fff; font-weight: bold; margin: 0; }
        .war-room-sub { color: #00e5ff; font-size: 0.8em; letter-spacing: 2px; text-transform: uppercase; }

        .req-card-epic {
            background: linear-gradient(135deg, #0f1520 0%, #050810 100%);
            border: 1px solid #1c2e3e; border-radius: 12px; padding: 20px;
            margin-bottom: 15px; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }
        .req-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; margin-bottom: 10px;}
        .req-player-name { font-family: 'Orbitron'; font-size: 1.4em; font-weight: 900; color: #fff; }
        .req-badge { font-family: 'Orbitron'; font-size: 0.7em; padding: 4px 10px; border-radius: 4px; margin-left: 10px; vertical-align: middle; }
        .badge-pending { background: #ffea0020; color: #ffea00; border: 1px solid #ffea00; }
        .badge-approved { background: #00e67620; color: #00e676; border: 1px solid #00e676; }
        .badge-rejected { background: #ff174420; color: #ff1744; border: 1px solid #ff1744; }
        .req-type-tag { font-family: monospace; font-size: 0.8em; padding: 2px 6px; border-radius: 3px; background: #333; color: #aaa; margin-right: 10px; }
        .req-body { font-size: 1.0em; color: #b0bec5; background: rgba(0,0,0,0.3); padding: 10px; border-radius: 6px; }
        
        div[data-testid="column"] button { font-family: 'Orbitron'; font-size: 0.8em; text-transform: uppercase; }
        .farm-box { border: 2px solid #00e5ff; background: rgba(0, 229, 255, 0.05); padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES NOTION ---
def buscar_config_id(key_target):
    if not DB_CONFIG_ID: return None, False, "Todas"
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        res = requests.post(url, headers=headers, json={})
        if res.status_code == 200:
            results = res.json().get("results", [])
            for page in results:
                props = page["properties"]
                try:
                    clave_actual = props["Clave"]["title"][0]["text"]["content"]
                    if clave_actual == key_target:
                        estado = props.get("Activo", {}).get("checkbox", False)
                        filtro_list = props.get("Filtro", {}).get("rich_text", [])
                        filtro_val = filtro_list[0]["text"]["content"] if filtro_list else "Todas"
                        return page["id"], estado, filtro_val
                except: continue
    except: pass
    return None, False, "Todas"

def actualizar_config(page_id, nuevo_estado, nuevo_filtro=None):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    props = {"Activo": {"checkbox": nuevo_estado}}
    if nuevo_filtro is not None:
        props["Filtro"] = {"rich_text": [{"text": {"content": nuevo_filtro}}]}
    requests.patch(url, headers=headers, json={"properties": props})

def registrar_log_admin(usuario_afectado, titulo_evento, detalle, universidad="Admin", año="Admin", tipo_categoria="Sistema"):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Evento": {"title": [{"text": {"content": titulo_evento}}]},
            "Jugador": {"rich_text": [{"text": {"content": usuario_afectado}}]},
            "Tipo": {"select": {"name": tipo_categoria}},
            "Detalle": {"rich_text": [{"text": {"content": detalle}}]},
            "Fecha": {"date": {"start": now_iso}},
            "Universidad": {"select": {"name": str(universidad)}},
            "Año": {"select": {"name": str(año)}}
        }
    }
    requests.post(url, headers=headers, json=payload)

@st.cache_data(ttl=60)
def get_players():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    has_more = True; next_cursor = None; players = []
    while has_more:
        payload = {} if not next_cursor else {"start_cursor": next_cursor}
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            data = res.json()
            for p in data["results"]:
                props = p["properties"]
                try:
                    name = props["Jugador"]["title"][0]["text"]["content"]
                    uni = props.get("Universidad", {}).get("select", {}).get("name", "Sin Asignar")
                    gen = props.get("Año", {}).get("select", {}).get("name", "Sin Año")
                    estado = props.get("Estado UAM", {}).get("select", {}).get("name", "Desconocido").strip()
                    
                    players.append({
                        "id": p["id"], "Aspirante": name, 
                        "Escuadrón": props.get("Nombre Escuadrón", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Sin Escuadrón"),
                        "Universidad": uni,
                        "Generación": gen,
                        "Estado": estado,
                        "MP": props.get("MP", {}).get("number", 0), 
                        "AP": props.get("AP", {}).get("number", 0), 
                        "VP": props.get("VP", {}).get("number", 0)
                    })
                except: pass
            has_more = data["has_more"]; next_cursor = data["next_cursor"]
        else: has_more = False
    return pd.DataFrame(players)

def update_stat_batch(player_id, updates_dict):
    url = f"https://api.notion.com/v1/pages/{player_id}"
    props = {k: {"number": v} for k, v in updates_dict.items()}
    requests.patch(url, headers=headers, json={"properties": props})

def finalize_request(page_id, status_label, observation_text=""):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    data = {
        "properties": {
            "Procesado": {"checkbox": True},
            "Status": {"select": {"name": status_label}},
            "Fecha respuesta": {"date": {"start": now_iso}},
            "Observaciones": {"rich_text": [{"text": {"content": observation_text}}]}
        }
    }
    requests.patch(url, headers=headers, json=data)

@st.cache_data(ttl=60)
def get_pending_count():
    if not DB_SOLICITUDES_ID: return 0
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    payload = {"filter": {"property": "Status", "select": {"equals": "Pendiente"}}, "page_size": 100}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=3)
        if res.status_code == 200:
            c = len(res.json()["results"])
            return f"{c}+" if res.json()["has_more"] else c
    except: pass
    return 0

# --- LOGIN ---
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if not st.session_state.admin_logged_in:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.markdown("<h2 style='text-align:center;'>🛡️ COMANDO CENTRAL</h2>", unsafe_allow_html=True)
        pwd = st.text_input("Credencial:", type="password")
        if st.button("ACCEDER"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else: st.error("⛔ ACCESO DENEGADO")
    st.stop()

# --- MAIN ---
df_players = get_players()
with st.sidebar:
    st.title("🎛️ CONTROL")
    
    # --- 1. FILTROS TÁCTICOS (AHORA ARRIBA) ---
    uni_opts = ["Todas"] + (list(df_players["Universidad"].unique()) if not df_players.empty else [])
    sel_uni = st.selectbox("📍 Universidad:", uni_opts)
    
    gen_opts = ["Todas"] + (list(df_players["Generación"].unique()) if not df_players.empty else [])
    sel_gen = st.selectbox("📅 Generación (Año):", gen_opts)
    
    # Lógica de Filtrado Centralizado
    df_global = df_players.copy()
    if not df_players.empty:
        if sel_uni != "Todas": df_global = df_global[df_global["Universidad"] == sel_uni]
        if sel_gen != "Todas": df_global = df_global[df_global["Generación"] == sel_gen]
    
    # Filtro Activos (Para SITREP y Operaciones)
    df_active = df_global[df_global["Estado"] != "Finalizado"]

    st.divider()

    # --- 2. SITREP ADAPTATIVO ---
    st.markdown("### 📊 SITREP")
    
    # Métricas basadas en los FILTROS ACTUALES
    val_aspirantes = len(df_active)
    val_mp = df_active["MP"].sum()
    val_ap = df_active["AP"].sum()
    val_pendientes = get_pending_count() # Se mantiene global por rendimiento

    # Formateo (1.000)
    fmt_mp = f"{val_mp:,.0f}".replace(",", ".")
    fmt_ap = f"{val_ap:,.0f}".replace(",", ".")
    
    c_s1, c_s2 = st.columns(2)
    c_s1.metric("Aspirantes", val_aspirantes, help="Aspirantes Activos (Según filtros)")
    c_s2.metric("Pendientes", val_pendientes, help="Solicitudes Pendientes (Global)")
    
    c_s3, c_s4 = st.columns(2)
    c_s3.metric("Total MP", fmt_mp, help="Suma de MasterPoints filtrados")
    c_s4.metric("Total AP", fmt_ap, help="Suma de AngioPoints filtrados")
    
    st.divider()
    
    # --- 3. SISTEMAS DE MANTENIMIENTO ---
    st.markdown("### 🚨 SISTEMA")
    mant_id, mant_estado, _ = buscar_config_id("MODO_MANTENIMIENTO")
    if mant_id:
        nuevo_mant = st.toggle("MODO MANTENIMIENTO", value=mant_estado)
        if nuevo_mant != mant_estado:
            actualizar_config(mant_id, nuevo_mant); st.toast("Actualizado"); time.sleep(1); st.rerun()
    else: st.error("Error Config Mantenimiento")

    # --- 4. FARMEO ---
    st.divider()
    st.markdown("### 📦 FARMEO DIARIO")
    drop_id, drop_estado, drop_filtro_actual = buscar_config_id("DROP_SUMINISTROS")
    if drop_id:
        with st.container():
            if drop_estado: st.markdown(f"""<div class="farm-box">🟢 <b>FARMEO ACTIVO</b><br>Objetivo: {drop_filtro_actual}</div>""", unsafe_allow_html=True)
            target_uni_opts = ["Todas"] + (list(df_players["Universidad"].unique()) if not df_players.empty else [])
            idx_def = target_uni_opts.index(drop_filtro_actual) if drop_filtro_actual in target_uni_opts else 0
            uni_objetivo = st.selectbox("🎯 Objetivo:", target_uni_opts, index=idx_def, key="drop_target")
            nuevo_drop = st.toggle("ACTIVAR FARMEO", value=drop_estado)
            if nuevo_drop != drop_estado or (drop_estado and uni_objetivo != drop_filtro_actual):
                if st.button("💾 APLICAR"): actualizar_config(drop_id, nuevo_drop, uni_objetivo); st.toast("Actualizado"); time.sleep(1); st.rerun()
    
    st.divider()
    if st.button("🧹 Limpiar Caché"): st.cache_data.clear(); st.rerun()
    if st.button("Cerrar Sesión"): st.session_state.admin_logged_in = False; st.rerun()

tab_req, tab_ops, tab_list = st.tabs(["📡 SOLICITUDES", "⚡ OPERACIONES", "👥 NÓMINA"])

# --- TAB 1: SOLICITUDES (CON FIX DE COBRO) ---
with tab_req:
    c_title, c_refresh = st.columns([4, 1])
    with c_title: st.markdown("### 📡 TRANSMISIONES ENTRANTES")
    with c_refresh: 
        if st.button("🔄 REFRESCAR"): st.rerun()

    filtro_estado = st.radio("Estado:", ["Pendiente", "Respondido", "Rechazado", "Aprobado"], horizontal=True, index=0)
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
                remitente = props.get("Remitente", {}).get("title", [{}])[0].get("text", {}).get("content", "Anónimo")
                mensaje = props.get("Mensaje", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                tipo = props.get("Tipo", {}).get("select", {}).get("name", "Mensaje")
                raw_date = item["created_time"]
                try: 
                    utc_dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    fecha_str = utc_dt.astimezone(pytz.timezone('America/Santiago')).strftime("%d/%m %H:%M")
                except: fecha_str = "Fecha desc."
                status = props.get("Status", {}).get("select", {}).get("name", "Pendiente")
                solicitudes.append({"id": item["id"], "remitente": remitente, "mensaje": mensaje, "fecha": fecha_str, "status": status, "tipo": tipo})
    except: pass
    
    if not solicitudes: st.info(f"📭 Bandeja vacía ({filtro_estado})")
    else:
        for r in solicitudes:
            # FIX: COMPARACIÓN INSENSIBLE A MAYÚSCULAS
            tipo_upper = str(r['tipo']).upper()
            es_habilidad = "HABILIDAD" in tipo_upper or "PODER" in tipo_upper
            es_compra = "COMPRA" in tipo_upper or "MERCADO" in tipo_upper

            if es_habilidad: border_color, icon_type = "#d500f9", "⚡ PODER"
            elif es_compra: border_color, icon_type = "#FFD700", "🛒 COMPRA"
            else: border_color, icon_type = "#00e5ff", "💬 MENSAJE"

            st.markdown(f"""
            <div class="req-card-epic" style="border-left: 4px solid {border_color};">
                <div class="req-header">
                    <div class="req-player-name">{r['remitente']}<span class="req-badge badge-{r['status'].lower()}">{r['status']}</span></div>
                    <div><span class="req-type-tag">{icon_type}</span><span style="font-size:0.8em; color:#666;">{r['fecha']}</span></div>
                </div>
                <div class="req-body">{r['mensaje']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if filtro_estado == "Pendiente":
                c_obs, c_acts = st.columns([3, 2])
                with c_obs: 
                    obs_text = st.text_input("Respuesta / Obs:", key=f"obs_{r['id']}")
                    # CAJA DE COBRO
                    costo_final = 0
                    if es_compra:
                        import re
                        match = re.search(r'Costo:\s*(\d+)', r['mensaje'])
                        costo_detectado = int(match.group(1)) if match else 0
                        st.markdown(f"<div style='font-size:0.8em; color:#FFD700; margin-bottom:5px;'>💰 Confirmar Cobro (AP):</div>", unsafe_allow_html=True)
                        costo_final = st.number_input("Monto a descontar:", value=costo_detectado, step=50, key=f"cost_{r['id']}", label_visibility="collapsed")

                with c_acts:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    c_ok, c_no = st.columns(2)
                    with c_ok:
                        if es_habilidad:
                            if st.button("⚡ APROBAR", key=f"ok_{r['id']}", type="primary"):
                                exito, msg = aprobar_solicitud_habilidad(r['id'], r['remitente'], r['mensaje'])
                                if exito: st.success(msg); time.sleep(1); st.rerun()
                                else: st.error(msg)
                        elif es_compra:
                            if st.button("🛒 APROBAR", key=f"ok_{r['id']}", type="primary"):
                                with st.spinner("Procesando cobro..."):
                                    exito, msg = aprobar_solicitud_mercado(r['id'], r['remitente'], costo_final, obs_text or "Entrega autorizada.")
                                    if exito: st.success(msg); time.sleep(1); st.rerun()
                                    else: st.error(msg)
                        else: 
                            if st.button("✅ RESPONDER", key=f"ok_{r['id']}"):
                                finalize_request(r['id'], "Respondido", obs_text or "Leído")
                                st.success("Listo"); time.sleep(1); st.rerun()
                    with c_no:
                        if st.button("❌ RECHAZAR", key=f"no_{r['id']}"):
                            finalize_request(r['id'], "Rechazado", obs_text or "Rechazado"); st.rerun()

# --- TAB 2: OPERACIONES (WAR ROOM) ---
with tab_ops:
    if df_global.empty: st.warning("Sin datos visibles.")
    else:
        # --- GESTIÓN INDIVIDUAL (TODOS) ---
        st.markdown("""<div style="background: rgba(0, 229, 255, 0.05); border-left: 5px solid #00e5ff; padding: 15px; border-radius: 0 10px 10px 0; margin-bottom: 20px;"><h3 style="margin:0; color:#fff; font-family:'Orbitron';">⚡ EXPEDIENTE TÁCTICO INDIVIDUAL</h3></div>""", unsafe_allow_html=True)

        selected_aspirante_name = st.selectbox("Seleccionar Aspirante:", df_global["Aspirante"].tolist())
        
        if selected_aspirante_name:
            p_data = df_global[df_global["Aspirante"] == selected_aspirante_name].iloc[0]
            
            estado_real = p_data['Estado']
            if estado_real == "Finalizado":
                status_color, status_icon, status_label = "#ff1744", "🎓", "FINALIZADO"
            else:
                status_color, status_icon, status_label = "#00e676", "🛡️", estado_real.upper()

            st.markdown(f"""
<div style="background: linear-gradient(90deg, #0a1018 0%, #1c2e3e 100%); border: 1px solid #333; border-radius: 10px; padding: 20px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
    <div>
        <div style="font-family:'Orbitron'; font-size:1.5em; color:#fff; font-weight:bold; letter-spacing:1px;">{p_data['Aspirante']}</div>
        <div style="color:#aaa; font-size:0.9em; margin-top:5px;">ESCUADRÓN: <span style="color:#00e5ff;">{p_data['Escuadrón']}</span> | GENERACIÓN: <span style="color:#fff;">{p_data['Generación']}</span></div>
    </div>
    <div style="text-align:right;">
        <div style="background:{status_color}20; color:{status_color}; border:1px solid {status_color}; padding:5px 15px; border-radius:20px; font-size:0.8em; font-weight:bold; display:inline-block;">{status_label}</div>
        <div style="margin-top:5px; font-size:2em;">{status_icon}</div>
    </div>
</div>
""", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"<div style='background:rgba(255, 215, 0, 0.05); padding:10px; border-radius:8px; border:1px solid #FFD70030; text-align:center;'><h2 style='color:#FFD700; margin:0;'>{p_data['MP']}</h2><div style='color:#FFD700; font-size:0.8em; font-weight:bold;'>MASTER POINTS (MP)</div></div>", unsafe_allow_html=True)
                delta_mp = st.number_input("Ajustar MP", value=0, step=10, key="d_mp")
            with c2:
                st.markdown(f"<div style='background:rgba(0, 229, 255, 0.05); padding:10px; border-radius:8px; border:1px solid #00e5ff30; text-align:center;'><h2 style='color:#00e5ff; margin:0;'>{p_data['AP']}</h2><div style='color:#00e5ff; font-size:0.8em; font-weight:bold;'>ANGIO POINTS (AP)</div></div>", unsafe_allow_html=True)
                delta_ap = st.number_input("Ajustar AP", value=0, step=10, key="d_ap")
            with c3:
                st.markdown(f"<div style='background:rgba(255, 23, 68, 0.05); padding:10px; border-radius:8px; border:1px solid #ff174430; text-align:center;'><h2 style='color:#ff1744; margin:0;'>{p_data['VP']}%</h2><div style='color:#ff1744; font-size:0.8em; font-weight:bold;'>VITA POINTS (VP)</div></div>", unsafe_allow_html=True)
                delta_vp = st.number_input("Ajustar VP", value=0, step=10, key="d_vp")

            st.markdown("<br>", unsafe_allow_html=True)
            reason_indiv = st.text_input("📝 Motivo del ajuste (Requerido):", placeholder="Ej: Bonificación por excelencia...")
            
            if st.button("💾 ACTUALIZAR EXPEDIENTE", type="primary", use_container_width=True):
                if delta_mp == 0 and delta_ap == 0 and delta_vp == 0: st.warning("⚠️ Sin cambios.")
                elif not reason_indiv: st.error("⚠️ Motivo obligatorio.")
                else:
                    updates, log_details = {}, []
                    if delta_mp != 0: updates["MP"] = int(max(0, p_data['MP'] + delta_mp)); log_details.append(f"{'+' if delta_mp > 0 else ''}{delta_mp} MP")
                    if delta_ap != 0: updates["AP"] = int(max(0, p_data['AP'] + delta_ap)); log_details.append(f"{'+' if delta_ap > 0 else ''}{delta_ap} AP")
                    if delta_vp != 0: updates["VP"] = int(max(0, min(100, p_data['VP'] + delta_vp))); log_details.append(f"{'+' if delta_vp > 0 else ''}{delta_vp} VP")
                    if updates:
                        update_stat_batch(p_data["id"], updates)
                        full_log = f"{reason_indiv} | {', '.join(log_details)}"
                        registrar_log_admin(p_data['Aspirante'], "Ajuste Manual", full_log, p_data['Universidad'], p_data['Generación'], "Sistema")
                        st.success("✅ Datos actualizados."); time.sleep(1.5); st.rerun()

            st.markdown("---")
            with st.expander("📜 HISTORIAL OPERATIVO RECIENTE (Últimos 5 Eventos)", expanded=False):
                def get_local_history(name_target):
                    if not DB_LOGS_ID: return []
                    u = f"https://api.notion.com/v1/databases/{DB_LOGS_ID}/query"
                    p = {"filter": {"property": "Jugador", "rich_text": {"contains": name_target}}, "sorts": [{"property": "Fecha", "direction": "descending"}], "page_size": 5}
                    try:
                        r = requests.post(u, headers=headers, json=p, timeout=5)
                        history = []
                        if r.status_code == 200:
                            for i in r.json()["results"]:
                                pr = i["properties"]
                                evt = pr["Evento"]["title"][0]["text"]["content"] if pr["Evento"]["title"] else "-"
                                det = pr["Detalle"]["rich_text"][0]["text"]["content"] if pr["Detalle"]["rich_text"] else "-"
                                raw_d = pr["Fecha"]["date"]["start"] if pr["Fecha"]["date"] else ""
                                try: dt = datetime.fromisoformat(raw_d.replace('Z', '+00:00')); date_str = dt.strftime("%d/%m %H:%M")
                                except: date_str = raw_d
                                history.append({"FECHA": date_str, "EVENTO": evt, "DETALLE": det})
                        return history
                    except: return []
                
                historial = get_local_history(p_data['Aspirante'])
                if historial: st.table(pd.DataFrame(historial))
                else: st.info("Sin registros recientes.")
        
        st.markdown("---")
        
        # --- WAR ROOM (SOLO ACTIVOS) ---
        if df_active.empty: st.info("No hay escuadrones activos para operaciones masivas.")
        else:
            st.markdown("""<div class="war-room-header"><h3 class="war-room-title">🛰️ WAR ROOM: OPERACIONES DE ESCUADRÓN</h3><div class="war-room-sub">PROTOCOLOS DE RECOMPENSA Y SANCIÓN MASIVA</div></div>""", unsafe_allow_html=True)
            
            c_squad, c_mode = st.columns([2, 1])
            with c_squad:
                squads_disponibles = df_active["Escuadrón"].unique()
                target_squad = st.selectbox("🎯 Escuadrón Objetivo:", squads_disponibles, key="sq_mass")
            with c_mode:
                mode_op = st.radio("Protocolo:", ["🎁 AIRDROP (Premio)", "💣 BOMBARDEO (Castigo)"], horizontal=True, label_visibility="collapsed")

            if "AIRDROP" in mode_op:
                st.caption("📦 Despliegue de suministros tácticos por cumplimiento de misión.")
                misiones_data = cargar_todas_misiones_admin(sel_uni)
                if not misiones_data: mission_map = {}; lista_nombres = ["Misión Genérica"]
                else: mission_map = {m['nombre']: m for m in misiones_data}; lista_nombres = list(mission_map.keys())
                
                c_mis, c_custom = st.columns([2, 1])
                with c_mis: mision_seleccionada_nombre = st.selectbox("📜 Misión / Actividad:", lista_nombres)
                
                current_mission_data = mission_map.get(mision_seleccionada_nombre, {})
                current_rewards = current_mission_data.get("rewards", {})
                real_mission_name = current_mission_data.get("raw_name", mision_seleccionada_nombre)

                if "mass_mp_val" not in st.session_state: st.session_state.mass_mp_val = 0
                if "mass_ap_val" not in st.session_state: st.session_state.mass_ap_val = 0
                if "mass_reason" not in st.session_state: st.session_state.mass_reason = ""
                if "mass_title" not in st.session_state: st.session_state.mass_title = ""

                defaults = {"gold": [150, 100], "silver": [100, 75], "bronze": [70, 50], "part": [30, 30]}

                def set_rewards(rank_key, label_log, emoji):
                    notion_r = current_rewards.get(rank_key, {})
                    r_mp, r_ap = notion_r.get("mp", 0), notion_r.get("ap", 0)
                    if r_mp == 0 and r_ap == 0: r_mp, r_ap = defaults.get(rank_key, [0,0])
                    st.session_state.in_mp = int(r_mp)
                    st.session_state.in_ap = int(r_ap)
                    st.session_state.mass_mp_val = int(r_mp)
                    st.session_state.mass_ap_val = int(r_ap)
                    st.session_state.mass_reason = f"{emoji} {label_log}: {real_mission_name}"
                    st.session_state.mass_title = f"🏆 Recompensa: {real_mission_name}"

                st.markdown("##### 🏅 SELECCIONA EL RANGO DE VICTORIA")
                cols_rank = st.columns(4)
                with cols_rank[0]: 
                    if st.button("🥇 1er LUGAR", use_container_width=True): set_rewards("gold", "1er Lugar", "🥇")
                with cols_rank[1]: 
                    if st.button("🥈 2do LUGAR", use_container_width=True): set_rewards("silver", "2do Lugar", "🥈")
                with cols_rank[2]: 
                    if st.button("🥉 3er LUGAR", use_container_width=True): set_rewards("bronze", "3er Lugar", "🥉")
                with cols_rank[3]: 
                    if st.button("🎖️ PARTICIPACIÓN", use_container_width=True): set_rewards("part", "Participación", "🎖️")

                st.markdown(f"""<div style="background:rgba(255,255,255,0.05); padding:15px; border-radius:10px; border:1px solid #333; margin-top:10px;"><div style="font-size:0.8em; color:#aaa;">CONFIGURACIÓN DEL ENVÍO:</div><div style="font-family:'Orbitron'; color:#fff; font-size:1.1em;">{st.session_state.mass_reason if st.session_state.mass_reason else 'Selecciona un rango arriba...'}</div></div>""", unsafe_allow_html=True)
                
                c_val1, c_val2, c_go = st.columns([1, 1, 2])
                val_mp = c_val1.number_input("MP a enviar:", value=st.session_state.mass_mp_val, key="in_mp")
                val_ap = c_val2.number_input("AP a enviar:", value=st.session_state.mass_ap_val, key="in_ap")
                
                with c_go:
                    st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                    if st.button("🚀 EJECUTAR AIRDROP MASIVO", type="primary", use_container_width=True):
                        if not st.session_state.mass_reason: st.error("Selecciona rango.")
                        else:
                            targets = df_active[df_active["Escuadrón"] == target_squad]
                            if targets.empty: st.warning("No hay aspirantes activos.")
                            else:
                                bar = st.progress(0, text="Desplegando..."); total = len(targets)
                                log_t, log_d = st.session_state.mass_title, f"{st.session_state.mass_reason} | Recompensa: +{val_mp} MP, +{val_ap} AP"
                                for i, (_, s) in enumerate(targets.iterrows()):
                                    ups = {}; 
                                    if val_mp > 0: ups["MP"] = s["MP"] + val_mp
                                    if val_ap > 0: ups["AP"] = s["AP"] + val_ap
                                    if ups: update_stat_batch(s["id"], ups); registrar_log_admin(s["Aspirante"], log_t, log_d, s["Universidad"], s["Generación"], "Misión")
                                    bar.progress((i + 1) / total); time.sleep(0.1)
                                st.success(f"✅ ¡Operación Exitosa! {total} aspirantes."); time.sleep(2); st.rerun()
            
            else:
                st.error("⚠️ ZONA DE PELIGRO: Acciones punitivas.")
                c1, c2 = st.columns(2)
                dmg_vp = c1.number_input("Daño a VP", value=0, min_value=0)
                pen_mp = c2.number_input("Penalización MP", value=0, min_value=0)
                reason_bomb = st.text_input("Motivo del Castigo:")
                confirm = st.checkbox("Confirmar orden de fuego", key="nuke_confirm")
                if st.button("💣 EJECUTAR BOMBARDEO", type="secondary", disabled=not confirm, use_container_width=True):
                    if not reason_bomb: st.error("Falta motivo.")
                    else:
                        targets = df_active[df_active["Escuadrón"] == target_squad]
                        if targets.empty: st.warning("Sin objetivos.")
                        else:
                            bar = st.progress(0, text="Atacando..."); total = len(targets)
                            log_bt, log_bd = f"💀 Sanción: {reason_bomb}", f"BOMBARDEO: {reason_bomb} | -{pen_mp} MP, -{dmg_vp} VP"
                            for i, (_, s) in enumerate(targets.iterrows()):
                                ups = {}
                                if pen_mp > 0: ups["MP"] = max(0, s["MP"] - pen_mp)
                                if dmg_vp > 0: ups["VP"] = max(0, s["VP"] - dmg_vp)
                                if ups: update_stat_batch(s["id"], ups); registrar_log_admin(s["Aspirante"], log_bt, log_bd, s["Universidad"], s["Generación"], "Sanción")
                                bar.progress((i + 1) / total); time.sleep(0.1)
                            st.toast("💥 BOMBARDEO COMPLETADO", icon="🔥"); time.sleep(2); st.rerun()

with tab_list:
    st.markdown("### 👥 NÓMINA FILTRADA (SOLO ACTIVOS)")
    if df_active.empty: st.info("No hay alumnos activos con los filtros actuales.")
    else: st.dataframe(df_active, use_container_width=True, hide_index=True)
