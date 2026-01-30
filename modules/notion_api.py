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
    get_notion_checkbox, get_notion_file_url, validar_codigo_seguro
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
    except Exception as e: 
        print(f"❌ ERROR METADATA: {e}")
        return None, None

def notion_fetch_all(url, payload):
    """Función maestra con Paginación + TIMEOUT + VALIDACIÓN DE STATUS."""
    results = []
    has_more = True
    next_cursor = None
    if payload is None: payload = {}

    while has_more:
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
            response.raise_for_status() 
            data = response.json()
            results.extend(data.get("results", []))
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor", None)
        except requests.exceptions.HTTPError as err:
            print(f"❌ Error HTTP Notion: {err.response.status_code} - {err.response.text}")
            has_more = False
        except Exception as e:
            print(f"❌ Error Conexión: {e}")
            has_more = False
    return results

# --- 🛡️ SISTEMA (MODIFICADO PARA LOGS EXPLÍCITOS) ---
def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO", uni_override=None, ano_override=None):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    
    # Si nos pasan uni/ano (desde admin), usamos eso. Si no, buscamos en sesión.
    if uni_override and ano_override:
        uni, ano = uni_override, ano_override
    else:
        uni, ano = get_player_metadata()
        
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    
    properties = {
        "Evento": {"title": [{"text": {"content": str(accion)}}]}, 
        "Jugador": {"rich_text": [{"text": {"content": str(usuario)}}]},
        "Detalle": {"rich_text": [{"text": {"content": str(detalles)}}]},
        "Tipo": {"select": {"name": tipo}},
        "Fecha": {"date": {"start": now_iso}}
    }
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}

    try: requests.post(url, headers=headers, json={"parent": {"database_id": DB_LOGS_ID}, "properties": properties}, timeout=5)
    except: pass

@st.cache_data(ttl=60, show_spinner=False)
def verificar_modo_mantenimiento():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "MODO_MANTENIMIENTO"}}}
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results: return get_notion_checkbox(results[0]["properties"], "Activo")
        return False
    except: return False

# --- 👤 JUGADORES ---
@st.cache_data(ttl=300, show_spinner="Sincronizando perfil...")
def cargar_datos_jugador(email):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Correo electrónico", "email": {"equals": email}}}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        response.raise_for_status()
        results = response.json().get("results", [])
        if results: return results[0]
        return None
    except Exception as e:
        print(f"❌ Error Login: {e}")
        return None

# --- 📢 ANUNCIOS ---
@st.cache_data(ttl=600)
def cargar_anuncios():
    if not DB_ANUNCIOS_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_ANUNCIOS_ID}/query"
    payload = {
        "filter": {"property": "Activo", "checkbox": {"equals": True}},
        "sorts": [{"timestamp": "created_time", "direction": "descending"}]
    }
    raw_results = notion_fetch_all(url, payload)
    anuncios = []
    for r in raw_results:
        p = r["properties"]
        anuncios.append({
            "titulo": get_notion_text(p, "Titulo", "Anuncio"),
            "contenido": get_notion_text(p, "Contenido"),
            "universidad": get_notion_multi_select(p, "Universidad"),
            "año": get_notion_multi_select(p, "Año"),
            "fecha": get_notion_date(p, "Fecha") or r["created_time"]
        })
    return anuncios

# --- 🚀 MISIONES ---
@st.cache_data(ttl=600)
def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    payload = {
        "filter": {"property": "Estado", "status": {"equals": "Activa"}},
        "sorts": [{"property": "Fecha Lanzamiento", "direction": "ascending"}]
    }
    raw_results = notion_fetch_all(url, payload)
    misiones = []
    for r in raw_results:
        p = r["properties"]
        misiones.append({
            "id": r["id"],
            "nombre": get_notion_text(p, "Misión", "Sin Título"),
            "descripcion": get_notion_text(p, "Descripción"),
            "tipo": get_notion_select(p, "Tipo", "Misión"),
            "f_apertura": get_notion_date(p, "Fecha Apertura"),
            "f_cierre": get_notion_date(p, "Fecha Cierre"),
            "f_lanzamiento": get_notion_date(p, "Fecha Lanzamiento"),
            "inscritos": get_notion_text(p, "Inscritos"),
            "target_unis": get_notion_multi_select(p, "Universidad Objetivo"),
            "password": get_notion_text(p, "Password"),
            "link": get_notion_url(p, "Link")
        })
    return misiones

def inscribir_jugador_mision(page_id, inscritos_frontend, nombre_jugador):
    url_get = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        res_get = requests.get(url_get, headers=headers, timeout=API_TIMEOUT)
        res_get.raise_for_status()
        
        props_live = res_get.json()["properties"]
        texto_inscritos_real = get_notion_text(props_live, "Inscritos")
        
        lista_actual = [x.strip() for x in texto_inscritos_real.split(",")]
        if nombre_jugador in lista_actual: return True 
            
        nuevo_texto = f"{texto_inscritos_real}, {nombre_jugador}" if texto_inscritos_real else nombre_jugador
        url_patch = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"properties": {"Inscritos": {"rich_text": [{"text": {"content": nuevo_texto}}]}}}
        res_patch = requests.patch(url_patch, headers=headers, json=payload, timeout=API_TIMEOUT)
        res_patch.raise_for_status()
        
        registrar_evento_sistema(nombre_jugador, "Inscripción Misión", f"ID: {page_id}", "Misión")
        st.cache_data.clear() 
        return True
    except Exception as e:
        print(f"Error inscripción: {e}")
        return False

# --- ⚡ HABILIDADES ---
@st.cache_data(ttl=3600)
def cargar_habilidades(rol_jugador):
    if not rol_jugador or not DB_HABILIDADES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    payload = {
        "filter": {"property": "Rol", "select": {"equals": rol_jugador}}, 
        "sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        res.raise_for_status()
        habilidades = []
        for item in res.json()["results"]:
            p = item["properties"]
            nombre = "Habilidad Sin Nombre"
            for key, val in p.items():
                if val['type'] == 'title':
                    content_list = val.get("title", [])
                    if content_list: nombre = "".join([t.get("plain_text", "") for t in content_list])
                    break 
            costo = get_notion_number(p, "Costo AP") or get_notion_number(p, "Costo")
            habilidades.append({
                "id": item["id"], 
                "nombre": nombre, 
                "costo": costo, 
                "nivel_req": get_notion_number(p, "Nivel Requerido", 1),
                "desc": get_notion_text(p, "Descripcion", "Sin descripción"),
                "icon_url": get_notion_file_url(p, "Icono")
            })
        return habilidades
    except Exception as e:
        print(f"Error cargando habilidades: {e}")
        return []

# --- 📩 SOLICITUDES ---
def enviar_solicitud(tipo, mensaje, detalles, usuario):
    if not DB_SOLICITUDES_ID: 
        st.error("❌ Error: DB_SOLICITUDES_ID no configurada.")
        return False
    url = "https://api.notion.com/v1/pages"
    uni, ano = get_player_metadata()
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    
    properties = {
        "Remitente": {"title": [{"text": {"content": str(usuario)}}]},
        "Tipo": {"select": {"name": tipo}},
        "Mensaje": {"rich_text": [{"text": {"content": f"{mensaje}\n\nDetalles: {detalles}"}}]}, 
        "Status": {"select": {"name": "Pendiente"}}, 
        "Fecha de creación": {"date": {"start": now_iso}} 
    }
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}

    try: 
        res = requests.post(url, headers=headers, json={"parent": {"database_id": DB_SOLICITUDES_ID}, "properties": properties}, timeout=API_TIMEOUT)
        res.raise_for_status()
        return True
    except Exception as e: 
        err_msg = "Error desconocido"
        if hasattr(e, 'response') and e.response is not None:
            try: err_msg = e.response.json().get('message', e.response.text)
            except: err_msg = e.response.text
        else: err_msg = str(e)
        st.error(f"⛔ Error de Notion: {err_msg}")
        return False

# --- 🛍️ MERCADO (LOG MEJORADO) ---
def procesar_compra_habilidad(skill_name, cost_ap, cost_mp, skill_id_notion):
    try:
        url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        res_player = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
        res_player.raise_for_status()
        props_reales = res_player.json()["properties"]
        current_ap = get_notion_number(props_reales, "AP")
        current_mp = get_notion_number(props_reales, "MP")
    except Exception as e:
        print(f"⚠️ Error leyendo saldo en vivo: {e}")
        current_ap = get_notion_number(st.session_state.jugador.get("properties", {}), "AP")
        current_mp = get_notion_number(st.session_state.jugador.get("properties", {}), "MP")
    
    if current_ap < cost_ap:
        return False, f"Saldo insuficiente. (Tienes: {current_ap} AP)"

    msg = f"Solicitud de activación: {skill_name}"
    detalles = f"Costo: {cost_ap} AP" # Simplificado solo a AP
    
    if enviar_solicitud("Poder", msg, detalles, st.session_state.nombre):
        # FIX LOG: Tipo "Habilidad" y detalle con costo
        registrar_evento_sistema(st.session_state.nombre, "Solicitud Habilidad", f"{skill_name} (-{cost_ap} AP)", "Habilidad")
        return True, "Solicitud enviada."
    
    return False, "Error al enviar solicitud."

# --- 📦 SUMINISTROS ---
def cargar_estado_suministros():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "DROP_SUMINISTROS"}}}
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results: return get_notion_checkbox(results[0]["properties"], "Activo")
        return False
    except: return False

def procesar_suministro(rarity_name, rewards):
    try:
        url_get = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        res_get = requests.get(url_get, headers=headers, timeout=API_TIMEOUT)
        res_get.raise_for_status()
        
        props_reales = res_get.json()["properties"]
        current_ap = get_notion_number(props_reales, "AP")
        current_mp = get_notion_number(props_reales, "MP")
        current_vp = get_notion_number(props_reales, "VP")

        new_ap = current_ap + rewards["AP"]
        new_mp = current_mp + rewards["MP"]
        new_vp = min(100, current_vp + rewards["VP"])
        
        now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
        payload = {
            "properties": {
                "AP": {"number": new_ap},
                "MP": {"number": new_mp},
                "VP": {"number": new_vp},
                "Ultimo Suministro": {"date": {"start": now_iso}}
            }
        }
        res_patch = requests.patch(url_get, headers=headers, json=payload, timeout=API_TIMEOUT)
        res_patch.raise_for_status()
        
        detalle = f"Farmeo {rarity_name}: AP: +{rewards['AP']} | MP: +{rewards['MP']} | VP: +{rewards['VP']}"
        registrar_evento_sistema(st.session_state.nombre, "Suministro Reclamado", detalle, "Suministro")
        return True
    except Exception as e: 
        print(f"Error Suministro: {e}")
        return False

# --- 🔐 CÓDIGOS ---
def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline."
    if not validar_codigo_seguro(codigo_input): return False, "❌ Formato inválido."

    url_query = f"https://api.notion.com/v1/databases/{DB_CODIGOS_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Código", "title": {"equals": codigo_input.strip().upper()}},
                {"property": "Activo", "checkbox": {"equals": True}}
            ]
        }
    }
    try:
        res = requests.post(url_query, headers=headers, json=payload, timeout=API_TIMEOUT)
        res.raise_for_status()
        results = res.json().get("results", [])
        if not results: return False, "❌ Código inválido o expirado."
        
        code_page = results[0]
        p_code = code_page["properties"]
        
        redeemed_text = get_notion_text(p_code, "Redimido Por")
        if st.session_state.nombre in [x.strip() for x in redeemed_text.split(",")]:
            return False, "⚠️ Ya canjeaste este código."

        limit = get_notion_number(p_code, "Limite Usos", None) 
        current_uses = get_notion_number(p_code, "Usos Actuales")
        if limit is not None and current_uses >= limit: return False, "⚠️ Código agotado."
            
        rew_ap = get_notion_number(p_code, "Valor AP")
        rew_mp = get_notion_number(p_code, "Valor MP")
        rew_vp = get_notion_number(p_code, "Valor VP")
        
        url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        res_player = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
        res_player.raise_for_status()
        p_player_real = res_player.json()["properties"]
        
        new_ap = get_notion_number(p_player_real, "AP") + rew_ap
        new_mp = get_notion_number(p_player_real, "MP") + rew_mp
        new_vp = min(100, get_notion_number(p_player_real, "VP") + rew_vp)
        
        req_p = requests.patch(url_player, headers=headers, json={
            "properties": {"AP": {"number": new_ap}, "MP": {"number": new_mp}, "VP": {"number": new_vp}}
        }, timeout=API_TIMEOUT)
        req_p.raise_for_status()
        
        new_list = f"{redeemed_text}, {st.session_state.nombre}" if redeemed_text else st.session_state.nombre
        req_c = requests.patch(f"https://api.notion.com/v1/pages/{code_page['id']}", headers=headers, json={
            "properties": {
                "Usos Actuales": {"number": current_uses + 1},
                "Redimido Por": {"rich_text": [{"text": {"content": new_list}}]}
            }
        }, timeout=API_TIMEOUT)
        req_c.raise_for_status()
        
        detalle = f"Código: {codigo_input} | +{rew_ap} AP, +{rew_mp} MP, +{rew_vp} VP"
        registrar_evento_sistema(st.session_state.nombre, "Canje Código", detalle, "Código")
        return True, f"¡Canjeado! +{rew_ap} AP"
    except Exception as e: return False, f"Error: {str(e)}"

# --- 🔮 TRIVIA ---
def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    payload = {"filter": {"property": "Activa", "checkbox": {"equals": True}}, "page_size": 30}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        res.raise_for_status()
        results = res.json().get("results", [])
        if not results: return None
        q = random.choice(results)
        p = q["properties"]
        return {
            "ref_id": q["id"],
            "pregunta": get_notion_text(p, "Pregunta"),
            "opcion_a": get_notion_text(p, "Opción A"),
            "opcion_b": get_notion_text(p, "Opción B"),
            "opcion_c": get_notion_text(p, "Opción C"),
            "correcta": get_notion_select(p, "Correcta"),
            "recompensa": get_notion_number(p, "Recompensa AP"),
            "exp_correcta": get_notion_text(p, "Explicación Correcta", "Correcto"),
            "exp_incorrecta": get_notion_text(p, "Explicación Incorrecta", "Incorrecto")
        }
    except: return None

def procesar_recalibracion(reward_ap, is_correct, question_id):
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    try:
        if is_correct and reward_ap > 0:
            res_get = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
            res_get.raise_for_status()
            current_ap = get_notion_number(res_get.json()["properties"], "AP")
            requests.patch(url_player, headers=headers, json={"properties": {"AP": {"number": current_ap + reward_ap}}}, timeout=API_TIMEOUT)
        requests.patch(url_player, headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": now_iso}}}}, timeout=API_TIMEOUT)
        res_text = "CORRECTO" if is_correct else "FALLO"
        registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"{res_text} (+{reward_ap if is_correct else 0})", "Trivia")
    except: pass

# --- 👮‍♂️ FUNCIONES DE ADMIN (APROBACIÓN INTELIGENTE) ---

def buscar_page_id_por_nombre(nombre_jugador):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Jugador", "title": {"equals": nombre_jugador}}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results: return results[0]["id"]
    except: pass
    return None

def aprobar_solicitud_habilidad(request_id, nombre_jugador, detalles_texto):
    """
    1. Extrae solo costo AP.
    2. Descuenta saldo al jugador real.
    3. Marca solicitud como Aprobada, Procesada, Fecha Resp y Status.
    4. Loguea usando la Universidad/Año del jugador, no del admin.
    """
    # 1. PARSEO DE COSTOS (Solo buscamos AP ahora)
    costo_ap = 0
    try:
        # Busca "Costo: X AP" (case insensitive)
        match_ap = re.search(r'Costo:.*?(\d+)\s*AP', detalles_texto, re.IGNORECASE)
        if match_ap: costo_ap = int(match_ap.group(1))
    except: return False, "Error leyendo los costos."

    if costo_ap == 0: return False, "No se encontró costo AP en la solicitud."

    # 2. COBRO AL JUGADOR
    player_page_id = buscar_page_id_por_nombre(nombre_jugador)
    if not player_page_id: return False, f"No se encontró al jugador {nombre_jugador}."
        
    try:
        url_player = f"https://api.notion.com/v1/pages/{player_page_id}"
        res_get = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
        res_get.raise_for_status()
        
        props = res_get.json()["properties"]
        current_ap = get_notion_number(props, "AP")
        # Datos para el log (Identidad del alumno)
        player_uni = get_notion_select(props, "Universidad")
        player_ano = get_notion_select(props, "Año")
        
        if current_ap < costo_ap:
            return False, f"El jugador no tiene saldo suficiente (Tiene {current_ap} AP)."
            
        new_ap = current_ap - costo_ap
        req_patch = requests.patch(url_player, headers=headers, json={
            "properties": {"AP": {"number": new_ap}}
        }, timeout=API_TIMEOUT)
        req_patch.raise_for_status()
        
    except Exception as e: return False, f"Error al cobrar: {str(e)}"

    # 3. ACTUALIZAR SOLICITUD (STATUS + CHECKBOX + FECHA)
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    try:
        url_req = f"https://api.notion.com/v1/pages/{request_id}"
        payload_req = {
            "properties": {
                "Status": {"select": {"name": "Aprobado"}},
                "Procesado": {"checkbox": True}, # FIX: Checkbox para ocultar
                "Fecha respuesta": {"date": {"start": now_iso}}, # FIX: Fecha de cierre
                "Respuesta Comando": {"rich_text": [{"text": {"content": "✅ Solicitud procesada y saldo descontado."}}]}
            }
        }
        requests.patch(url_req, headers=headers, json=payload_req, timeout=API_TIMEOUT)
        
        # FIX LOG: Usamos uni/ano del jugador, no del admin
        registrar_evento_sistema(
            nombre_jugador, 
            "Solicitud Aprobada", 
            f"Aprobado (-{costo_ap} AP)", 
            "Habilidad", 
            uni_override=player_uni, 
            ano_override=player_ano
        )
        
        return True, "✅ Cobro realizado y solicitud cerrada correctamente."
        
    except Exception as e:
        return False, f"Se cobró pero falló cerrar la solicitud: {str(e)}"
