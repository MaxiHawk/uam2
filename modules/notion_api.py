import streamlit as st
import requests
import time
from datetime import datetime
import pytz
import random
import json

# Importamos la configuración centralizada
from config import (
    HEADERS, 
    DB_CONFIG_ID, DB_LOGS_ID, DB_JUGADORES_ID, DB_MISIONES_ID, 
    DB_SOLICITUDES_ID, DB_CODIGOS_ID, DB_TRIVIA_ID, DB_HABILIDADES_ID,
    DB_ANUNCIOS_ID
)

# --- ALIAS DE COMPATIBILIDAD ---
headers = HEADERS 

# --- 🛠️ UTILIDADES INTERNAS ---
def get_chile_time_iso():
    return datetime.now(pytz.timezone('America/Santiago')).isoformat()

def get_player_metadata():
    """Extrae Universidad y Año de la sesión actual."""
    try:
        if "jugador" in st.session_state and st.session_state.jugador:
            props = st.session_state.jugador.get("properties", {})
            uni_obj = props.get("Universidad", {}).get("select")
            uni = uni_obj["name"] if uni_obj else None
            ano_obj = props.get("Año", {}).get("select")
            ano = ano_obj["name"] if ano_obj else None
            return uni, ano
    except: pass
    return None, None

# --- 🛡️ SISTEMA (CONFIG & LOGS) ---
@st.cache_data(ttl=60, show_spinner=False)
def verificar_modo_mantenimiento():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "MODO_MANTENIMIENTO"}}}
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results: return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO"):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    uni, ano = get_player_metadata()
    properties = {
        "Evento": {"title": [{"text": {"content": str(accion)}}]}, 
        "Jugador": {"rich_text": [{"text": {"content": str(usuario)}}]},
        "Detalle": {"rich_text": [{"text": {"content": str(detalles)}}]},
        "Tipo": {"select": {"name": tipo}},
        "Fecha": {"date": {"start": get_chile_time_iso()}}
    }
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}

    try: requests.post(url, headers=headers, json={"parent": {"database_id": DB_LOGS_ID}, "properties": properties}, timeout=2)
    except: pass

# --- 👤 JUGADORES ---
@st.cache_data(ttl=300, show_spinner="Sincronizando perfil...")
def cargar_datos_jugador(email):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Correo electrónico", "email": {"equals": email}}}
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results: return results[0]
        return None
    except: return None

# --- 📢 ANUNCIOS ---
@st.cache_data(ttl=600)
def cargar_anuncios():
    if not DB_ANUNCIOS_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_ANUNCIOS_ID}/query"
    payload = {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "sorts": [{"timestamp": "created_time", "direction": "descending"}]}
    try:
        res = requests.post(url, headers=headers, json=payload)
        anuncios = []
        if res.status_code == 200:
            for r in res.json().get("results", []):
                props = r["properties"]
                try:
                    titulo = props.get("Titulo", {}).get("title", [{}])[0].get("text", {}).get("content", "Anuncio")
                    contenido = props.get("Contenido", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                    anuncios.append({"titulo": titulo, "contenido": contenido})
                except: pass
        return anuncios
    except: return []

# --- 🚀 MISIONES ---
@st.cache_data(ttl=600)
def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    payload = {"filter": {"property": "Estado", "status": {"equals": "Activa"}}, "sorts": [{"property": "Fecha Lanzamiento", "direction": "ascending"}]}
    try:
        response = requests.post(url, headers=headers, json=payload)
        misiones = []
        if response.status_code == 200:
            for p in response.json().get("results", []):
                props = p["properties"]
                def get_text(prop_name): return props.get(prop_name, {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                def get_title(prop_name): return props.get(prop_name, {}).get("title", [{}])[0].get("text", {}).get("content", "Sin Título")
                misiones.append({
                    "id": p["id"], "nombre": get_title("Misión"), "descripcion": get_text("Descripción"),
                    "tipo": props.get("Tipo", {}).get("select", {}).get("name", "Misión"),
                    "f_cierre": props.get("Fecha Cierre", {}).get("date", {}).get("start"),
                    "inscritos": get_text("Inscritos"), "password": get_text("Password"), "link": props.get("Link", {}).get("url", "#")
                })
        return misiones
    except: return []

def inscribir_jugador_mision(page_id, inscritos_actuales, nombre_jugador):
    nuevos_inscritos = f"{inscritos_actuales}, {nombre_jugador}" if inscritos_actuales else nombre_jugador
    url = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        if requests.patch(url, headers=headers, json={"properties": {"Inscritos": {"rich_text": [{"text": {"content": nuevos_inscritos}}]}}}).status_code == 200:
            registrar_evento_sistema(nombre_jugador, "Inscripción Misión", f"ID: {page_id}", "Misión")
            st.cache_data.clear()
            return True
        return False
    except: return False

# --- 📩 SOLICITUDES ---
def enviar_solicitud(tipo, mensaje, detalles, usuario):
    if not DB_SOLICITUDES_ID: return False
    url = "https://api.notion.com/v1/pages"
    uni, ano = get_player_metadata()
    properties = {
        "Usuario": {"title": [{"text": {"content": str(usuario)}}]}, "Tipo": {"select": {"name": tipo}},
        "Mensaje": {"rich_text": [{"text": {"content": f"{mensaje}\n\nDetalles: {detalles}"}}]}, 
        "Status": {"select": {"name": "Pendiente"}}, "Fecha de creación": {"date": {"start": get_chile_time_iso()}} 
    }
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}
    try: return requests.post(url, headers=headers, json={"parent": {"database_id": DB_SOLICITUDES_ID}, "properties": properties}).status_code == 200
    except: return False

# --- 🛍️ MERCADO DE HABILIDADES ---
def procesar_compra_habilidad(skill_name, cost_ap, cost_mp, skill_id_notion):
    current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
    current_mp = st.session_state.jugador.get("MP", {}).get("number", 0)
    if current_ap < cost_ap: return False, "Saldo AP insuficiente."
    
    exito = enviar_solicitud("Compra Habilidad", f"Solicitud: {skill_name}", f"Costo: {cost_ap} AP", st.session_state.nombre)
    if exito:
        registrar_evento_sistema(st.session_state.nombre, "Solicitud Habilidad", f"{skill_name} (-{cost_ap} AP)", "Mercado")
        return True, "Solicitud enviada al Comando."
    return False, "Error al enviar solicitud."

# --- NUEVO: CARGAR HABILIDADES REALES ---
@st.cache_data(ttl=3600)
def cargar_habilidades():
    if not DB_HABILIDADES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    # Ordenamos por Nivel (Ascendente) y luego por Costo
    payload = {
        "sorts": [
            {"property": "Nivel Requerido", "direction": "ascending"},
            {"property": "Costo AP", "direction": "ascending"}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        skills = []
        if res.status_code == 200:
            for r in res.json().get("results", []):
                props = r["properties"]
                # Extracción segura basada en tu diagnóstico
                try:
                    nombre = props.get("Habilidad", {}).get("title", [{}])[0].get("text", {}).get("content", "Skill")
                    desc = props.get("Descripcion", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
                    costo = props.get("Costo AP", {}).get("number", 0)
                    nivel_req = props.get("Nivel Requerido", {}).get("number", 1)
                    
                    skills.append({
                        "id": r["id"],
                        "nombre": nombre,
                        "desc": desc,
                        "costo": costo,
                        "nivel_req": nivel_req
                    })
                except: pass
        return skills
    except: return []

# --- 📦 SUMINISTROS ---
def cargar_estado_suministros():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "DROP_SUMINISTROS"}}}
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results: return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def procesar_suministro(rarity_name, rewards):
    try:
        player = st.session_state.jugador
        new_ap = player.get("AP", {}).get("number", 0) + rewards["AP"]
        new_mp = player.get("MP", {}).get("number", 0) + rewards["MP"]
        new_vp = min(100, player.get("VP", {}).get("number", 0) + rewards["VP"])
        url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        payload = {"properties": {"AP": {"number": new_ap}, "MP": {"number": new_mp}, "VP": {"number": new_vp}, "Ultimo Suministro": {"date": {"start": get_chile_time_iso()}}}}
        if requests.patch(url, headers=headers, json=payload).status_code == 200:
            registrar_evento_sistema(st.session_state.nombre, "Suministro Reclamado", f"AP:+{rewards['AP']}|MP:+{rewards['MP']}", rarity_name)
            return True
        return False
    except: return False

# --- 🔐 CÓDIGOS Y TRIVIA (Sin Cambios) ---
def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline."
    url = f"https://api.notion.com/v1/databases/{DB_CODIGOS_ID}/query"
    payload = {"filter": {"and": [{"property": "Código", "title": {"equals": codigo_input}}, {"property": "Activo", "checkbox": {"equals": True}}]}}
    try:
        res = requests.post(url, headers=headers, json=payload)
        results = res.json().get("results", [])
        if not results: return False, "❌ Código inválido."
        props = results[0]["properties"]
        redeemed = props.get("Redimido Por", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "")
        if st.session_state.nombre in redeemed: return False, "⚠️ Ya canjeaste este código."
        
        rew_ap = props.get("Valor AP", {}).get("number", 0)
        url_p = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        player = st.session_state.jugador
        new_ap = player.get("AP", {}).get("number", 0) + rew_ap
        
        if requests.patch(url_p, headers=headers, json={"properties": {"AP": {"number": new_ap}}}).status_code == 200:
            new_list = f"{redeemed}, {st.session_state.nombre}" if redeemed else st.session_state.nombre
            requests.patch(f"https://api.notion.com/v1/pages/{results[0]['id']}", headers=headers, json={"properties": {"Redimido Por": {"rich_text": [{"text": {"content": new_list}}]}}})
            registrar_evento_sistema(st.session_state.nombre, "Canje Código", f"Code: {codigo_input} (+{rew_ap} AP)", "Código")
            return True, f"¡Canjeado! +{rew_ap} AP"
        return False, "Error al actualizar."
    except Exception as e: return False, str(e)

def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    try:
        res = requests.post(url, headers=headers, json={"filter": {"property": "Activa", "checkbox": {"equals": True}}, "page_size": 20})
        results = res.json().get("results", [])
        if not results: return None
        q = random.choice(results)
        p = q["properties"]
        return {
            "ref_id": q["id"], "pregunta": p["Pregunta"]["title"][0]["text"]["content"],
            "opcion_a": p["Opción A"]["rich_text"][0]["text"]["content"], "opcion_b": p["Opción B"]["rich_text"][0]["text"]["content"], "opcion_c": p["Opción C"]["rich_text"][0]["text"]["content"],
            "correcta": p["Correcta"]["select"]["name"], "recompensa": p["Recompensa AP"]["number"],
            "exp_correcta": p.get("Explicación Correcta", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Bien"),
            "exp_incorrecta": p.get("Explicación Incorrecta", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Mal")
        }
    except: return None

def procesar_recalibracion(reward_ap, is_correct, question_id):
    if is_correct and reward_ap > 0:
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
        requests.patch(f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}", headers=headers, json={"properties": {"AP": {"number": current_ap + reward_ap}}})
    requests.patch(f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}", headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": get_chile_time_iso()}}}})
    registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"{'CORRECTO' if is_correct else 'FALLO'} (+{reward_ap if is_correct else 0})", "Trivia")
