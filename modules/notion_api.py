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

# --- 🛡️ SISTEMA (CONFIG & LOGS) ---
@st.cache_data(ttl=60, show_spinner=False)
def verificar_modo_mantenimiento():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        # CORRECCIÓN: Tu columna se llama "Clave" (Title)
        payload = {
            "filter": {
                "property": "Clave", 
                "title": {"equals": "MODO_MANTENIMIENTO"}
            }
        }
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                # CORRECCIÓN: Tu checkbox se llama "Activo"
                return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO"):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    
    # CORRECCIÓN MASIVA SEGÚN TU ESTRUCTURA REAL:
    # - Evento (Title) -> Aquí va la acción (ej: "Login")
    # - Jugador (Rich Text) -> Aquí va el usuario
    # - Detalle (Rich Text) -> Detalles extra
    # - Tipo (Select) -> Info/Error/Warning
    # - Fecha (Date)
    
    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Evento": {"title": [{"text": {"content": str(accion)}}]}, 
            "Jugador": {"rich_text": [{"text": {"content": str(usuario)}}]},
            "Detalle": {"rich_text": [{"text": {"content": str(detalles)}}]},
            "Tipo": {"select": {"name": tipo}},
            "Fecha": {"date": {"start": get_chile_time_iso()}}
        }
    }
    try: requests.post(url, headers=headers, json=payload, timeout=2)
    except: pass

# --- 👤 JUGADORES ---
@st.cache_data(ttl=300, show_spinner="Sincronizando perfil...")
def cargar_datos_jugador(email):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {
        "filter": {
            "property": "Correo electrónico", # Coincide con tu DB
            "email": {"equals": email}
        }
    }
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
    payload = {
        "filter": {"property": "Activo", "checkbox": {"equals": True}},
        "sorts": [{"timestamp": "created_time", "direction": "descending"}]
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        anuncios = []
        if res.status_code == 200:
            for r in res.json().get("results", []):
                props = r["properties"]
                try:
                    titulo_list = props.get("Titulo", {}).get("title", [])
                    titulo = titulo_list[0]["text"]["content"] if titulo_list else "Anuncio"
                    cont_list = props.get("Contenido", {}).get("rich_text", [])
                    contenido = cont_list[0]["text"]["content"] if cont_list else ""
                    
                    uni_target = [u["name"] for u in props.get("Universidad", {}).get("multi_select", [])]
                    ano_target = [a["name"] for a in props.get("Año", {}).get("multi_select", [])]
                    
                    fecha = r["created_time"]
                    if "Fecha" in props and props["Fecha"]["date"]:
                        fecha = props["Fecha"]["date"]["start"]

                    anuncios.append({
                        "titulo": titulo, "contenido": contenido,
                        "universidad": uni_target, "año": ano_target, "fecha": fecha
                    })
                except: pass
        return anuncios
    except: return []

# --- 🚀 MISIONES ---
@st.cache_data(ttl=600)
def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    payload = {
        "filter": {"property": "Estado", "status": {"equals": "Activa"}},
        "sorts": [{"property": "Fecha Lanzamiento", "direction": "ascending"}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        misiones = []
        if response.status_code == 200:
            for p in response.json().get("results", []):
                props = p["properties"]
                # Helpers de extracción segura
                def get_text(prop_name):
                    l = props.get(prop_name, {}).get("rich_text", [])
                    return l[0]["text"]["content"] if l else ""
                
                def get_title(prop_name):
                    l = props.get(prop_name, {}).get("title", [])
                    return l[0]["text"]["content"] if l else "Sin Título"

                misiones.append({
                    "id": p["id"],
                    "nombre": get_title("Misión"),
                    "descripcion": get_text("Descripción"),
                    "tipo": props.get("Tipo", {}).get("select", {}).get("name", "Misión"),
                    "f_apertura": props.get("Fecha Apertura", {}).get("date", {}).get("start"),
                    "f_cierre": props.get("Fecha Cierre", {}).get("date", {}).get("start"),
                    "inscritos": get_text("Inscritos"),
                    "target_unis": [x["name"] for x in props.get("Universidad Objetivo", {}).get("multi_select", [])],
                    "password": get_text("Password"),
                    "link": props.get("Link", {}).get("url", "#")
                })
        return misiones
    except: return []

def inscribir_jugador_mision(page_id, inscritos_actuales, nombre_jugador):
    nuevos_inscritos = f"{inscritos_actuales}, {nombre_jugador}" if inscritos_actuales else nombre_jugador
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Inscritos": {"rich_text": [{"text": {"content": nuevos_inscritos}}]}}}
    try:
        if requests.patch(url, headers=headers, json=payload).status_code == 200:
            registrar_evento_sistema(nombre_jugador, "Inscripción Misión", f"ID: {page_id}")
            st.cache_data.clear()
            return True
        return False
    except: return False

# --- 📩 SOLICITUDES (CORREGIDO) ---
def enviar_solicitud(tipo, mensaje, detalles, usuario):
    if not DB_SOLICITUDES_ID: return False
    url = "https://api.notion.com/v1/pages"
    
    # CORRECCIÓN: Tu DB usa "Status" (no Estado) y "Usuario" (Title)
    payload = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Usuario": {"title": [{"text": {"content": str(usuario)}}]},
            "Tipo": {"select": {"name": tipo}},
            "Mensaje": {"rich_text": [{"text": {"content": f"{mensaje}\n\nDetalles: {detalles}"}}]}, # Combinamos porque no vi campo "Detalles" en tu reporte
            "Status": {"select": {"name": "Pendiente"}}, # <--- CORREGIDO: Status
            "Fecha de creación": {"date": {"start": get_chile_time_iso()}} # Usamos el campo que vi en tu reporte
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.status_code == 200
    except: return False

# --- 🛍️ MERCADO DE HABILIDADES (PARCHE DE EMERGENCIA) ---
def procesar_compra_habilidad(skill_name, cost_ap, cost_mp, skill_id_notion):
    """
    ⚠️ NOTA TÉCNICA: El diagnóstico mostró que la DB de JUGADORES NO TIENE
    una columna 'Relation' para guardar las habilidades compradas.
    
    SOLUCIÓN: Descontaremos el AP/MP y registraremos el LOG, pero NO intentaremos
    guardar la relación para evitar el error 400.
    """
    current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
    current_mp = st.session_state.jugador.get("MP", {}).get("number", 0)
    
    if current_ap < cost_ap or current_mp < cost_mp:
        return False, "Saldo insuficiente."

    new_ap = current_ap - cost_ap
    new_mp = current_mp - cost_mp

    # Actualizamos SOLO los saldos
    url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    payload = {
        "properties": {
            "AP": {"number": new_ap},
            "MP": {"number": new_mp}
        }
    }
    
    try:
        res = requests.patch(url, headers=headers, json=payload)
        if res.status_code == 200:
            registrar_evento_sistema(st.session_state.nombre, "Compra Habilidad", f"Skill: {skill_name} (Solo cobro)")
            return True, f"¡{skill_name} activada! (AP descontado)"
        else:
            return False, "Error de enlace con el servidor."
    except Exception as e:
        return False, f"Error técnico: {str(e)}"

# --- 📦 SUMINISTROS (CORREGIDO) ---
def cargar_estado_suministros():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        # CORRECCIÓN: Buscamos en "Clave"
        payload = {
            "filter": {
                "property": "Clave", 
                "title": {"equals": "DROP_SUMINISTROS"}
            }
        }
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def procesar_suministro(rewards):
    try:
        player = st.session_state.jugador
        new_ap = player.get("AP", {}).get("number", 0) + rewards["AP"]
        new_mp = player.get("MP", {}).get("number", 0) + rewards["MP"]
        new_vp = min(100, player.get("VP", {}).get("number", 0) + rewards["VP"])
        
        url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        payload = {
            "properties": {
                "AP": {"number": new_ap},
                "MP": {"number": new_mp},
                "VP": {"number": new_vp},
                "Ultimo Suministro": {"date": {"start": get_chile_time_iso()}}
            }
        }
        res = requests.patch(url, headers=headers, json=payload)
        if res.status_code == 200:
            registrar_evento_sistema(st.session_state.nombre, "Suministro Reclamado", str(rewards))
            return True
        return False
    except: return False

# --- 🔐 CÓDIGOS DE CANJE ---
def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline."
    
    url = f"https://api.notion.com/v1/databases/{DB_CODIGOS_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Código", "title": {"equals": codigo_input}},
                {"property": "Activo", "checkbox": {"equals": True}}
            ]
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        results = res.json().get("results", [])
        if not results: return False, "❌ Código inválido."
        
        code_page = results[0]
        props = code_page["properties"]
        page_id = code_page["id"]
        
        redeemed_text = ""
        if props.get("Redimido Por", {}).get("rich_text"):
            redeemed_text = props["Redimido Por"]["rich_text"][0]["text"]["content"]
            
        if st.session_state.nombre in [x.strip() for x in redeemed_text.split(",")]:
            return False, "⚠️ Ya canjeaste este código."

        limit = props.get("Limite Usos", {}).get("number")
        current_uses = props.get("Usos Actuales", {}).get("number", 0)
        if limit is not None and current_uses >= limit:
            return False, "⚠️ Código agotado."
            
        rew_ap = props.get("Valor AP", {}).get("number", 0)
        rew_mp = props.get("Valor MP", {}).get("number", 0)
        rew_vp = props.get("Valor VP", {}).get("number", 0)
        
        player = st.session_state.jugador
        new_ap = player.get("AP", {}).get("number", 0) + rew_ap
        new_mp = player.get("MP", {}).get("number", 0) + rew_mp
        new_vp = min(100, player.get("VP", {}).get("number", 0) + rew_vp)
        
        url_p = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        req_p = requests.patch(url_p, headers=headers, json={
            "properties": {"AP": {"number": new_ap}, "MP": {"number": new_mp}, "VP": {"number": new_vp}}
        })
        
        if req_p.status_code == 200:
            new_list = f"{redeemed_text}, {st.session_state.nombre}" if redeemed_text else st.session_state.nombre
            requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={
                "properties": {
                    "Usos Actuales": {"number": current_uses + 1},
                    "Redimido Por": {"rich_text": [{"text": {"content": new_list}}]}
                }
            })
            registrar_evento_sistema(st.session_state.nombre, "Canje Código", f"Code: {codigo_input}")
            return True, f"¡Canjeado! +{rew_ap} AP"
        return False, "Error al actualizar perfil."
    except Exception as e: return False, str(e)

# --- 🔮 TRIVIA ---
def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    payload = {"filter": {"property": "Activa", "checkbox": {"equals": True}}, "page_size": 30}
    try:
        res = requests.post(url, headers=headers, json=payload)
        results = res.json().get("results", [])
        if not results: return None
        
        q = random.choice(results)
        p = q["properties"]
        
        return {
            "ref_id": q["id"],
            "pregunta": p["Pregunta"]["title"][0]["text"]["content"],
            "opcion_a": p["Opción A"]["rich_text"][0]["text"]["content"],
            "opcion_b": p["Opción B"]["rich_text"][0]["text"]["content"],
            "opcion_c": p["Opción C"]["rich_text"][0]["text"]["content"],
            "correcta": p["Correcta"]["select"]["name"],
            "recompensa": p["Recompensa AP"]["number"],
            "exp_correcta": p.get("Explicación Correcta", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Correcto"),
            "exp_incorrecta": p.get("Explicación Incorrecta", {}).get("rich_text", [{}])[0].get("text", {}).get("content", "Incorrecto")
        }
    except: return None

def procesar_recalibracion(reward_ap, is_correct, question_id):
    if is_correct and reward_ap > 0:
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
        url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        requests.patch(url, headers=headers, json={"properties": {"AP": {"number": current_ap + reward_ap}}})
    
    url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    requests.patch(url, headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": get_chile_time_iso()}}}})
    
    res_text = "CORRECTO" if is_correct else "FALLO"
    registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"{res_text} (+{reward_ap if is_correct else 0})")
