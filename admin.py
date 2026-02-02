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
from modules.notion_api import aprobar_solicitud_habilidad

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except FileNotFoundError:
    st.error("⚠️ Error: Falta ADMIN_PASSWORD en .streamlit/secrets.toml")
    st.stop()

st.set_page_config(page_title="Centro de Mando | Praxis", page_icon="🎛️", layout="wide")
headers = HEADERS

# --- ESTILOS CSS ÉPICOS (V6 - ROBUST) ---
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <style>
        .stApp { background-color: #050810; color: #e0f7fa; }
        
        /* Cards de Solicitudes */
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
        
        /* Estilo Farmeo */
        .farm-box {
            border: 2px solid #00e5ff; background: rgba(0, 229, 255, 0.05);
            padding: 15px; border-radius: 10px; margin-bottom: 20px;
        }
    </style>
""", unsafe_allow_html=True)

# --- FUNCIONES NOTION ROBUSTAS (SCAN & MATCH) ---
def buscar_config_id(key_target):
    """
    Descarga TODA la config (son pocas filas) y busca manualmente la clave.
    Esto evita errores de indexación de la API de Notion.
    """
    if not DB_CONFIG_ID: return None, False, "Todas"
    
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        res = requests.post(url, headers=headers, json={})
        if res.status_code == 200:
            results = res.json().get("results", [])
            for page in results:
                props = page["properties"]
                # Obtenemos el título (Clave)
                try:
                    clave_actual = props["Clave"]["title"][0]["text"]["content"]
                    if clave_actual == key_target:
                        estado = props.get("Activo", {}).get("checkbox", False)
                        # Intentamos leer el filtro, si existe
                        filtro_list = props.get("Filtro", {}).get("rich_text", [])
                        filtro_val = filtro_list[0]["text"]["content"] if filtro_list else "Todas"
                        return page["id"], estado, filtro_val
                except: continue
    except Exception as e: print(f"Error config: {e}")
    return None, False, "Todas"

def actualizar_config(page_id, nuevo_estado, nuevo_filtro=None):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    props = {"Activo": {"checkbox": nuevo_estado}}
    
    if nuevo_filtro is not None:
        props["Filtro"] = {"rich_text": [{"text": {"content": nuevo_filtro}}]}
        
    requests.patch(url, headers=headers, json={"properties": props})

# --- OTRAS FUNCIONES ---
def registrar_log_admin(usuario_afectado, tipo_evento, detalle, universidad="Admin", año="Admin"):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Evento": {"title": [{"text": {"content": tipo_evento}}]},
            "Jugador": {"rich_text": [{"text": {"content": usuario_afectado}}]},
            "Tipo": {"select": {"name": "Sistema"}},
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
                    
                    players.append({
                        "id": p["id"], "Aspirante": name, 
                        "Escuadrón": props.get("Nombre Escuadrón", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Sin Escuadrón"),
                        "Universidad": uni,
                        "Generación": gen,
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

def update_stat(player_id, stat_name, new_value):
    url = f"https://api.notion.com/v1/pages/{player_id}"
    requests.patch(url, headers=headers, json={"properties": {stat_name: {"number": int(new_value)}}})

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
    
    # --- FILTROS GLOBALES (CON GENERACIÓN) ---
    uni_opts = ["Todas"] + (list(df_players["Universidad"].unique()) if not df_players.empty else [])
    sel_uni = st.selectbox("📍 Universidad:", uni_opts)
    
    gen_opts = ["Todas"] + (list(df_players["Generación"].unique()) if not df_players.empty else [])
    sel_gen = st.selectbox("📅 Generación (Año):", gen_opts)
    
    # Lógica de Filtrado
    df_filtered = df_players.copy()
    if not df_players.empty:
        if sel_uni != "Todas": df_filtered = df_filtered[df_filtered["Universidad"] == sel_uni]
        if sel_gen != "Todas": df_filtered = df_filtered[df_filtered["Generación"] == sel_gen]
    
    st.divider()
    
    # --- 🚨 GESTIÓN DE SISTEMA (MANTENIMIENTO & FARMEO) ---
    st.markdown("### 🚨 SISTEMA")
    
    # 1. MODO MANTENIMIENTO
    mant_id, mant_estado, _ = buscar_config_id("MODO_MANTENIMIENTO")
    if mant_id:
        nuevo_mant = st.toggle("MODO MANTENIMIENTO", value=mant_estado)
        if nuevo_mant != mant_estado:
            actualizar_config(mant_id, nuevo_mant)
            st.toast("Configuración Actualizada"); time.sleep(1); st.rerun()
    else:
        st.error("BD Config: No se halló 'MODO_MANTENIMIENTO'")

    st.divider()

    # 2. DROP SUMINISTROS (FARMEO DIFERENCIADO)
    st.markdown("### 📦 FARMEO DIARIO")
    drop_id, drop_estado, drop_filtro_actual = buscar_config_id("DROP_SUMINISTROS")
    
    if drop_id:
        with st.container():
            # Mostramos un marco visual si está activo
            if drop_estado:
                st.markdown(f"""<div class="farm-box">🟢 <b>FARMEO ACTIVO</b><br>Objetivo: {drop_filtro_actual}</div>""", unsafe_allow_html=True)
            
            # Selector de Universidad Objetivo (Basado en las Unis disponibles en Players)
            target_uni_opts = ["Todas"] + (list(df_players["Universidad"].unique()) if not df_players.empty else [])
            
            # Si ya hay un filtro guardado, intentamos ponerlo como default
            idx_def = 0
            if drop_filtro_actual in target_uni_opts:
                idx_def = target_uni_opts.index(drop_filtro_actual)
                
            uni_objetivo = st.selectbox("🎯 Universidad Objetivo:", target_uni_opts, index=idx_def, key="drop_target")
            
            # El Switch
            nuevo_drop = st.toggle("ACTIVAR FARMEO", value=drop_estado)
            
            # Lógica de cambio: Si cambia el switch O si cambia la uni mientras está encendido
            if nuevo_drop != drop_estado or (drop_estado and uni_objetivo != drop_filtro_actual):
                if st.button("💾 APLICAR CAMBIOS FARMEO"):
                    actualizar_config(drop_id, nuevo_drop, uni_objetivo)
                    st.toast(f"Drop {uni_objetivo}: {'ON' if nuevo_drop else 'OFF'}")
                    time.sleep(1); st.rerun()
    else:
        st.error("BD Config: No se halló 'DROP_SUMINISTROS'")
        
    st.divider()
    if st.button("🧹 Limpiar Caché"): st.cache_data.clear(); st.rerun()
    if st.button("Cerrar Sesión"): st.session_state.admin_logged_in = False; st.rerun()

tab_req, tab_ops, tab_list = st.tabs(["📡 SOLICITUDES", "⚡ OPERACIONES", "👥 NÓMINA"])

# --- TAB 1: SOLICITUDES ---
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
                tipo_obj = props.get("Tipo", {}).get("select")
                tipo = tipo_obj["name"] if tipo_obj else "Mensaje"
                
                raw_date = item["created_time"]
                try:
                    utc_dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    fecha_str = utc_dt.astimezone(pytz.timezone('America/Santiago')).strftime("%d/%m %H:%M")
                except: fecha_str = "Fecha desc."
                status = props.get("Status", {}).get("select", {}).get("name", "Pendiente")
                solicitudes.append({"id": item["id"], "remitente": remitente, "mensaje": mensaje, "fecha": fecha_str, "status": status, "tipo": tipo})
    except: pass
    
    if not solicitudes:
        st.info(f"📭 Bandeja vacía ({filtro_estado})")
    else:
        for r in solicitudes:
            es_habilidad = "Habilidad" in r['tipo'] or "Poder" in r['tipo']
            es_compra = "Compra" in r['tipo'] or "Mercado" in r['tipo']
            
            if es_habilidad: border_color, icon_type = "#d500f9", "⚡ PODER"
            elif es_compra: border_color, icon_type = "#FFD700", "🛒 COMPRA"
            else: border_color, icon_type = "#00e5ff", "💬 MENSAJE"

            with st.container():
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
                    with c_obs: obs_text = st.text_input("Respuesta / Obs:", key=f"obs_{r['id']}")
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
                                    finalize_request(r['id'], "Aprobado", obs_text or "Entrega autorizada.")
                                    st.success("Entregado"); time.sleep(1); st.rerun()
                            else: 
                                if st.button("✅ RESPONDER", key=f"ok_{r['id']}"):
                                    finalize_request(r['id'], "Respondido", obs_text or "Leído")
                                    st.success("Listo"); time.sleep(1); st.rerun()
                        with c_no:
                            if st.button("❌ RECHAZAR", key=f"no_{r['id']}"):
                                finalize_request(r['id'], "Rechazado", obs_text or "Rechazado")
                                st.rerun()

# --- TAB 2 Y 3: SIN CAMBIOS (YA ESTABAN OK) ---
with tab_ops:
    if df_filtered.empty: st.warning("Sin datos.")
    else:
        st.markdown("### ⚡ GESTIÓN INDIVIDUAL")
        sel_aspirante = st.selectbox("Aspirante:", df_filtered["Aspirante"].tolist())
        if sel_aspirante:
            p_data = df_filtered[df_filtered["Aspirante"] == sel_aspirante].iloc[0]
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("MP", p_data['MP'])
                if st.button("➕ MP", key="mp"): update_stat(p_data["id"], "MP", p_data['MP']+10); st.toast("OK"); time.sleep(0.5); st.rerun()
            with c2:
                st.metric("AP", p_data['AP'])
                if st.button("➕ AP", key="ap"): update_stat(p_data["id"], "AP", p_data['AP']+5); st.toast("OK"); time.sleep(0.5); st.rerun()
            
            st.markdown("---")
            st.markdown("<div class='mass-ops-box'>### 💣 BOMBARDEO MASIVO</div>", unsafe_allow_html=True)
            t_squad = st.selectbox("Escuadrón:", df_filtered["Escuadrón"].unique())
            motivo = st.text_input("Motivo:")
            val_mp = st.number_input("MP Masivo", 0)
            if st.button("🚀 EJECUTAR"):
                targets = df_filtered[df_filtered["Escuadrón"] == t_squad]
                for i, (_, s) in enumerate(targets.iterrows()):
                    if val_mp: update_stat(s["id"], "MP", s["MP"]+val_mp)
                    registrar_log_admin(s["Aspirante"], "Masivo", motivo, s["Universidad"], s["Generación"])
                st.success("Hecho"); time.sleep(1); st.rerun()

with tab_list:
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
