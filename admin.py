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
    DB_LOGS_ID
)
from modules.notion_api import aprobar_solicitud_habilidad

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except FileNotFoundError:
    st.error("⚠️ Error: Falta ADMIN_PASSWORD en .streamlit/secrets.toml")
    st.stop()

st.set_page_config(page_title="Centro de Mando | Praxis", page_icon="🎛️", layout="wide")
headers = HEADERS

# --- ESTILOS CSS ÉPICOS (V3) ---
st.markdown("""
    <style>
        /* Importamos la fuente directamente aquí para asegurar que cargue */
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
        
        .stApp { background-color: #050810; color: #e0f7fa; }
        
        /* TARJETA DE SOLICITUD MEJORADA */
        .req-card-epic {
            background: linear-gradient(135deg, #0f1520 0%, #050810 100%);
            border: 1px solid #1c2e3e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 15px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
            transition: all 0.3s ease;
        }
        
        .req-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
        }
        
        .req-player-name {
            font-family: 'Orbitron', sans-serif;
            font-size: 1.4em;
            font-weight: 900;
            color: #fff;
            letter-spacing: 1px;
            text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        .req-badge {
            font-family: 'Orbitron', sans-serif;
            font-size: 0.7em;
            font-weight: bold;
            padding: 4px 10px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 1px;
            box-shadow: 0 0 10px rgba(0,0,0,0.5);
        }
        
        .badge-pending { background: rgba(255, 234, 0, 0.15); color: #ffea00; border: 1px solid #ffea00; text-shadow: 0 0 5px #ffea00; }
        .badge-approved { background: rgba(0, 230, 118, 0.15); color: #00e676; border: 1px solid #00e676; text-shadow: 0 0 5px #00e676; }
        .badge-rejected { background: rgba(255, 23, 68, 0.15); color: #ff1744; border: 1px solid #ff1744; text-shadow: 0 0 5px #ff1744; }
        
        .req-meta {
            text-align: right;
        }
        
        .req-type {
            font-family: 'Orbitron', sans-serif;
            font-weight: bold;
            font-size: 0.9em;
            color: #ccc;
            text-transform: uppercase;
        }
        
        .req-date {
            font-size: 0.75em;
            color: #666;
            font-family: monospace;
        }
        
        .req-body {
            font-size: 1em;
            color: #b0bec5;
            background: rgba(0, 0, 0, 0.3);
            padding: 12px;
            border-radius: 6px;
            border-left: 3px solid #333;
            font-family: sans-serif;
        }
        
        .req-body strong { color: #fff; }
    </style>
""", unsafe_allow_html=True)

# --- HELPERS ---
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
            "Universidad": {"select": {"name": str(universidad)}},
            "Año": {"select": {"name": str(año)}}
        }
    }
    try: requests.post(url, headers=headers, json=payload)
    except: pass

@st.cache_data(ttl=60)
def get_players():
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    has_more = True; next_cursor = None; players = []
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
                    players.append({
                        "id": p["id"], 
                        "Aspirante": name, 
                        "Escuadrón": props.get("Nombre Escuadrón", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Sin Escuadrón"), 
                        "Universidad": props.get("Universidad", {}).get("select", {}).get("name", "Sin Asignar"),
                        "Generación": props.get("Año", {}).get("select", {}).get("name", "Sin Año"),
                        "MP": props.get("MP", {}).get("number", 0), 
                        "AP": props.get("AP", {}).get("number", 0), 
                        "VP": props.get("VP", {}).get("number", 0),
                        "Insignias": [x["name"] for x in props.get("Insignias", {}).get("multi_select", [])]
                    })
                except: pass
            has_more = data["has_more"]; next_cursor = data["next_cursor"]
        else: has_more = False
    return pd.DataFrame(players)

def update_stat_batch(player_id, updates_dict):
    url = f"https://api.notion.com/v1/pages/{player_id}"
    props = {k: {"number": v} for k, v in updates_dict.items()}
    requests.patch(url, headers=headers, json={"properties": props})

def update_badges_batch(player_id, new_badges_list):
    url = f"https://api.notion.com/v1/pages/{player_id}"
    requests.patch(url, headers=headers, json={"properties": {"Insignias": {"multi_select": [{"name": b} for b in new_badges_list]}}})

def update_stat(player_id, stat_name, new_value):
    url = f"https://api.notion.com/v1/pages/{player_id}"
    requests.patch(url, headers=headers, json={"properties": {stat_name: {"number": int(new_value)}}})

def finalize_request(page_id, status_label, observation_text=""):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    chile_tz = pytz.timezone('America/Santiago')
    now_iso = datetime.now(chile_tz).isoformat()
    data = {
        "properties": {
            "Procesado": {"checkbox": True},
            "Status": {"select": {"name": status_label}},
            "Fecha respuesta": {"date": {"start": now_iso}},
            # FIX: Nombre correcto de columna
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
    st.title("🎛️ PANEL DE CONTROL")
    uni_opts = ["Todas"] + (list(df_players["Universidad"].unique()) if not df_players.empty else [])
    gen_opts = ["Todas"] + (list(df_players["Generación"].unique()) if not df_players.empty else [])
    sel_uni = st.selectbox("📍 Universidad:", uni_opts)
    sel_gen = st.selectbox("📅 Generación:", gen_opts)
    
    df_filtered = df_players.copy()
    if not df_players.empty:
        if sel_uni != "Todas": df_filtered = df_filtered[df_filtered["Universidad"] == sel_uni]
        if sel_gen != "Todas": df_filtered = df_filtered[df_filtered["Generación"] == sel_gen]
    
    st.divider(); st.metric("Aspirantes Activos", len(df_filtered))
    if st.button("🧹 Limpiar Caché"): st.cache_data.clear(); st.rerun()
    if st.button("Cerrar Sesión"): st.session_state.admin_logged_in = False; st.rerun()

tab_req, tab_ops, tab_list = st.tabs(["📡 SOLICITUDES", "⚡ OPERACIONES", "👥 NÓMINA"])

# --- TAB 1: SOLICITUDES (VISUAL ÉPICA) ---
with tab_req:
    c_title, c_refresh = st.columns([4, 1])
    with c_title: st.markdown("### 📡 TRANSMISIONES")
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
                
                # Fecha robusta
                raw_date = item["created_time"]
                try:
                    utc_dt = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                    chile_tz = pytz.timezone('America/Santiago')
                    fecha_str = utc_dt.astimezone(chile_tz).strftime("%d/%m %H:%M")
                except: fecha_str = "Fecha desc."
                
                status_actual = props.get("Status", {}).get("select", {}).get("name", "Pendiente")
                solicitudes.append({"id": item["id"], "remitente": remitente, "mensaje": mensaje, "fecha": fecha_str, "status": status_actual})
    except: pass
    
    if not solicitudes:
        st.info(f"📭 Bandeja vacía ({filtro_estado})")
    else:
        for r in solicitudes:
            is_skill = "Costo:" in r['mensaje']
            msg_clean = re.sub(r'\|\s*0\s*MP', '', r['mensaje']) if is_skill else r['mensaje']
            
            # LOGICA DE ESTILO
            status_class = "badge-pending"
            status_label = r['status'].upper()
            border_color = "#ffea00" # Amarillo por defecto
            
            if status_label == "APROBADO": 
                status_class = "badge-approved"
                border_color = "#00e676"
            elif status_label == "RECHAZADO": 
                status_class = "badge-rejected"
                border_color = "#ff1744"
                
            type_text = "⚡ PODER" if is_skill else "💬 MENSAJE"
            type_color = "#FFD700" if is_skill else "#00e5ff" # Oro para poder, Azul para mensaje
            
            # Si es poder, sobreescribimos el borde
            if is_skill: border_color = "#FFD700"

            with st.container():
                st.markdown(f"""
                <div class="req-card-epic" style="border-left: 4px solid {border_color};">
                    <div class="req-header">
                        <div class="req-player-name">
                            {r['remitente']}
                            <span class="req-badge {status_class}">{status_label}</span>
                        </div>
                        <div class="req-meta">
                            <div class="req-type" style="color: {type_color};">{type_text}</div>
                            <div class="req-date">{r['fecha']}</div>
                        </div>
                    </div>
                    <div class="req-body">
                        {msg_clean}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                if filtro_estado == "Pendiente":
                    c_obs, c_acts = st.columns([3, 2])
                    with c_obs: 
                        obs_text = st.text_input("Observación:", key=f"obs_{r['id']}", placeholder="Opcional...")
                    with c_acts:
                        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
                        c_ok, c_no = st.columns(2)
                        with c_ok:
                            if st.button("✅ APROBAR", key=f"ok_{r['id']}", use_container_width=True):
                                if is_skill:
                                    with st.spinner("Cobrando..."):
                                        exito, msg = aprobar_solicitud_habilidad(r['id'], r['remitente'], r['mensaje'])
                                        if exito: st.success(msg); time.sleep(1.5); st.rerun()
                                        else: st.error(msg)
                                else:
                                    finalize_request(r['id'], "Respondido", obs_text or "Leído")
                                    st.success("Respondido"); time.sleep(1); st.rerun()
                        with c_no:
                            if st.button("❌ RECHAZAR", key=f"no_{r['id']}", use_container_width=True):
                                finalize_request(r['id'], "Rechazado", obs_text or "Rechazado")
                                st.warning("Rechazado"); time.sleep(1); st.rerun()

# --- TAB 2 Y 3: SIN CAMBIOS ---
with tab_ops:
    if df_filtered.empty: st.warning("Sin datos visibles.")
    else:
        st.markdown("### ⚡ GESTIÓN INDIVIDUAL")
        selected_aspirante_name = st.selectbox("Aspirante:", df_filtered["Aspirante"].tolist())
        p_data = df_filtered[df_filtered["Aspirante"] == selected_aspirante_name].iloc[0]
        c_mp, c_ap, c_vp = st.columns(3)
        with c_mp:
            st.metric("MasterPoints", p_data['MP'])
            mod_mp = st.number_input("MP", value=10, key="n_mp")
            if st.button("➕ MP", key="a_mp"): 
                update_stat(p_data["id"], "MP", p_data['MP']+mod_mp)
                registrar_log_admin(p_data['Aspirante'], "Ajuste MP", f"+{mod_mp} MP", p_data['Universidad'], p_data['Generación'])
                st.toast("Hecho"); time.sleep(0.5); st.rerun()
        with c_ap:
            st.metric("AngioPoints", p_data['AP'])
            mod_ap = st.number_input("AP", value=5, key="n_ap")
            if st.button("➕ AP", key="a_ap"): 
                update_stat(p_data["id"], "AP", p_data['AP']+mod_ap)
                registrar_log_admin(p_data['Aspirante'], "Ajuste AP", f"+{mod_ap} AP", p_data['Universidad'], p_data['Generación'])
                st.toast("Hecho"); time.sleep(0.5); st.rerun()
        # ... (Resto de operaciones igual) ...
        # (He recortado el final del código de operaciones para que entre en la respuesta, 
        #  si quieres el archivo COMPLETO con operaciones avísame, pero el foco era UI y Fix Solicitudes)
        
        # ... INCLUIR AQUÍ EL BLOQUE DE BOMBARDEO MASIVO SI LO USAS ...
        st.markdown("---")
        st.markdown("<div class='mass-ops-box'>### 💣 BOMBARDEO MASIVO</div>", unsafe_allow_html=True)
        target_squad = st.selectbox("Escuadrón:", df_filtered["Escuadrón"].unique(), key="sq_mass")
        c1, c2, c3 = st.columns(3)
        m_mp = c1.number_input("MP", value=0); m_ap = c2.number_input("AP", value=0); m_vp = c3.number_input("VP", value=0)
        reason = st.text_input("Motivo:")
        if st.button("🚀 EJECUTAR", use_container_width=True):
            if not reason: st.error("Falta motivo.")
            else:
                targets = df_filtered[df_filtered["Escuadrón"] == target_squad]
                bar = st.progress(0); n = len(targets)
                for i, (_, s) in enumerate(targets.iterrows()):
                    ups = {}
                    if m_mp: ups["MP"] = max(0, s["MP"]+m_mp)
                    if m_ap: ups["AP"] = max(0, s["AP"]+m_ap)
                    if m_vp: ups["VP"] = max(0, min(100, s["VP"]+m_vp))
                    if ups:
                        update_stat_batch(s["id"], ups)
                        registrar_log_admin(s["Aspirante"], "Masivo", f"{reason}", s["Universidad"], s["Generación"])
                    bar.progress((i+1)/n)
                st.success("Listo"); time.sleep(1); st.rerun()

with tab_list:
    st.markdown("### 👥 NÓMINA")
    st.dataframe(df_filtered, use_container_width=True, hide_index=True)
