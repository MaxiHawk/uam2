import streamlit as st
import requests
import time
from datetime import datetime
import pytz
import random
import json
import re  # NUEVO: Para validación de expresiones regulares

# Importamos la configuración centralizada
from config import (
    HEADERS, 
    DB_CONFIG_ID, DB_LOGS_ID, DB_JUGADORES_ID, DB_MISIONES_ID, 
    DB_SOLICITUDES_ID, DB_CODIGOS_ID, DB_TRIVIA_ID, DB_HABILIDADES_ID,
    DB_ANUNCIOS_ID, DB_MERCADO_ID
)

# --- ALIAS DE COMPATIBILIDAD ---
headers = HEADERS 
TIMEOUT_SEC = 10  # NUEVO: Límite de tiempo estándar para peticiones (segundos)

# --- 🛠️ UTILIDADES INTERNAS ---
def get_chile_time_iso():
    return datetime.now(pytz.timezone('America/Santiago')).isoformat()

def get_player_metadata():
    """
    Recupera Universidad y Año de forma robusta desde la sesión.
    Prioriza las variables procesadas 'uni_actual' y 'ano_actual'.
    """
    try:
        uni = st.session_state.get("uni_actual")
        ano = st.session_state.get("ano_actual")
        if uni and ano: return uni, ano

        # Fallback
        if "jugador" in st.session_state and st.session_state.jugador:
            props = st.session_state.jugador.get("properties", {})
            if not uni and "Universidad" in props:
                sel = props["Universidad"].get("select")
                if sel: uni = sel.get("name")
            if not ano and "Año" in props:
                sel = props["Año"].get("select")
                if sel: ano = sel.get("name")
        return uni, ano
    except Exception as e: 
        print(f"❌ ERROR METADATA: {e}")
        return None, None

def validar_codigo_seguro(codigo):
    """
    NUEVO: Valida que el código tenga un formato seguro antes de enviarlo a la API.
    Permite solo letras mayúsculas, números y guiones.
    """
    if not codigo: return False
    codigo = codigo.strip().upper()
    # Regex: Solo A-Z, 0-9 y guiones (-). Evita inyecciones raras.
    if re.match(r'^[A-Z0-9-]+$', codigo):
        return True
    return False

def notion_fetch_all(url, payload):
    """Función maestra con Paginación + TIMEOUTS."""
    results = []
    has_more = True
    next_cursor = None
    if payload is None: payload = {}

    while has_more:
        if next_cursor: payload["start_cursor"] = next_cursor
        try:
            # NUEVO: Agregado timeout=TIMEOUT_SEC
            response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
            if response.status_code == 200:
                data = response.json()
                results.extend(data.get("results", []))
                has_more = data.get("has_more", False)
                next_cursor = data.get("next_cursor", None)
            else:
                print(f"❌ Error Notion {response.status_code}: {response.text}")
                has_more = False
        except Exception as e:
            print(f"❌ Error Conexión: {e}")
            has_more = False
    return results

# --- 🛡️ SISTEMA (CONFIG & LOGS) ---
@st.cache_data(ttl=60, show_spinner=False)
def verificar_modo_mantenimiento():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        payload = {"filter": {"property": "Clave", "title": {"equals": "MODO_MANTENIMIENTO"}}}
        res = requests.post(url, headers=headers, json=payload, timeout=5) # Timeout corto
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                return results[0]["properties"].get("Activo", {}).get("checkbox", False)
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

    payload = {"parent": {"database_id": DB_LOGS_ID}, "properties": properties}
    try: requests.post(url, headers=headers, json=payload, timeout=5)
    except: pass

# --- 👤 JUGADORES ---
@st.cache_data(ttl=300, show_spinner="Sincronizando perfil...")
def cargar_datos_jugador(email):
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"property": "Correo electrónico", "email": {"equals": email}}}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
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
    raw_results = notion_fetch_all(url, payload)
    
    anuncios = []
    for r in raw_results:
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
    for p in raw_results:
        props = p["properties"]
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
            "f_lanzamiento": props.get("Fecha Lanzamiento", {}).get("date", {}).get("start"),
            "inscritos": get_text("Inscritos"),
            "target_unis": [x["name"] for x in props.get("Universidad Objetivo", {}).get("multi_select", [])],
            "password": get_text("Password"),
            "link": props.get("Link", {}).get("url", "#")
        })
    return misiones

def inscribir_jugador_mision(page_id, inscritos_frontend, nombre_jugador):
    url_get = f"https://api.notion.com/v1/pages/{page_id}"
    try:
        # Paso 1: Leer estado actual real con timeout
        res_get = requests.get(url_get, headers=headers, timeout=TIMEOUT_SEC)
        if res_get.status_code != 200: return False
        
        props_live = res_get.json()["properties"]
        l_inscritos = props_live.get("Inscritos", {}).get("rich_text", [])
        texto_inscritos_real = l_inscritos[0]["text"]["content"] if l_inscritos else ""
        
        lista_actual = [x.strip() for x in texto_inscritos_real.split(",")]
        if nombre_jugador in lista_actual: return True 
            
        nuevo_texto = f"{texto_inscritos_real}, {nombre_jugador}" if texto_inscritos_real else nombre_jugador
        
        url_patch = f"https://api.notion.com/v1/pages/{page_id}"
        payload = {"properties": {"Inscritos": {"rich_text": [{"text": {"content": nuevo_texto}}]}}}
        
        if requests.patch(url_patch, headers=headers, json=payload, timeout=TIMEOUT_SEC).status_code == 200:
            registrar_evento_sistema(nombre_jugador, "Inscripción Misión", f"ID: {page_id}", "Misión")
            st.cache_data.clear() 
            return True
        return False
    except Exception as e:
        print(f"Error inscripción: {e}")
        return False

# --- ⚡ HABILIDADES (MOVIDO A BACKEND PARA LIMPIEZA) ---
@st.cache_data(ttl=3600)
def cargar_habilidades(rol_jugador):
    """
    Carga habilidades desde el backend, con búsqueda inteligente de título.
    """
    if not rol_jugador: return []
    if not DB_HABILIDADES_ID: return []
    
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    payload = {
        "filter": {"property": "Rol", "select": {"equals": rol_jugador}}, 
        "sorts": [{"property": "Nivel Requerido", "direction": "ascending"}]
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
        habilidades = []
        if res.status_code == 200:
            for item in res.json()["results"]:
                props = item["properties"]
                try:
                    # BÚSQUEDA INTELIGENTE DEL TÍTULO
                    nombre = "Habilidad Sin Nombre"
                    for key, val in props.items():
                        if val['type'] == 'title':
                            content_list = val.get("title", [])
                            if content_list:
                                nombre = "".join([t.get("plain_text", "") for t in content_list])
                            break 

                    costo = 0
                    if "Costo AP" in props: costo = props.get("Costo AP", {}).get("number", 0)
                    elif "Costo" in props: costo = props.get("Costo", {}).get("number", 0)
                    
                    nivel_req = 1
                    if "Nivel Requerido" in props: 
                        nivel_req = props.get("Nivel Requerido", {}).get("number", 1)

                    desc_obj = props.get("Descripcion", {}).get("rich_text", [])
                    descripcion = desc_obj[0]["text"]["content"] if desc_obj else "Sin descripción"
                    
                    icon_url = None
                    if "Icono" in props:
                        files = props["Icono"].get("files", [])
                        if files: 
                            icon_url = files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
                        
                    habilidades.append({
                        "id": item["id"], 
                        "nombre": nombre, 
                        "costo": costo, 
                        "nivel_req": nivel_req, 
                        "desc": descripcion, # Nota: en app usabas 'desc' o 'descripcion'? Estandarizamos a 'desc'
                        "descripcion": descripcion, # Duplicamos para compatibilidad
                        "icon_url": icon_url
                    })
                except Exception as e: pass
        return habilidades
    except: return []

# --- 📩 SOLICITUDES ---
def enviar_solicitud(tipo, mensaje, detalles, usuario):
    if not DB_SOLICITUDES_ID: return False
    url = "https://api.notion.com/v1/pages"
    uni, ano = get_player_metadata()
    
    properties = {
        "Usuario": {"title": [{"text": {"content": str(usuario)}}]},
        "Remitente": {"title": [{"text": {"content": str(usuario)}}]},
        "Tipo": {"select": {"name": tipo}},
        "Mensaje": {"rich_text": [{"text": {"content": f"{mensaje}\n\nDetalles: {detalles}"}}]}, 
        "Status": {"select": {"name": "Pendiente"}}, 
        "Fecha de creación": {"date": {"start": get_chile_time_iso()}} 
    }
    if uni: properties["Universidad"] = {"select": {"name": uni}}
    if ano: properties["Año"] = {"select": {"name": ano}}

    payload = {"parent": {"database_id": DB_SOLICITUDES_ID}, "properties": properties}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
        return res.status_code == 200
    except: return False

# --- 🛍️ MERCADO ---
def procesar_compra_habilidad(skill_name, cost_ap, cost_mp, skill_id_notion):
    current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
    current_mp = st.session_state.jugador.get("MP", {}).get("number", 0)
    
    if current_ap < cost_ap or current_mp < cost_mp:
        return False, "Saldo insuficiente para solicitar."

    msg_solicitud = f"Solicitud de activación: {skill_name}"
    detalles_solicitud = f"Costo: {cost_ap} AP | {cost_mp} MP. (Esperando aprobación manual)."
    
    exito = enviar_solicitud("Compra Habilidad", msg_solicitud, detalles_solicitud, st.session_state.nombre)
    
    if exito:
        registrar_evento_sistema(st.session_state.nombre, "Solicitud Habilidad", f"{skill_name}", "Mercado")
        return True, "Solicitud enviada al Comando."
    else:
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
            if results:
                return results[0]["properties"].get("Activo", {}).get("checkbox", False)
        return False
    except: return False

def procesar_suministro(rarity_name, rewards):
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
        res = requests.patch(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
        
        if res.status_code == 200:
            detalle_txt = f"Farmeo {rarity_name}: AP: +{rewards['AP']} | MP: +{rewards['MP']} | VP: +{rewards['VP']}"
            registrar_evento_sistema(st.session_state.nombre, "Suministro Reclamado", detalle_txt, "Suministro")
            return True
        return False
    except: return False

# --- 🔐 CÓDIGOS DE CANJE (AHORA CON VALIDACIÓN) ---
def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline."
    
    # NUEVO: VALIDACIÓN PREVIA (Evita inyección y formatos raros)
    if not validar_codigo_seguro(codigo_input):
        return False, "❌ Formato de código inválido (use A-Z, 0-9)."

    url = f"https://api.notion.com/v1/databases/{DB_CODIGOS_ID}/query"
    payload = {
        "filter": {
            "and": [
                {"property": "Código", "title": {"equals": codigo_input.strip().upper()}},
                {"property": "Activo", "checkbox": {"equals": True}}
            ]
        }
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
        results = res.json().get("results", [])
        if not results: return False, "❌ Código inválido o expirado."
        
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
        }, timeout=TIMEOUT_SEC)
        
        if req_p.status_code == 200:
            new_list = f"{redeemed_text}, {st.session_state.nombre}" if redeemed_text else st.session_state.nombre
            requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={
                "properties": {
                    "Usos Actuales": {"number": current_uses + 1},
                    "Redimido Por": {"rich_text": [{"text": {"content": new_list}}]}
                }
            }, timeout=TIMEOUT_SEC)
            
            detalle_log = f"Código: {codigo_input} | +{rew_ap} AP, +{rew_mp} MP, +{rew_vp} VP"
            registrar_evento_sistema(st.session_state.nombre, "Canje Código", detalle_log, "Código")
            
            return True, f"¡Canjeado! +{rew_ap} AP"
        return False, "Error al actualizar perfil."
    except Exception as e: return False, str(e)

# --- 🔮 TRIVIA ---
def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    payload = {"filter": {"property": "Activa", "checkbox": {"equals": True}}, "page_size": 30}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT_SEC)
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
        requests.patch(url, headers=headers, json={"properties": {"AP": {"number": current_ap + reward_ap}}}, timeout=TIMEOUT_SEC)
    
    url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    requests.patch(url, headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": get_chile_time_iso()}}}}, timeout=TIMEOUT_SEC)
    
    res_text = "CORRECTO" if is_correct else "FALLO"
    registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"{res_text} (+{reward_ap if is_correct else 0})", "Trivia")
