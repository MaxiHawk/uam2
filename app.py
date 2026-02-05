import streamlit as st
import requests
import time
import random
import json
import re
from datetime import datetime
import pytz

# Importamos Configuración
from config import (
    HEADERS, API_TIMEOUT,
    DB_CONFIG_ID, DB_LOGS_ID, DB_JUGADORES_ID, DB_MISIONES_ID, 
    DB_SOLICITUDES_ID, DB_CODIGOS_ID, DB_TRIVIA_ID, DB_HABILIDADES_ID,
    DB_ANUNCIOS_ID, DB_MERCADO_ID
)

# Importamos las Herramientas Maestras
from modules.utils import (
    get_notion_text, get_notion_number, get_notion_select, 
    get_notion_multi_select, get_notion_date, get_notion_url, 
    get_notion_checkbox, get_notion_file_url, validar_codigo_seguro, get_notion_unique_id
)

# Alias
headers = HEADERS 

# --- 🛠️ UTILIDADES INTERNAS ---
def get_player_metadata():
    """Recupera Universidad y Año priorizando sesión."""
    try:
        uni = st.session_state.get("uni_actual")
        ano = st.session_state.get("ano_actual")
        if uni and ano: return uni, ano

        # Fallback manual
        if "jugador" in st.session_state and st.session_state.jugador:
            props = st.session_state.jugador.get("properties", {})
            if not uni: uni = get_notion_select(props, "Universidad")
            if not ano: ano = get_notion_select(props, "Año")
        return uni, ano
    except: return "Desconocido", "Desconocido"

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Praxis | Universo AngioMasters", page_icon="🧬", layout="centered")

# Estilos CSS Cyberpunk
st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
        .stApp { background-color: #050810; color: #e0f7fa; font-family: 'Rajdhani', sans-serif; }
        h1, h2, h3 { font-family: 'Orbitron', sans-serif; color: #00e5ff; text-shadow: 0 0 10px rgba(0,229,255,0.3); }
        
        /* BOTONES */
        .stButton>button {
            background: linear-gradient(45deg, #0d47a1, #00e5ff); border: none; color: white;
            font-family: 'Orbitron', sans-serif; letter-spacing: 1px; transition: all 0.3s;
        }
        .stButton>button:hover { transform: scale(1.05); box-shadow: 0 0 15px #00e5ff; }
        
        /* TABS */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { background-color: rgba(0,229,255,0.1); border-radius: 5px 5px 0 0; color: #fff; }
        .stTabs [aria-selected="true"] { background-color: #00e5ff !important; color: #000 !important; font-weight: bold; }

        /* KPI CARDS */
        .kpi-card {
            background: rgba(13, 71, 161, 0.2); border: 1px solid #00e5ff; border-radius: 10px;
            padding: 10px; text-align: center; margin-bottom: 10px;
        }
        .kpi-val { font-family: 'Orbitron'; font-size: 1.5em; color: #fff; }
        .kpi-label { font-size: 0.8em; color: #00e5ff; text-transform: uppercase; }
        
        /* MESSAGE BUBBLES */
        .msg-container {
            background: rgba(255,255,255,0.05); border-left: 3px solid #00e5ff;
            padding: 10px; margin-bottom: 10px; border-radius: 0 10px 10px 0;
        }
        .msg-meta { font-size: 0.7em; color: #888; margin-bottom: 5px; font-family: 'Orbitron'; }
        
        /* MARKET CARDS */
        .market-card {
            background: linear-gradient(135deg, #1a237e 0%, #000 100%);
            border: 1px solid #ffd700; border-radius: 10px; padding: 15px; margin-bottom: 15px;
            position: relative; overflow: hidden;
        }
    </style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE SESIÓN ---
if "jugador_id" not in st.session_state: st.session_state.jugador_id = None
if "jugador" not in st.session_state: st.session_state.jugador = None

def login():
    st.markdown("<div style='text-align:center; margin-top:50px;'><img src='https://i.imgur.com/P9Jg9Wz.png' width='150'></div>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center;'>ACCESO AL SISTEMA</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        user = st.text_input("Identificación (Usuario):").strip()
        pwd = st.text_input("Código de Acceso (Contraseña):", type="password").strip()
        submitted = st.form_submit_button("INICIAR ENLACE")
        
        if submitted:
            if not user or not pwd:
                st.error("Credenciales incompletas.")
                return

            payload = {"filter": {"property": "Nick", "rich_text": {"equals": user}}}
            try:
                res = requests.post(f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query", headers=headers, json=payload)
                data = res.json()
                
                if data["results"]:
                    player = data["results"][0]
                    stored_pass = get_notion_text(player["properties"], "Pass")
                    
                    if stored_pass == pwd:
                        st.session_state.jugador_id = player["id"]
                        st.session_state.jugador = player
                        # Guardar metadatos en sesión
                        st.session_state.uni_actual = get_notion_select(player["properties"], "Universidad")
                        st.session_state.ano_actual = get_notion_select(player["properties"], "Año")
                        st.success("✅ Acceso Autorizado")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("⛔ Contraseña incorrecta.")
                else: st.error("🚫 Usuario no encontrado.")
            except Exception as e: st.error(f"Error de conexión: {e}")

def logout():
    st.session_state.jugador_id = None
    st.session_state.jugador = None
    st.session_state.uni_actual = None
    st.session_state.ano_actual = None
    st.rerun()

# --- VISTA PRINCIPAL ---
if not st.session_state.jugador_id:
    login()
else:
    # RECARGAR DATOS FRESCOS
    try:
        r_fresh = requests.get(f"https://api.notion.com/v1/pages/{st.session_state.jugador_id}", headers=headers)
        if r_fresh.status_code == 200:
            st.session_state.jugador = r_fresh.json()
    except: pass

    p = st.session_state.jugador["properties"]
    nombre = get_notion_text(p, "Jugador") # Título principal
    if not nombre: nombre = "Agente"
    
    rango = get_notion_select(p, "Rango")
    squad = get_notion_text(p, "Nombre Escuadrón") or "Sin Escuadrón"
    
    mp = get_notion_number(p, "MP")
    ap = get_notion_number(p, "AP")
    vp = get_notion_number(p, "VP")
    
    # Metadatos para filtrar
    uni_player, ano_player = get_player_metadata()

    # --- SIDEBAR (PERFIL Y CONTROLES) ---
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center; margin-bottom:20px;">
            <div style="font-family:'Orbitron'; font-size:1.2em; color:#fff; font-weight:bold;">{nombre}</div>
            <div style="font-size:0.8em; color:#00e5ff;">{rango}</div>
            <div style="font-size:0.8em; color:#aaa;">{squad}</div>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='kpi-card'><div class='kpi-val' style='color:#ffd700;'>{mp}</div><div class='kpi-label'>MP</div></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='kpi-card'><div class='kpi-val' style='color:#00e5ff;'>{ap}</div><div class='kpi-label'>AP</div></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='kpi-card'><div class='kpi-val' style='color:#ff1744;'>{vp}%</div><div class='kpi-label'>VP</div></div>", unsafe_allow_html=True)
        
        st.divider()
        
        # BOTONES DE CONTROL (MOVIDOS AQUÍ PARA MEJOR UX)
        if st.button("🔄 ACTUALIZAR", use_container_width=True): st.rerun()
        if st.button("🚪 CERRAR SESIÓN", use_container_width=True): logout()

    # --- TABS PRINCIPALES ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📢 COMUNICACIONES", "📜 MISIONES", "⚡ PODERES", "🛒 MERCADO", "🏆 RANGOS"])

    # 1. COMUNICACIONES (MEJORADO V17)
    with tab1:
        st.markdown("### 📡 TRANSIMISIONES")
        
        # Filtro de mensajes: Globales (Sin Uni) O Específicos de mi Uni/Año
        # Notion Filter: (Uni Is Empty OR Uni = MiUni) AND (Año Is Empty OR Año = MiAño)
        # Nota: La API de Notion tiene limites en filtros compuestos complejos "OR" anidados.
        # Estrategia: Traemos los últimos 20 y filtramos en Python para asegurar precisión.
        
        payload_msgs = {
            "sorts": [{"property": "Fecha", "direction": "descending"}],
            "page_size": 30
        }
        
        mensajes_filtrados = []
        try:
            res = requests.post(f"https://api.notion.com/v1/databases/{DB_ANUNCIOS_ID}/query", headers=headers, json=payload_msgs)
            if res.status_code == 200:
                raw_msgs = res.json()["results"]
                for m in raw_msgs:
                    props = m["properties"]
                    # Filtros de destino
                    target_uni = get_notion_select(props, "Universidad Destino")
                    target_ano = get_notion_select(props, "Generación Destino")
                    
                    # Lógica de coincidencia
                    match_uni = (target_uni is None) or (target_uni == "Todas") or (target_uni == uni_player)
                    match_ano = (target_ano is None) or (target_ano == "Todas") or (target_ano == str(ano_player))
                    
                    if match_uni and match_ano:
                        titulo = get_notion_text(props, "Título")
                        cuerpo = get_notion_text(props, "Mensaje")
                        fecha = get_notion_date(props, "Fecha")
                        mensajes_filtrados.append({"t": titulo, "c": cuerpo, "f": fecha})
        except: pass

        if not mensajes_filtrados:
            st.info("📭 Sin transmisiones recientes.")
        else:
            # --- MEJORA UX: CONTENEDOR CON SCROLL ---
            with st.container(height=500, border=True):
                for msg in mensajes_filtrados:
                    st.markdown(f"""
                    <div class="msg-container">
                        <div class="msg-meta">📅 {msg['f']} | 📨 SISTEMA CENTRAL</div>
                        <div style="font-weight:bold; color:#fff; margin-bottom:5px;">{msg['t']}</div>
                        <div style="color:#b0bec5; font-size:0.9em;">{msg['c']}</div>
                    </div>
                    """, unsafe_allow_html=True)

    # 2. MISIONES
    with tab2:
        st.markdown("### 📜 MISIONES ACTIVAS")
        # Traer misiones filtradas
        payload_m = {
            "filter": {"and": [
                {"property": "Estado", "status": {"equals": "Activa"}}
            ]}
        }
        # Nota: Idealmente filtrar también por Uni/Año si las misiones son específicas
        
        try:
            res_m = requests.post(f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query", headers=headers, json=payload_m)
            misiones = res_m.json().get("results", [])
            
            misiones_validas = []
            for m in misiones:
                p_m = m["properties"]
                # Filtro local de Uni/Año
                m_uni = get_notion_multi_select(p_m, "Universidad")
                m_ano = get_notion_multi_select(p_m, "Año")
                
                check_uni = (not m_uni) or ("Todas" in m_uni) or (uni_player in m_uni)
                check_ano = (not m_ano) or ("Todas" in m_ano) or (ano_player in m_ano)
                
                if check_uni and check_ano:
                    misiones_validas.append(m)
            
            if not misiones_validas:
                st.info("✅ No hay misiones pendientes.")
            else:
                for mis in misiones_validas:
                    pm = mis["properties"]
                    nom = get_notion_text(pm, "Misión")
                    desc = get_notion_text(pm, "Descripción")
                    rew_mp = get_notion_number(pm, "Recompensa MP")
                    rew_ap = get_notion_number(pm, "Recompensa AP")
                    
                    with st.expander(f"📜 {nom} (+{rew_mp} MP | +{rew_ap} AP)"):
                        st.write(desc)
                        # Lógica de entrega de código...
                        code_input = st.text_input(f"Código de confirmación:", key=f"c_{mis['id']}")
                        if st.button("ENVIAR REPORTE", key=f"b_{mis['id']}"):
                            if validar_codigo_seguro(code_input, mis['id']):
                                # Procesar recompensa (simplificado, idealmente vía solicitud)
                                # Aquí podríamos crear una SOLICITUD de "Completar Misión" para que el Admin apruebe
                                # O validación directa si el código es único.
                                # Por seguridad: Creamos Solicitud de Validación.
                                now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
                                p_req = {
                                    "parent": {"database_id": DB_SOLICITUDES_ID},
                                    "properties": {
                                        "Remitente": {"title": [{"text": {"content": nombre}}]},
                                        "Tipo": {"select": {"name": "Misión"}},
                                        "Mensaje": {"rich_text": [{"text": {"content": f"Misión completada: {nom}. Código: {code_input}"}}]},
                                        "Universidad": {"select": {"name": uni_player}},
                                        "Año": {"select": {"name": ano_player}},
                                        "Status": {"select": {"name": "Pendiente"}}
                                    }
                                }
                                requests.post("https://api.notion.com/v1/pages", headers=headers, json=p_req)
                                st.success("Reporte enviado al comando. Esperando confirmación.")
                            else:
                                st.error("Código inválido.")

        except: st.error("Error cargando misiones.")

    # 3. PODERES (HABILIDADES)
    with tab3:
        st.markdown("### ⚡ ARSENAL DE HABILIDADES")
        st.caption(f"Saldo Actual: {ap} AP")
        
        try:
            res_h = requests.post(f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query", headers=headers, json={})
            habs = res_h.json().get("results", [])
            
            if not habs: st.info("Arsenal vacío.")
            else:
                for h in habs:
                    ph = h["properties"]
                    h_nom = get_notion_text(ph, "Habilidad")
                    h_desc = get_notion_text(ph, "Efecto")
                    h_costo = get_notion_number(ph, "Costo AP")
                    h_req = get_notion_select(ph, "Requisito Nivel") # Si aplica
                    
                    # Card
                    st.markdown(f"""
                    <div style="border:1px solid #d500f9; padding:10px; border-radius:10px; margin-bottom:10px; background:rgba(213,0,249,0.05);">
                        <div style="font-weight:bold; color:#d500f9;">{h_nom}</div>
                        <div style="font-size:0.9em; color:#fff;">{h_desc}</div>
                        <div style="text-align:right; font-weight:bold; color:#ffd700;">-{h_costo} AP</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.button(f"ACTIVAR {h_nom}", key=f"hab_{h['id']}"):
                        if ap >= h_costo:
                            # Crear solicitud
                            p_req = {
                                "parent": {"database_id": DB_SOLICITUDES_ID},
                                "properties": {
                                    "Remitente": {"title": [{"text": {"content": nombre}}]},
                                    "Tipo": {"select": {"name": "Habilidad"}},
                                    # IMPORTANTE: Mandar Costo en el mensaje para que el Admin descuente
                                    "Mensaje": {"rich_text": [{"text": {"content": f"Activación: {h_nom}. Costo: {h_costo}"}}]},
                                    "Universidad": {"select": {"name": uni_player}},
                                    "Año": {"select": {"name": ano_player}},
                                    "Status": {"select": {"name": "Pendiente"}}
                                }
                            }
                            requests.post("https://api.notion.com/v1/pages", headers=headers, json=p_req)
                            st.success("⚡ Solicitud de activación enviada. El sistema descontará los AP al aprobar.")
                        else:
                            st.error("AP Insuficientes.")
        except: pass

    # 4. MERCADO
    with tab4:
        st.markdown("### 🛒 MERCADO NEGRO")
        st.caption(f"Saldo disponible: {ap} AP")
        
        try:
            res_mk = requests.post(f"https://api.notion.com/v1/databases/{DB_MERCADO_ID}/query", headers=headers, json={})
            items = res_mk.json().get("results", [])
            
            if not items: st.info("Mercado cerrado.")
            else:
                cols = st.columns(2)
                for idx, it in enumerate(items):
                    pi = it["properties"]
                    i_nom = get_notion_text(pi, "Item")
                    i_desc = get_notion_text(pi, "Descripción")
                    i_cost = get_notion_number(pi, "Precio")
                    i_stock = get_notion_number(pi, "Stock")
                    
                    with cols[idx % 2]:
                        st.markdown(f"""
                        <div class="market-card">
                            <div style="color:#ffd700; font-weight:bold;">{i_nom}</div>
                            <div style="font-size:0.8em; color:#aaa;">{i_desc}</div>
                            <div style="margin-top:10px; display:flex; justify-content:space-between;">
                                <span style="color:#00e5ff;">{i_cost} AP</span>
                                <span style="color:#fff;">Stock: {i_stock}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if i_stock > 0:
                            if st.button(f"COMPRAR", key=f"buy_{it['id']}"):
                                if ap >= i_cost:
                                    p_req = {
                                        "parent": {"database_id": DB_SOLICITUDES_ID},
                                        "properties": {
                                            "Remitente": {"title": [{"text": {"content": nombre}}]},
                                            "Tipo": {"select": {"name": "Compra"}},
                                            "Mensaje": {"rich_text": [{"text": {"content": f"Compra de Item: {i_nom}. Costo: {i_cost}"}}]},
                                            "Universidad": {"select": {"name": uni_player}},
                                            "Año": {"select": {"name": ano_player}},
                                            "Status": {"select": {"name": "Pendiente"}}
                                        }
                                    }
                                    requests.post("https://api.notion.com/v1/pages", headers=headers, json=p_req)
                                    st.success("📦 Pedido realizado. Esperando aprobación.")
                                else: st.error("Fondos insuficientes.")
                        else:
                            st.button("AGOTADO", key=f"sold_{it['id']}", disabled=True)
        except: pass

    # 5. RANGOS (Solo visualización simple por ahora)
    with tab5:
        st.markdown("### 🏆 TABLA DE POSICIONES")
        st.info("Próximamente: Clasificación global.")
