import streamlit as st
import requests
import time
from datetime import datetime
import pytz
import random

# Importamos la configuración centralizada
from config import (
    HEADERS, 
    DB_CONFIG_ID, DB_LOGS_ID, DB_JUGADORES_ID, DB_MISIONES_ID, 
    DB_SOLICITUDES_ID, DB_CODIGOS_ID, DB_TRIVIA_ID, DB_HABILIDADES_ID
)

# --- ALIAS DE COMPATIBILIDAD ---
# Esto permite que el código copiado funcione sin cambiar "headers" por "HEADERS" en cada línea
headers = HEADERS 

# --- 🛡️ SISTEMA (KILL SWITCH & LOGS) ---
@st.cache_data(ttl=60, show_spinner=False)
def verificar_modo_mantenimiento():
    """Consulta si el Kill Switch está activo en Notion."""
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
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
                props = results[0]["properties"]
                return props.get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO"):
    """Registra eventos en la base de datos de Logs."""
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    
    chile_tz = pytz.timezone('America/Santiago')
    now = datetime.now(chile_tz).isoformat()
    
    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Usuario": {"title": [{"text": {"content": str(usuario)}}]},
            "Acción": {"rich_text": [{"text": {"content": str(accion)}}]},
            "Detalles": {"rich_text": [{"text": {"content": str(detalles)}}]},
            "Tipo": {"select": {"name": tipo}},
            "Fecha": {"date": {"start": now}}
        }
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=2)
    except: pass

# --- 👤 JUGADORES (PERFIL) ---
@st.cache_data(ttl=300, show_spinner="Conectando con la base de datos...")
def cargar_datos_jugador(email):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {
        "filter": {
            "property": "Email",
            "email": {"equals": email}
        }
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results:
                return results[0] # Retorna la página completa del jugador
        return None
    except: return None

# --- 🚀 MISIONES ---
@st.cache_data(ttl=600)
def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    payload = {
        "filter": {
            "property": "Estado",
            "status": {"equals": "Activa"}
        },
        "sorts": [{"property": "Fecha Lanzamiento", "direction": "ascending"}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        misiones = []
        if response.status_code == 200:
            for p in response.json().get("results", []):
                props = p["properties"]
                
                # Extracción segura de datos
                nombre = props["Misión"]["title"][0]["text"]["content"] if props["Misión"]["title"] else "Misión Clasificada"
                desc = props["Descripción"]["rich_text"][0]["text"]["content"] if props["Descripción"]["rich_text"] else ""
                tipo = props["Tipo"]["select"]["name"] if props["Tipo"]["select"] else "Misión"
                
                f_apertura = props["Fecha Apertura"]["date"]["start"] if props["Fecha Apertura"]["date"] else None
                f_cierre = props["Fecha Cierre"]["date"]["start"] if props["Fecha Cierre"]["date"] else None
                f_lanzamiento = props["Fecha Lanzamiento"]["date"]["start"] if props["Fecha Lanzamiento"]["date"] else None
                
                inscritos = ""
                if "Inscritos" in props and props["Inscritos"]["rich_text"]:
                    inscritos = props["Inscritos"]["rich_text"][0]["text"]["content"]
                
                target_unis = [x["name"] for x in props["Universidad Objetivo"]["multi_select"]] if props["Universidad Objetivo"]["multi_select"] else ["Todas"]
                password = props["Password"]["rich_text"][0]["text"]["content"] if props.get("Password", {}).get("rich_text") else "N/A"
                link = props["Link"]["url"] if props.get("Link", {}).get("url") else "#"
                
                misiones.append({
                    "id": p["id"],
                    "nombre": nombre,
                    "descripcion": desc,
                    "tipo": tipo,
                    "f_apertura": f_apertura,
                    "f_cierre": f_cierre,
                    "f_lanzamiento": f_lanzamiento,
                    "inscritos": inscritos,
                    "target_unis": target_unis,
                    "password": password,
                    "link": link
                })
        return misiones
    except: return []

def inscribir_jugador_mision(page_id, inscritos_actuales, nombre_jugador):
    nuevos_inscritos = f"{inscritos_actuales}, {nombre_jugador}" if inscritos_actuales else nombre_jugador
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Inscritos": {
                "rich_text": [{"text": {"content": nuevos_inscritos}}]
            }
        }
    }
    try:
        res = requests.patch(url, headers=headers, json=payload)
        if res.status_code == 200:
            registrar_evento_sistema(nombre_jugador, "Inscripción Misión", f"ID Misión: {page_id}")
            st.cache_data.clear() # Limpiamos caché para ver el cambio
            return True
        return False
    except: return False

# --- 📩 SOLICITUDES ---
def enviar_solicitud(tipo, mensaje, detalles, usuario):
    if not DB_SOLICITUDES_ID: return False
    url = "https://api.notion.com/v1/pages"
    
    chile_tz = pytz.timezone('America/Santiago')
    now = datetime.now(chile_tz).isoformat()
    
    payload = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Usuario": {"title": [{"text": {"content": usuario}}]},
            "Tipo": {"select": {"name": tipo}},
            "Mensaje": {"rich_text": [{"text": {"content": mensaje}}]},
            "Detalles": {"rich_text": [{"text": {"content": detalles}}]},
            "Estado": {"status": {"name": "Pendiente"}},
            "Fecha": {"date": {"start": now}}
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        return res.status_code == 200
    except: return False

# --- 🔐 CÓDIGOS (BLINDADO) ---
def procesar_codigo_canje(codigo_input):
    # 1. Validación de Estado (Lista Negra)
    estado_actual = str(st.session_state.get("estado_uam", "")).strip()
    if estado_actual in ["Finalizado", "Expulsado", "Retirado"]:
        return False, "⛔ Acceso denegado. Protocolo exclusivo para aspirantes activos."

    if not DB_CODIGOS_ID: return False, "Sistema de códigos no configurado."
    
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
        if res.status_code != 200: return False, "Error de conexión."
        
        results = res.json().get("results", [])
        if not results: return False, "❌ Código inválido, expirado o no existe."
        
        code_page = results[0]
        props = code_page["properties"]
        page_id = code_page["id"]
        
        redeemed_text = ""
        if "Redimido Por" in props and props["Redimido Por"]["rich_text"]:
            redeemed_text = props["Redimido Por"]["rich_text"][0]["text"]["content"]
        
        # Normalizamos nombres para evitar errores de espacios
        lista_redimidos = [x.strip() for x in redeemed_text.split(",")]
        
        if st.session_state.nombre in lista_redimidos:
            return False, "⚠️ Ya has canjeado este código previamente."
            
        limit = props.get("Limite Usos", {}).get("number")
        current_uses = props.get("Usos Actuales", {}).get("number") or 0
        
        if limit is not None and current_uses >= limit:
            return False, "⚠️ Este código ha alcanzado su límite máximo de usos."
            
        rew_ap = props.get("Valor AP", {}).get("number") or 0
        rew_mp = props.get("Valor MP", {}).get("number") or 0
        rew_vp = props.get("Valor VP", {}).get("number") or 0
        
        # Actualización local (pre-calculo)
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0) or 0
        current_mp = st.session_state.jugador.get("MP", {}).get("number", 0) or 0
        current_vp = st.session_state.jugador.get("VP", {}).get("number", 0) or 0
        
        new_ap = current_ap + rew_ap
        new_mp = current_mp + rew_mp
        new_vp = min(100, current_vp + rew_vp)
        
        # 1. Actualizar Jugador
        player_pid = st.session_state.player_page_id
        url_player = f"https://api.notion.com/v1/pages/{player_pid}"
        payload_player = {"properties": {"AP": {"number": new_ap}, "MP": {"number": new_mp}, "VP": {"number": new_vp}}}
        
        req_p = requests.patch(url_player, headers=headers, json=payload_player)
        if req_p.status_code != 200: return False, "Error al actualizar perfil."
        
        # 2. Actualizar Código
        new_uses = current_uses + 1
        new_redeemed_list = redeemed_text + "," + st.session_state.nombre if redeemed_text else st.session_state.nombre
        
        url_code = f"https://api.notion.com/v1/pages/{page_id}"
        payload_code = {
            "properties": {
                "Usos Actuales": {"number": new_uses},
                "Redimido Por": {"rich_text": [{"text": {"content": new_redeemed_list}}]}
            }
        }
        requests.patch(url_code, headers=headers, json=payload_code)
        
        detalles = f"Código: {codigo_input} | +{rew_ap} AP, +{rew_mp} MP, +{rew_vp} VP"
        registrar_evento_sistema(st.session_state.nombre, "Canje Código", detalles)
        
        return True, f"¡Código Canjeado! +{rew_ap} AP, +{rew_mp} MP"
        
    except Exception as e:
        return False, f"Error técnico: {str(e)}"

# --- 🔮 TRIVIA ---
def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    # Filtro aleatorio simple (offset no soportado nativo, traemos lote pequeño)
    payload = {
         "filter": {"property": "Activa", "checkbox": {"equals": True}},
         "page_size": 30
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        results = res.json().get("results", [])
        if not results: return None
        
        q_page = random.choice(results)
        props = q_page["properties"]
        
        return {
            "ref_id": q_page["id"],
            "pregunta": props["Pregunta"]["title"][0]["text"]["content"],
            "opcion_a": props["Opción A"]["rich_text"][0]["text"]["content"],
            "opcion_b": props["Opción B"]["rich_text"][0]["text"]["content"],
            "opcion_c": props["Opción C"]["rich_text"][0]["text"]["content"],
            "correcta": props["Correcta"]["select"]["name"], # "A", "B", "C"
            "recompensa": props["Recompensa AP"]["number"],
            "exp_correcta": props["Explicación Correcta"]["rich_text"][0]["text"]["content"] if props.get("Explicación Correcta", {}).get("rich_text") else "¡Correcto!",
            "exp_incorrecta": props["Explicación Incorrecta"]["rich_text"][0]["text"]["content"] if props.get("Explicación Incorrecta", {}).get("rich_text") else "Incorrecto."
        }
    except: return None

def procesar_recalibracion(reward_ap, is_correct, question_id):
    # 1. Actualizar AP Jugador
    if is_correct and reward_ap > 0:
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
        new_ap = current_ap + reward_ap
        url_p = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        requests.patch(url_p, headers=headers, json={"properties": {"AP": {"number": new_ap}}})
    
    # 2. Registrar el intento en el jugador (Fecha última recalibración)
    chile_tz = pytz.timezone('America/Santiago')
    now = datetime.now(chile_tz).isoformat()
    
    url_p_date = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    requests.patch(url_p_date, headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": now}}}})
    
    # 3. Log
    res_text = "CORRECTO" if is_correct else "FALLO"
    registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"Resultado: {res_text} | +{reward_ap if is_correct else 0} AP")

# --- 📦 SUMINISTROS (LOOT) ---
def cargar_estado_suministros():
    """Retorna True si el sistema de suministros está activo globalmente."""
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "SUMINISTROS_ACTIVOS"}}}
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def procesar_suministro(rewards):
    """Aplica las recompensas del loot al jugador y actualiza la fecha de cobro."""
    try:
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
        current_mp = st.session_state.jugador.get("MP", {}).get("number", 0)
        current_vp = st.session_state.jugador.get("VP", {}).get("number", 0)
        
        new_ap = current_ap + rewards["AP"]
        new_mp = current_mp + rewards["MP"]
        new_vp = min(100, current_vp + rewards["VP"])
        
        chile_tz = pytz.timezone('America/Santiago')
        now = datetime.now(chile_tz).isoformat()
        
        url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        payload = {
            "properties": {
                "AP": {"number": new_ap},
                "MP": {"number": new_mp},
                "VP": {"number": new_vp},
                "Ultimo Suministro": {"date": {"start": now}}
            }
        }
        res = requests.patch(url, headers=headers, json=payload)
        
        if res.status_code == 200:
            registrar_evento_sistema(st.session_state.nombre, "Suministro Reclamado", f"Recibido: {rewards}")
            return True
        return False
    except: return False