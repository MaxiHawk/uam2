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

# --- 🛡️ SISTEMA (ACTUALIZADO: SOPORTE ID_REF) ---
def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO", uni_override=None, ano_override=None, id_ref=None):
    if not DB_LOGS_ID: return
    url = "https://api.notion.com/v1/pages"
    
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
    
    # Metadata opcional
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}
    
    # --- NUEVO: ID_Ref Numérico ---
    if id_ref is not None:
        try:
            properties["ID_Ref"] = {"number": int(id_ref)}
        except: pass # Si no es número, lo ignoramos para no romper el log
    # ------------------------------

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

# --- 🚀 MISIONES (CON NARRATIVA Y RECOMPENSAS) ---
@st.cache_data(ttl=600)
def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    
    payload = {
        "filter": {"property": "Activa", "checkbox": {"equals": True}},
        "sorts": [{"property": "Lanzamiento", "direction": "ascending"}]
    }
    
    raw_results = notion_fetch_all(url, payload)
    
    misiones = []
    for r in raw_results:
        p = r["properties"]
        misiones.append({
            "id": r["id"],
            "nombre": get_notion_text(p, "Nombre", "Operación Sin Título"), 
            "descripcion": get_notion_text(p, "Descripcion", ""),
            "tipo": get_notion_select(p, "Tipo", "Hazaña"),
            "f_apertura": get_notion_date(p, "Apertura Inscripciones"),
            "f_cierre": get_notion_date(p, "Cierre Inscripciones"),
            "f_lanzamiento": get_notion_date(p, "Lanzamiento"),
            "inscritos": get_notion_text(p, "Inscritos"),
            "target_unis": get_notion_multi_select(p, "Universidad"),
            "password": get_notion_text(p, "Password"),
            "link": get_notion_url(p, "Enlace"),
            # --- NUEVOS CAMPOS ---
            "narrativa": get_notion_text(p, "Narrativa", "Información Clasificada."),
            "recompensas_txt": get_notion_text(p, "Recompensas Texto", "Recompensa Standard"),
            "insignia_file": get_notion_text(p, "Insignia ID"), # Ej: hazana_1.png
            "advertencia": get_notion_text(p, "Advertencia", "El incumplimiento será sancionado.")
        })
    return misiones

# --- 📝 INSCRIPCIÓN (AHORA CON LOG LEGIBLE) ---
def inscribir_jugador_mision(page_id, _unused_str, player_name, mision_nombre="Actividad Clasificada"):
    """
    Inscribe al jugador obteniendo primero la data FRESCA de Notion para evitar sobrescrituras
    por caché. (Anti-Race Condition).
    """
    if not DB_MISIONES_ID: return False
    
    url_page = f"https://api.notion.com/v1/pages/{page_id}"
    
    try:
        # 1. BLINDAJE: Consultamos la lista REAL actual en el servidor (bypaseando caché local)
        get_res = requests.get(url_page, headers=headers, timeout=API_TIMEOUT)
        if get_res.status_code != 200: return False
        
        props = get_res.json()["properties"]
        # Leemos la propiedad "Inscritos" directamente de la fuente
        current_real_str = get_notion_text(props, "Inscritos", "")
        
        # 2. Procesamos sobre la data fresca
        lista = [x.strip() for x in current_real_str.split(",") if x.strip()]
        
        if player_name in lista: 
            return True # Ya estaba inscrito (según Notion)
            
        lista.append(player_name)
        new_str = ", ".join(lista)
        
        # 3. Guardamos la nueva lista
        payload = {
            "properties": {
                "Inscritos": {"rich_text": [{"text": {"content": new_str}}]}
            }
        }
        
        patch_res = requests.patch(url_page, headers=headers, json=payload, timeout=API_TIMEOUT)
        patch_res.raise_for_status()
        
        # 4. Log del Sistema
        registrar_evento_sistema(
            player_name, 
            "Inscripción Operación", 
            f"Confirmado en: {mision_nombre}", 
            "Misión"
        )
        return True
        
    except Exception as e:
        print(f"Error inscripción blindada: {e}")
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

# --- 🛍️ MERCADO ---
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
    detalles = f"Costo: {cost_ap} AP"
    
    if enviar_solicitud("Poder", msg, detalles, st.session_state.nombre):
        registrar_evento_sistema(st.session_state.nombre, "Solicitud Habilidad", f"{skill_name} (-{cost_ap} AP)", "Habilidad")
        return True, "Solicitud enviada."
    
    return False, "Error al enviar solicitud."
# --- 🛒 MERCADO (NUEVO BLINDAJE) ---
def procesar_compra_mercado(item_nombre, costo, is_real_money=False):
    try:
        # Solo verificamos saldo si NO es dinero real
        current_ap = 0
        if not is_real_money:
            url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
            res_player = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
            res_player.raise_for_status()
            props_reales = res_player.json()["properties"]
            current_ap = get_notion_number(props_reales, "AP")
            
            if current_ap < costo:
                return False, f"Saldo insuficiente. (Tienes: {current_ap} AP, Requiere: {costo})"
        
    except Exception as e:
        if not is_real_money: # Solo importa si es AP
            print(f"⚠️ Error leyendo saldo en vivo: {e}")
            current_ap = get_notion_number(st.session_state.jugador.get("properties", {}), "AP")
            if current_ap < costo: return False, "Saldo insuficiente (Cache)."

    msg = f"Solicitud de compra: {item_nombre}"
    
    # Diferenciamos el detalle según el tipo de moneda
    if is_real_money:
        detalles = f"Precio: ${costo:,} CLP (DINERO REAL) - No descontar AP"
    else:
        detalles = f"Costo: {costo} AP"
    
    if enviar_solicitud("COMPRA", msg, detalles, st.session_state.nombre):
        log_detail = f"{item_nombre} (${costo})" if is_real_money else f"{item_nombre} (-{costo} AP)"
        registrar_evento_sistema(st.session_state.nombre, "Solicitud Mercado", log_detail, "Mercado")
        return True, "Solicitud enviada. Coordinar pago con Admin." if is_real_money else "Solicitud enviada."
    
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

# --- EN modules/notion_api.py ---

def cargar_estado_suministros():
    """
    Consulta la configuración de 'DROP_SUMINISTROS' en Notion.
    Retorna una tupla: (estado_activo: bool, filtro_universidad: str)
    Ejemplo: (True, "Universidad de Valparaíso") o (False, "Todas")
    """
    # Si no hay ID de config, asumimos apagado
    if not DB_CONFIG_ID: return False, "Todas"
    
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    
    # Filtramos para buscar exactamente la fila de configuración de Drops
    payload = {
        "filter": {
            "property": "Clave",
            "title": {
                "equals": "DROP_SUMINISTROS"
            }
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                props = results[0]["properties"]
                
                # 1. Leemos el Checkbox "Activo"
                estado = props.get("Activo", {}).get("checkbox", False)
                
                # 2. Leemos el Texto "Filtro" (Si está vacío, asumimos "Todas")
                filtro_list = props.get("Filtro", {}).get("rich_text", [])
                filtro_txt = filtro_list[0]["text"]["content"] if filtro_list else "Todas"
                
                return estado, filtro_txt
                
    except Exception as e:
        print(f"Error consultando suministros: {e}")
        pass
        
    # Default por seguridad: Apagado y para Todas
    return False, "Todas"

# --- 🔐 CÓDIGOS (VERSIÓN 2.0: INSIGNIAS + SEGURIDAD) ---
def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline.", None
    if not validar_codigo_seguro(codigo_input): return False, "❌ Formato inválido.", None

    # 1. Buscamos el código
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
        if not results: return False, "❌ Código inválido o expirado.", None
        
        code_page = results[0]
        p_code = code_page["properties"]
        
        # 2. Validación de Uso (Lista de Texto Exacta)
        redeemed_text = get_notion_text(p_code, "Redimido Por")
        # Convertimos la lista de texto en una lista real de Python, limpiando espacios
        lista_usuarios = [x.strip() for x in redeemed_text.split(",") if x.strip()]
        
        if st.session_state.nombre in lista_usuarios:
            return False, "⚠️ Ya canjeaste este código anteriormente.", None

        limit = get_notion_number(p_code, "Limite Usos", None) 
        current_uses = get_notion_number(p_code, "Usos Actuales")
        if limit is not None and current_uses >= limit: 
            return False, "⚠️ Código agotado (Límite alcanzado).", None
            
        # 3. Lectura de Recompensas
        rew_ap = get_notion_number(p_code, "Valor AP")
        rew_mp = get_notion_number(p_code, "Valor MP")
        rew_vp = get_notion_number(p_code, "Valor VP")
        rew_badge = get_notion_select(p_code, "Insignia") # <--- NUEVO: Lee la insignia
        
        # 4. Actualización del Jugador (Lectura + Escritura)
        url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        res_player = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
        res_player.raise_for_status()
        p_player_real = res_player.json()["properties"]
        
        # Cálculos Puntos
        new_ap = get_notion_number(p_player_real, "AP") + rew_ap
        new_mp = get_notion_number(p_player_real, "MP") + rew_mp
        new_vp = min(100, get_notion_number(p_player_real, "VP") + rew_vp)
        
        # Lógica de Insignias (Append)
        player_updates = {
            "AP": {"number": new_ap}, 
            "MP": {"number": new_mp}, 
            "VP": {"number": new_vp}
        }
        
        badge_granted = False
        if rew_badge:
            # Obtenemos insignias actuales (Lista de objetos Multi-Select)
            current_badges_objs = p_player_real.get("Insignias", {}).get("multi_select", [])
            current_badges_names = [b["name"] for b in current_badges_objs]
            
            if rew_badge not in current_badges_names:
                # Agregamos la nueva (Notion requiere enviar TODA la lista de nuevo)
                new_badges_list = [{"name": n} for n in current_badges_names] + [{"name": rew_badge}]
                player_updates["Insignias"] = {"multi_select": new_badges_list}
                badge_granted = True
        
        # Patch Jugador
        req_p = requests.patch(url_player, headers=headers, json={"properties": player_updates}, timeout=API_TIMEOUT)
        req_p.raise_for_status()
        
        # 5. Actualización del Código (Consumo)
        # Agregamos el nombre con coma y espacio para mantener el formato limpio
        new_list_text = f"{redeemed_text}, {st.session_state.nombre}" if redeemed_text else st.session_state.nombre
        
        req_c = requests.patch(f"https://api.notion.com/v1/pages/{code_page['id']}", headers=headers, json={
            "properties": {
                "Usos Actuales": {"number": current_uses + 1},
                "Redimido Por": {"rich_text": [{"text": {"content": new_list_text}}]}
            }
        }, timeout=API_TIMEOUT)
        req_c.raise_for_status()
        
        # 6. Reporte Final
        detalle = f"Código: {codigo_input} | +{rew_ap} AP"
        if badge_granted: detalle += f" | Insignia: {rew_badge}"
        
        registrar_evento_sistema(st.session_state.nombre, "Canje Código", detalle, "Código")
        
        # Retornamos datos estructurados para la UI
        return True, "Código aceptado.", {"AP": rew_ap, "Insignia": rew_badge if badge_granted else None}
        
    except Exception as e: return False, f"Error técnico: {str(e)}", None

# --- 🔮 TRIVIA (CALIBRADO CON SCHEMA REAL) ---
def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    
    # Filtro: Solo preguntas activas
    payload = {"filter": {"property": "Activa", "checkbox": {"equals": True}}}
    
    try:
        # 1. Usamos fetch_all para obtener el POOL COMPLETO (no solo las primeras 30)
        # Esto soluciona el "Límite Invisible"
        raw_results = notion_fetch_all(url, payload)
        
        if not raw_results: return None
        
        # 2. Selección Aleatoria Real
        q = random.choice(raw_results)
        p = q["properties"]
        
        # 3. Mapeo Exacto
        return {
            "ref_id": q["id"],
            "public_id": get_notion_unique_id(p, "ID_TRIVIA"), 
            "pregunta": get_notion_text(p, "Pregunta"),
            "opcion_a": get_notion_text(p, "Opcion A"), # Schema: Sin tilde
            "opcion_b": get_notion_text(p, "Opcion B"),
            "opcion_c": get_notion_text(p, "Opcion C"),
            "correcta": get_notion_select(p, "Correcta"),
            "recompensa": get_notion_number(p, "Recompensa"), # Schema: "Recompensa" (no AP)
            "exp_correcta": get_notion_text(p, "Explicacion Correcta", "Correcto"), # Schema: Sin tilde
            "exp_incorrecta": get_notion_text(p, "Explicacion Incorrecta", "Incorrecto") # Schema: Sin tilde
        }
    except Exception as e:
        print(f"Error Trivia: {e}")
        return None

def procesar_recalibracion(reward_ap, is_correct, question_id, public_id_trivia=None):
    """
    Procesa el resultado de la trivia de forma segura y registra el ID público.
    """
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    url_player = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    
    try:
        # 1. Si ganó, sumamos AP
        if is_correct and reward_ap > 0:
            res_get = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
            res_get.raise_for_status()
            current_ap = get_notion_number(res_get.json()["properties"], "AP")
            
            requests.patch(url_player, headers=headers, json={
                "properties": {"AP": {"number": current_ap + reward_ap}}
            }, timeout=API_TIMEOUT)
        
        # 2. Registramos fecha
        requests.patch(url_player, headers=headers, json={
            "properties": {"Ultima Recalibracion": {"date": {"start": now_iso}}}
        }, timeout=API_TIMEOUT)
        
        # 3. Log del Sistema con ID_Ref
        res_text = "CORRECTO" if is_correct else "FALLO"
        id_ref_str = f"#{public_id_trivia}" if public_id_trivia else ""
        detalle_log = f"Trivia {id_ref_str}: {res_text} (+{reward_ap if is_correct else 0} AP)"
        
        # Enviamos public_id_trivia al nuevo parámetro id_ref
        registrar_evento_sistema(
            st.session_state.nombre, 
            "Trivia Oráculo", 
            detalle_log, 
            "Trivia",
            id_ref=public_id_trivia # <--- AQUÍ SE ENVÍA EL DATO
        )
        return True
    except Exception as e: 
        print(f"Error procesando trivia: {e}")
        return False

# --- 👮‍♂️ FUNCIONES DE ADMIN ---

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
    """
    # 1. PARSEO DE COSTOS
    costo_ap = 0
    try:
        match_ap = re.search(r'Costo:.*?(\d+)\s*AP', detalles_texto, re.IGNORECASE)
        if match_ap: costo_ap = int(match_ap.group(1))
    except: return False, "Error leyendo los costos."

    if costo_ap == 0: return False, "No se encontró costo AP en la solicitud."

    # 2. COBRO AL JUGADOR
    player_page_id = buscar_page_id_por_nombre(nombre_jugador)
    if not player_page_id: return False, f"No se encontró al jugador {nombre_jugador}."
        
    player_uni = None
    player_ano = None

    try:
        url_player = f"https://api.notion.com/v1/pages/{player_page_id}"
        res_get = requests.get(url_player, headers=headers, timeout=API_TIMEOUT)
        res_get.raise_for_status()
        
        props = res_get.json()["properties"]
        current_ap = get_notion_number(props, "AP")
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

    # 3. ACTUALIZAR SOLICITUD (FIX: Usar propiedad 'Observaciones')
    now_iso = datetime.now(pytz.timezone('America/Santiago')).isoformat()
    try:
        url_req = f"https://api.notion.com/v1/pages/{request_id}"
        payload_req = {
            "properties": {
                "Status": {"select": {"name": "Aprobado"}},
                "Procesado": {"checkbox": True}, 
                "Fecha respuesta": {"date": {"start": now_iso}}, 
                # AQUÍ ESTÁ EL CAMBIO CRÍTICO:
                "Observaciones": {"rich_text": [{"text": {"content": "✅ Solicitud procesada y saldo descontado."}}]}
            }
        }
        res_update = requests.patch(url_req, headers=headers, json=payload_req, timeout=API_TIMEOUT)
        res_update.raise_for_status()
        
        registrar_evento_sistema(
            nombre_jugador, "Solicitud Aprobada", f"Aprobado (-{costo_ap} AP)", 
            "Habilidad", uni_override=player_uni, ano_override=player_ano
        )
        return True, "✅ Cobro realizado y solicitud cerrada correctamente."
        
    except Exception as e:
        err_msg = str(e)
        if hasattr(e, 'response') and e.response is not None:
             err_msg = e.response.text
        return False, f"Cobro OK, pero falló actualizar solicitud (Revisar nombres columnas): {err_msg}"

# --- 🧬 SQUAD SYNC (CALIBRADO: UNI + AÑO + NO ALUMNI) ---
def obtener_miembros_escuadron(nombre_escuadron, uni, ano):
    """
    Retorna miembros del escuadrón que coincidan en Universidad y Año,
    y que NO sean Alumni (Estado != Finalizado).
    """
    if not nombre_escuadron or nombre_escuadron == "Sin Escuadrón": return []
    if not uni or not ano: return []
    
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    
    # Filtro compuesto: Escuadrón + Uni + Año + Activo
    payload = {
        "filter": {
            "and": [
                {"property": "Nombre Escuadrón", "rich_text": {"equals": nombre_escuadron}},
                {"property": "Universidad", "select": {"equals": uni}},
                {"property": "Año", "select": {"equals": ano}},
                {"property": "Estado UAM", "select": {"does_not_equal": "Finalizado"}} # Excluye Alumni
            ]
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        miembros = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                try:
                    props = r["properties"]
                    if "Jugador" in props and props["Jugador"]["title"]:
                        name = props["Jugador"]["title"][0]["text"]["content"]
                        miembros.append(name)
                except: pass
        return miembros
    except Exception as e:
        print(f"Error obteniendo squad: {e}")
        return []
# --- 📜 CÓDICE (CALIBRADO CON SCHEMA) ---
@st.cache_data(ttl=3600)
def cargar_codice():
    if not DB_CODICE_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_CODICE_ID}/query"
    # Ordenamos por nivel requerido (los más básicos primero)
    payload = {"sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]}
    
    try:
        raw_results = notion_fetch_all(url, payload)
        items = []
        for r in raw_results:
            props = r["properties"]
            try:
                # 1. Título
                nombre = get_notion_text(props, "Nombre", "Documento Sin Título")
                
                # 2. Descripción (Ojo con la tilde)
                desc = get_notion_text(props, "Descripción", "Sin descripción disponible.")
                
                # 3. Tipo (Select)
                tipo = get_notion_select(props, "Tipo", "General")
                
                # 4. Nivel
                nivel = get_notion_number(props, "Nivel Requerido", 1)
                
                # 5. URL del Recurso (Prioridad: Archivo > Enlace)
                url_recurso = "#"
                file_url = get_notion_file_url(props, "Archivo")
                link_url = get_notion_url(props, "Enlace")
                
                if file_url: url_recurso = file_url
                elif link_url: url_recurso = link_url
                
                items.append({
                    "id": r["id"],
                    "nombre": nombre, 
                    "descripcion": desc,
                    "tipo": tipo,
                    "nivel": nivel, 
                    "url": url_recurso
                })
            except Exception as e:
                print(f"Error parseando item codice: {e}")
                pass
        return items
    except Exception as e:
        print(f"Error carga codice: {e}")
        return []
