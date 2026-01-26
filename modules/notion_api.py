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
        # BUSCAMOS "MODO_MANTENIMIENTO" en la propiedad "Nombre" (Title)
        payload = {
            "filter": {
                "property": "Nombre", 
                "title": {"equals": "MODO_MANTENIMIENTO"}
            }
        }
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                # Si encuentra la fila, mira si el checkbox "Activo" está marcado
                val = results[0]["properties"].get("Activo", {}).get("checkbox", False)
                print(f"🔧 MANTENIMIENTO: Encontrado = {val}") # DEBUG
                return val
            else:
                print("🔧 MANTENIMIENTO: No se encontró la fila 'MODO_MANTENIMIENTO'") # DEBUG
        else:
            print(f"⚠️ ERROR NOTION MANTENIMIENTO: {res.status_code} - {res.text}") # DEBUG
        return False
    except Exception as e: 
        print(f"⚠️ EXCEPCION MANTENIMIENTO: {e}")
        return False

def registrar_evento_sistema(usuario, accion, detalles, tipo="INFO"):
    if not DB_LOGS_ID: 
        print("⚠️ LOGS: No hay ID de base de datos")
        return
    
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"database_id": DB_LOGS_ID},
        "properties": {
            "Usuario": {"title": [{"text": {"content": str(usuario)}}]},
            "Acción": {"rich_text": [{"text": {"content": str(accion)}}]},
            "Detalles": {"rich_text": [{"text": {"content": str(detalles)}}]},
            "Tipo": {"select": {"name": tipo}},
            "Fecha": {"date": {"start": get_chile_time_iso()}}
        }
    }
    try: 
        res = requests.post(url, headers=headers, json=payload, timeout=2)
        if res.status_code != 200:
            print(f"⚠️ ERROR LOGS: {res.text}") # DEBUG CRÍTICO
    except Exception as e:
        print(f"⚠️ EXCEPCION LOGS: {e}")

# --- 👤 JUGADORES ---
@st.cache_data(ttl=10, show_spinner="Sincronizando perfil...") # TTL bajo para pruebas
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
            if results: return results[0]
        else:
            print(f"⚠️ ERROR LOGIN: {response.text}")
        return None
    except: return None

# --- 📢 ANUNCIOS ---
@st.cache_data(ttl=60)
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
                try:
                    props = r["properties"]
                    # Extracción defensiva (si falta algo, no rompe todo)
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
                except Exception as e:
                    print(f"⚠️ ERROR PARSING ANUNCIO: {e}")
                    continue
        return anuncios
    except: return []

# --- 🚀 MISIONES (CORREGIDO) ---
@st.cache_data(ttl=60)
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
                try: # Try por CADA misión, así si una falla, las otras cargan
                    props = p["properties"]
                    
                    def get_text(prop_name):
                        l = props.get(prop_name, {}).get("rich_text", [])
                        return l[0]["text"]["content"] if l else ""
                    
                    def get_title(prop_name):
                        l = props.get(prop_name, {}).get("title", [])
                        return l[0]["text"]["content"] if l else "Sin Título"

                    # Parseo seguro de fechas
                    f_apertura = props.get("Fecha Apertura", {}).get("date", {}).get("start")
                    f_cierre = props.get("Fecha Cierre", {}).get("date", {}).get("start")
                    
                    misiones.append({
                        "id": p["id"],
                        "nombre": get_title("Misión"),
                        "descripcion": get_text("Descripción"),
                        "tipo": props.get("Tipo", {}).get("select", {}).get("name", "Misión"),
                        "f_apertura": f_apertura,
                        "f_cierre": f_cierre,
                        "inscritos": get_text("Inscritos"),
                        "target_unis": [x["name"] for x in props.get("Universidad Objetivo", {}).get("multi_select", [])],
                        "password": get_text("Password"),
                        "link": props.get("Link", {}).get("url", "#")
                    })
                except Exception as item_error:
                    print(f"⚠️ ERROR EN UNA MISIÓN: {item_error}")
                    continue
        else:
            print(f"⚠️ ERROR QUERY MISIONES: {response.text}")
        return misiones
    except Exception as e: 
        print(f"⚠️ ERROR GENERAL MISIONES: {e}")
        return []

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
    
    # INTENTO 1: Usando "Usuario" como Title (Estándar app 5)
    payload = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Usuario": {"title": [{"text": {"content": str(usuario)}}]},
            "Tipo": {"select": {"name": tipo}},
            "Mensaje": {"rich_text": [{"text": {"content": mensaje}}]},
            "Detalles": {"rich_text": [{"text": {"content": detalles}}]},
            "Estado": {"status": {"name": "Pendiente"}},
            "Fecha": {"date": {"start": get_chile_time_iso()}}
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code != 200:
            print(f"❌ ERROR SOLICITUD NOTION: {res.text}") 
        return res.status_code == 200
    except Exception as e:
        print(f"❌ EXCEPCION SOLICITUD: {e}")
        return False

# --- 🛍️ MERCADO DE HABILIDADES ---
def procesar_compra_habilidad(skill_name, cost_ap, cost_mp, skill_id_notion):
    current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
    current_mp = st.session_state.jugador.get("MP", {}).get("number", 0)
    
    if current_ap < cost_ap or current_mp < cost_mp:
        return False, "Saldo insuficiente."

    new_ap = current_ap - cost_ap
    new_mp = current_mp - cost_mp
    
    # OBTENCIÓN ROBUSTA DE HABILIDADES
    current_skills = st.session_state.jugador.get("Habilidades", {}).get("relation", [])
    current_ids = [k["id"] for k in current_skills]
    
    if skill_id_notion in current_ids:
        return False, "Ya posees esta habilidad."
        
    current_ids.append(skill_id_notion)

    url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    
    # Payload estricto para Relations
    payload = {
        "properties": {
            "AP": {"number": new_ap},
            "MP": {"number": new_mp},
            # 🛑 CRÍTICO: ¿La columna se llama 'Habilidades' en la DB Jugadores?
            "Habilidades": {"relation": [{"id": x} for x in current_ids]} 
        }
    }
    
    try:
        res = requests.patch(url, headers=headers, json=payload)
        if res.status_code == 200:
            registrar_evento_sistema(st.session_state.nombre, "Compra Habilidad", f"Skill: {skill_name}")
            return True, f"¡{skill_name} adquirida!"
        else:
            print(f"❌ ERROR COMPRA NOTION: {res.text}") # ESTO NOS DIRÁ QUÉ PASA
            return False, "Error de enlace con el servidor."
    except Exception as e:
        return False, f"Error técnico: {str(e)}"

# --- 📦 SUMINISTROS (CORREGIDO) ---
def cargar_estado_suministros():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        # Busca "DROP_SUMINISTROS" en columna "Nombre"
        payload = {
            "filter": {
                "property": "Nombre", 
                "title": {"equals": "DROP_SUMINISTROS"}
            }
        }
        res = requests.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if results:
                val = results[0]["properties"].get("Activo", {}).get("checkbox", False)
                print(f"📦 SUMINISTROS: {val}") # Debug
                return val
            else:
                print("📦 SUMINISTROS: No se encontró la fila 'DROP_SUMINISTROS'")
        return False
    except: return False

def procesar_suministro(rewards):
    try:
        # Cálculos de saldos
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
        else:
            print(f"❌ ERROR COBRO SUMINISTRO: {res.text}")
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
        
        # Validación
        redeemed_text = ""
        if props.get("Redimido Por", {}).get("rich_text"):
            redeemed_text = props["Redimido Por"]["rich_text"][0]["text"]["content"]
            
        if st.session_state.nombre in [x.strip() for x in redeemed_text.split(",")]:
            return False, "⚠️ Ya canjeaste este código."

        # Recompensas
        rew_ap = props.get("Valor AP", {}).get("number", 0)
        rew_mp = props.get("Valor MP", {}).get("number", 0)
        rew_vp = props.get("Valor VP", {}).get("number", 0)
        
        # Aplicar al jugador
        player = st.session_state.jugador
        new_ap = player.get("AP", {}).get("number", 0) + rew_ap
        new_mp = player.get("MP", {}).get("number", 0) + rew_mp
        new_vp = min(100, player.get("VP", {}).get("number", 0) + rew_vp)
        
        url_p = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        req_p = requests.patch(url_p, headers=headers, json={
            "properties": {"AP": {"number": new_ap}, "MP": {"number": new_mp}, "VP": {"number": new_vp}}
        })
        
        if req_p.status_code == 200:
            # Actualizar código
            new_list = f"{redeemed_text}, {st.session_state.nombre}" if redeemed_text else st.session_state.nombre
            requests.patch(f"https://api.notion.com/v1/pages/{page_id}", headers=headers, json={
                "properties": {
                    "Usos Actuales": {"number": props.get("Usos Actuales", {}).get("number", 0) + 1},
                    "Redimido Por": {"rich_text": [{"text": {"content": new_list}}]}
                }
            })
            # LOG
            registrar_evento_sistema(st.session_state.nombre, "Canje Código", f"Code: {codigo_input}")
            return True, f"¡Canjeado! +{rew_ap} AP"
        else:
            print(f"❌ ERROR APLICAR CÓDIGO A JUGADOR: {req_p.text}")
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
    except Exception as e:
        print(f"⚠️ ERROR TRIVIA: {e}")
        return None

def procesar_recalibracion(reward_ap, is_correct, question_id):
    if is_correct and reward_ap > 0:
        current_ap = st.session_state.jugador.get("AP", {}).get("number", 0)
        url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
        requests.patch(url, headers=headers, json={"properties": {"AP": {"number": current_ap + reward_ap}}})
    
    url = f"https://api.notion.com/v1/pages/{st.session_state.player_page_id}"
    requests.patch(url, headers=headers, json={"properties": {"Ultima Recalibracion": {"date": {"start": get_chile_time_iso()}}}})
    
    res_text = "CORRECTO" if is_correct else "FALLO"
    registrar_evento_sistema(st.session_state.nombre, "Trivia Oráculo", f"{res_text} (+{reward_ap if is_correct else 0})")
