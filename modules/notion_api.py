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
        return uni or "Desconocido", ano or "Desconocido"
    except: return "Desconocido", "Desconocido"

def registrar_evento_sistema(evento, detalle, tipo="Sistema"):
    """Registra en LOGS usando metadatos de sesión."""
    if not DB_LOGS_ID: return
    try:
        nombre = st.session_state.get("nombre", "Sistema")
        uni, ano = get_player_metadata()
        
        payload = {
            "parent": {"database_id": DB_LOGS_ID},
            "properties": {
                "Evento": {"title": [{"text": {"content": str(evento)}}]},
                "Jugador": {"rich_text": [{"text": {"content": str(nombre)}}]},
                "Tipo": {"select": {"name": str(tipo)}},
                "Detalle": {"rich_text": [{"text": {"content": str(detalle)}}]},
                "Universidad": {"select": {"name": str(uni)}},
                "Año": {"select": {"name": str(ano)}}
            }
        }
        requests.post("https://api.notion.com/v1/pages", headers=headers, json=payload, timeout=2)
    except: pass

def verificar_modo_mantenimiento():
    if not DB_CONFIG_ID: return False
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        res = requests.post(url, headers=headers, json={}, timeout=API_TIMEOUT)
        if res.status_code == 200:
            for r in res.json().get("results", []):
                k = get_notion_text(r["properties"], "Clave")
                if k == "MODO_MANTENIMIENTO":
                    return r["properties"]["Activo"]["checkbox"]
    except: pass
    return False

def cargar_datos_jugador(user):
    # (Esta función es usada por admin o validaciones extra, el login principal está en app.py)
    return None 

def cargar_misiones_activas():
    if not DB_MISIONES_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_MISIONES_ID}/query"
    payload = {
        "filter": {"property": "Estado", "select": {"equals": "Activa"}},
        "sorts": [{"property": "Fecha Lanzamiento", "direction": "ascending"}]
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        misiones = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                p = r["properties"]
                misiones.append({
                    "id": r["id"],
                    "nombre": get_notion_text(p, "Misión"),
                    "descripcion": get_notion_text(p, "Descripción"),
                    "narrativa": get_notion_text(p, "Narrativa"),
                    "tipo": get_notion_select(p, "Tipo"),
                    "recompensas_txt": get_notion_text(p, "Recompensas Texto"),
                    "f_lanzamiento": get_notion_date(p, "Fecha Lanzamiento"),
                    "f_apertura": get_notion_date(p, "Fecha Apertura"),
                    "f_cierre": get_notion_date(p, "Fecha Cierre"),
                    "inscritos": get_notion_text(p, "Inscritos") or "",
                    "target_unis": get_notion_multi_select(p, "Universidad Objetivo") or ["Todas"],
                    "password": get_notion_text(p, "Password Misión"),
                    "link": get_notion_url(p, "Link Misión"),
                    "advertencia": get_notion_text(p, "Advertencia")
                })
        return misiones
    except: return []

def inscribir_jugador_mision(page_id, inscritos_actuales, nombre_jugador, nombre_mision):
    lista = [x.strip() for x in inscritos_actuales.split(",") if x.strip()]
    if nombre_jugador in lista: return False
    lista.append(nombre_jugador)
    nueva_str = ", ".join(lista)
    
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"Inscritos": {"rich_text": [{"text": {"content": nueva_str}}]}}}
    
    try:
        requests.patch(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        registrar_evento_sistema(f"Inscripción: {nombre_mision}", "Jugador inscrito correctamente.", "Misión")
        return True
    except: return False

def enviar_solicitud(tipo, asunto, mensaje_texto, remitente):
    if not DB_SOLICITUDES_ID: return False
    url = "https://api.notion.com/v1/pages"
    
    uni, ano = get_player_metadata()
    
    full_msg = f"Asunto: {asunto}\n\n{mensaje_texto}"
    if "COMPRA" in tipo.upper() or "MERCADO" in tipo.upper(): full_msg = mensaje_texto 

    payload = {
        "parent": {"database_id": DB_SOLICITUDES_ID},
        "properties": {
            "Remitente": {"title": [{"text": {"content": remitente}}]},
            "Tipo": {"select": {"name": tipo}},
            "Mensaje": {"rich_text": [{"text": {"content": full_msg}}]},
            "Status": {"select": {"name": "Pendiente"}},
            "Universidad": {"select": {"name": str(uni)}},
            "Año": {"select": {"name": str(ano)}}
        }
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        return r.status_code == 200
    except: return False

# --- REEMPLAZAR ESTA FUNCIÓN EN modules/notion_api.py ---

def cargar_habilidades(rol_filtro):
    """
    Carga habilidades y filtra en Python para máxima compatibilidad.
    Maneja singular/plural automáticamente (ej: Visionarios vs Visionario).
    """
    if not DB_HABILIDADES_ID: return []
    
    # 1. Traemos TODAS las habilidades (sin filtrar en la API para evitar errores 400)
    url = f"https://api.notion.com/v1/databases/{DB_HABILIDADES_ID}/query"
    
    try:
        res = requests.post(url, headers=headers, json={}, timeout=API_TIMEOUT)
        skills = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                p = r["properties"]
                
                # --- LÓGICA DE FILTRADO INTELIGENTE ---
                roles_habilidad = []
                # Intentamos leer la propiedad "Rol" (Multi-select)
                try:
                    tags = get_notion_multi_select(p, "Rol")
                    if tags: roles_habilidad = tags
                except: pass
                
                # Criterios de coincidencia:
                # A. Tiene la etiqueta "Todos"
                # B. Tiene el rol exacto (Ej: "Visionarios")
                # C. Tiene el rol en singular (Ej: "Visionario")
                rol_singular = rol_filtro[:-1] if rol_filtro.endswith('s') else rol_filtro
                
                match = False
                if "Todos" in roles_habilidad: match = True
                elif rol_filtro in roles_habilidad: match = True
                elif rol_singular in roles_habilidad: match = True
                
                if not match: continue # Si no coincide, saltamos a la siguiente
                # --------------------------------------

                # Extraer datos
                cooldown = get_notion_number(p, "Cooldown")
                if cooldown is None: cooldown = 0

                skills.append({
                    "id": r["id"],
                    "nombre": get_notion_text(p, "Habilidad"),
                    "costo": get_notion_number(p, "Costo AP"),
                    "desc": get_notion_text(p, "Descripcion"),
                    "nivel_req": get_notion_number(p, "Nivel Requerido"),
                    "icon_url": get_notion_file_url(p, "Icono"),
                    "cooldown": cooldown
                })
                
            return sorted(skills, key=lambda x: x["costo"])
    except Exception as e:
        # Debug simple por si falla algo crítico
        print(f"Error cargando habilidades: {e}")
        return []
    return []

def procesar_compra_habilidad(nombre_hab, costo, nivel_req, id_hab):
    # Verificación de saldo local antes de llamar a API (doble check)
    if "jugador" not in st.session_state: return False, "No hay sesión."
    
    ap_actual = st.session_state.jugador.get("AP", {}).get("number", 0)
    if ap_actual < costo: return False, "Saldo insuficiente."
    
    # 1. Enviar Solicitud
    if enviar_solicitud("HABILIDAD", f"Compra: {nombre_hab}", f"Solicito activar: {nombre_hab}\nCosto: {costo} AP", st.session_state.nombre):
        # 2. Descontar AP localmente y en Notion
        nuevo_ap = ap_actual - costo
        pid = st.session_state.player_page_id
        
        try:
            url = f"https://api.notion.com/v1/pages/{pid}"
            payload = {"properties": {"AP": {"number": nuevo_ap}}}
            requests.patch(url, headers=headers, json=payload, timeout=API_TIMEOUT)
            
            # Actualizar estado local
            st.session_state.jugador["AP"]["number"] = nuevo_ap
            registrar_evento_sistema(f"Compra Habilidad: {nombre_hab}", f"Costo: {costo} AP", "Economía")
            return True, "Compra exitosa. Habilidad activada/solicitada."
        except: return False, "Error al descontar AP, pero solicitud enviada."
    else: return False, "Error de conexión."

def procesar_codigo_canje(codigo_input):
    if not DB_CODIGOS_ID: return False, "Sistema offline.", None
    
    # 1. Buscar código
    url = f"https://api.notion.com/v1/databases/{DB_CODIGOS_ID}/query"
    payload = {"filter": {"property": "Codigo", "title": {"equals": codigo_input}}}
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        if res.status_code != 200: return False, "Error buscando código.", None
        data = res.json()["results"]
        if not data: return False, "Código inválido o expirado.", None
        
        code_page = data[0]
        props = code_page["properties"]
        
        # Validar usos
        max_usos = get_notion_number(props, "Usos Maximos")
        usos_act = get_notion_number(props, "Usos Actuales")
        if max_usos > 0 and usos_act >= max_usos: return False, "Código agotado.", None
        
        # Validar si yo ya lo usé
        canjeados_por = get_notion_text(props, "Canjeado Por") or ""
        lista_canje = [x.strip() for x in canjeados_por.split(",") if x.strip()]
        if st.session_state.nombre in lista_canje: return False, "Ya usaste este código.", None
        
        # Validar expiración
        # (Implementación simple: si tiene fecha y ya pasó)
        
        # 2. Aplicar recompensas
        ap_premio = get_notion_number(props, "AP")
        mp_premio = get_notion_number(props, "MP")
        insignia = get_notion_select(props, "Insignia")
        
        pid = st.session_state.player_page_id
        p_props = st.session_state.jugador
        
        updates = {}
        if ap_premio: updates["AP"] = {"number": (p_props.get("AP", {}).get("number",0) + ap_premio)}
        if mp_premio: updates["MP"] = {"number": (p_props.get("MP", {}).get("number",0) + mp_premio)}
        
        if insignia:
            current_badges = p_props.get("Insignias", {}).get("multi_select", [])
            badge_names = [b["name"] for b in current_badges]
            if insignia not in badge_names:
                badge_names.append(insignia)
                updates["Insignias"] = {"multi_select": [{"name": n} for n in badge_names]}
        
        if updates:
            requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json={"properties": updates}, timeout=API_TIMEOUT)
            
            # 3. Actualizar Código (Sumar uso y agregar nombre)
            lista_canje.append(st.session_state.nombre)
            new_canje_str = ", ".join(lista_canje)
            up_code = {
                "Usos Actuales": {"number": usos_act + 1},
                "Canjeado Por": {"rich_text": [{"text": {"content": new_canje_str}}]}
            }
            requests.patch(f"https://api.notion.com/v1/pages/{code_page['id']}", headers=headers, json={"properties": up_code}, timeout=API_TIMEOUT)
            
            registrar_evento_sistema(f"Canje Código: {codigo_input}", f"Recompensa: {ap_premio} AP, {mp_premio} MP", "Sistema")
            return True, "Código canjeado.", {"AP": ap_premio, "MP": mp_premio, "Insignia": insignia}
            
        return False, "El código no otorgaba beneficios.", None

    except: return False, "Error técnico.", None

def cargar_pregunta_aleatoria():
    if not DB_TRIVIA_ID: return None
    url = f"https://api.notion.com/v1/databases/{DB_TRIVIA_ID}/query"
    try:
        # Filtro opcional: Solo activas
        res = requests.post(url, headers=headers, json={}, timeout=API_TIMEOUT)
        if res.status_code == 200:
            preguntas = []
            for r in res.json()["results"]:
                p = r["properties"]
                preguntas.append({
                    "ref_id": r["id"],
                    "pregunta": get_notion_text(p, "Pregunta"),
                    "opcion_a": get_notion_text(p, "Opcion A"),
                    "opcion_b": get_notion_text(p, "Opcion B"),
                    "opcion_c": get_notion_text(p, "Opcion C"),
                    "correcta": get_notion_select(p, "Correcta"), # "A", "B" o "C"
                    "recompensa": get_notion_number(p, "Recompensa AP"),
                    "exp_correcta": get_notion_text(p, "Explicacion Correcta"),
                    "exp_incorrecta": get_notion_text(p, "Explicacion Incorrecta"),
                    "public_id": get_notion_unique_id(p, "ID")
                })
            if preguntas: return random.choice(preguntas)
    except: pass
    return None

def procesar_recalibracion(recompensa, es_correcta, pregunta_id, public_id_str):
    nombre = st.session_state.nombre
    res = "CORRECTO" if es_correcta else "INCORRECTO"
    registrar_evento_sistema(f"Trivia: {public_id_str}", f"Resultado: {res}", "Juego")
    
    if es_correcta and recompensa > 0:
        pid = st.session_state.player_page_id
        ap_act = st.session_state.jugador.get("AP", {}).get("number", 0)
        nuevo = ap_act + recompensa
        try:
            requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json={"properties": {"AP": {"number": nuevo}}}, timeout=API_TIMEOUT)
            st.session_state.jugador["AP"]["number"] = nuevo
        except: pass

def cargar_estado_suministros():
    if not DB_CONFIG_ID: return False, "Todas"
    url = f"https://api.notion.com/v1/databases/{DB_CONFIG_ID}/query"
    try:
        res = requests.post(url, headers=headers, json={}, timeout=API_TIMEOUT)
        if res.status_code == 200:
            for r in res.json()["results"]:
                k = get_notion_text(r["properties"], "Clave")
                if k == "DROP_SUMINISTROS":
                    act = r["properties"]["Activo"]["checkbox"]
                    filtro_list = r["properties"].get("Filtro", {}).get("rich_text", [])
                    filtro = filtro_list[0]["text"]["content"] if filtro_list else "Todas"
                    return act, filtro
    except: pass
    return False, "Todas"

def procesar_suministro(tier, rewards):
    pid = st.session_state.player_page_id
    ap_gain = rewards.get("AP", 0)
    
    try:
        ap_act = st.session_state.jugador.get("AP", {}).get("number", 0)
        requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json={"properties": {"AP": {"number": ap_act + ap_gain}}}, timeout=API_TIMEOUT)
        st.session_state.jugador["AP"]["number"] = ap_act + ap_gain
        registrar_evento_sistema(f"Suministro {tier}", f"+{ap_gain} AP", "Loot")
        return True
    except: return False

def cargar_anuncios():
    if not DB_ANUNCIOS_ID: return []
    url = f"https://api.notion.com/v1/databases/{DB_ANUNCIOS_ID}/query"
    payload = {"filter": {"property": "Activo", "checkbox": {"equals": True}}, "sorts": [{"property": "Fecha", "direction": "descending"}]}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        items = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                p = r["properties"]
                items.append({
                    "titulo": get_notion_text(p, "Titulo"),
                    "contenido": get_notion_text(p, "Contenido"),
                    "fecha": get_notion_date(p, "Fecha"),
                    "universidad": get_notion_multi_select(p, "Universidad") or ["Todas"],
                    "año": get_notion_multi_select(p, "Año") or ["Todas"]
                })
        return items
    except: return []

def procesar_compra_mercado(item_nombre, costo, es_dinero_real):
    if not es_dinero_real:
        # Descuento de AP
        ap_act = st.session_state.jugador.get("AP", {}).get("number", 0)
        if ap_act < costo: return False, "Saldo insuficiente."
        
        nuevo_ap = ap_act - costo
        pid = st.session_state.player_page_id
        try:
            requests.patch(f"https://api.notion.com/v1/pages/{pid}", headers=headers, json={"properties": {"AP": {"number": nuevo_ap}}}, timeout=API_TIMEOUT)
            st.session_state.jugador["AP"]["number"] = nuevo_ap
        except: return False, "Error técnico descontando."
    
    # Enviar log de solicitud
    msg = f"Compra Mercado: {item_nombre} (Costo: {costo} {'CLP' if es_dinero_real else 'AP'})"
    enviar_solicitud("MERCADO", f"Compra: {item_nombre}", msg, st.session_state.nombre)
    return True, "Solicitud de compra enviada."

def obtener_miembros_escuadron(nombre_escuadron, uni, ano):
    if not nombre_escuadron: return []
    url = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
    payload = {"filter": {"and": [{"property": "Nombre Escuadrón", "rich_text": {"equals": nombre_escuadron}}, {"property": "Universidad", "select": {"equals": uni}}, {"property": "Año", "select": {"equals": ano}}]}}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        miembros = []
        if res.status_code == 200:
            for r in res.json()["results"]:
                try:
                    name = r["properties"]["Jugador"]["title"][0]["text"]["content"]
                    miembros.append(name)
                except: pass
        return miembros
    except: return []

def aprobar_solicitud_habilidad(page_id, remitente, mensaje_original):
    # Usado por ADMIN.PY
    # Extraer costo del mensaje si está
    costo = 0
    try:
        match = re.search(r'Costo:\s*(\d+)', mensaje_original)
        if match: costo = int(match.group(1))
    except: pass
    
    # Cerrar solicitud
    url_req = f"https://api.notion.com/v1/pages/{page_id}"
    payload_req = {
        "properties": {
            "Status": {"select": {"name": "Aprobado"}},
            "Procesado": {"checkbox": True},
            "Observaciones": {"rich_text": [{"text": {"content": "Habilidad desplegada."}}]},
            "Fecha respuesta": {"date": {"start": datetime.now(pytz.timezone('America/Santiago')).isoformat()}}
        }
    }
    
    try:
        requests.patch(url_req, headers=headers, json=payload_req, timeout=API_TIMEOUT)
        
        # Registrar evento (Opcional, ya que admin lo hace)
        return True, "Solicitud aprobada."
    except: return False, "Error cerrando solicitud."

def cargar_todas_misiones_admin(uni_filtro):
    # Función espejo para admin
    return cargar_misiones_activas() # Simplificado, reusamos la lógica

def aprobar_solicitud_mercado(page_id, remitente, costo_a_cobrar, obs):
    # ADMIN: Cobra AP si es necesario y cierra
    if costo_a_cobrar > 0:
        # Buscar usuario y descontar
        url_u = f"https://api.notion.com/v1/databases/{DB_JUGADORES_ID}/query"
        pay_u = {"filter": {"property": "Jugador", "title": {"equals": remitente}}}
        try:
            res = requests.post(url_u, headers=headers, json=pay_u)
            if res.status_code == 200 and res.json()["results"]:
                u_page = res.json()["results"][0]
                u_id = u_page["id"]
                ap_curr = u_page["properties"].get("AP", {}).get("number", 0)
                new_ap = max(0, ap_curr - costo_a_cobrar)
                requests.patch(f"https://api.notion.com/v1/pages/{u_id}", headers=headers, json={"properties": {"AP": {"number": new_ap}}})
        except: return False, "Error cobrando al usuario."

    # Cerrar solicitud
    url_req = f"https://api.notion.com/v1/pages/{page_id}"
    payload_req = {
        "properties": {
            "Status": {"select": {"name": "Entregado"}}, # Mercado usa "Entregado"
            "Procesado": {"checkbox": True},
            "Observaciones": {"rich_text": [{"text": {"content": obs}}]},
            "Fecha respuesta": {"date": {"start": datetime.now(pytz.timezone('America/Santiago')).isoformat()}}
        }
    }
    try:
        requests.patch(url_req, headers=headers, json=payload_req, timeout=API_TIMEOUT)
        
        # SILENCIADO: registrar_evento_sistema(...) <- ELIMINADO
        
        return True, "✅ Compra procesada y cobrada."
    except: return False, "Error cerrando solicitud en Notion."

def registrar_setup_inicial(page_id, nuevo_nick, avatar_url, nueva_password):
    """
    Finaliza el proceso de iniciación del recluta.
    Actualiza: Nombre (Nick), Clave (Password), Avatar y marca Setup_Completo.
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"
    
    payload = {
        "properties": {
            "Jugador": {"title": [{"text": {"content": nuevo_nick}}]}, 
            "Clave": {"rich_text": [{"text": {"content": nueva_password}}]}, # <--- CORREGIDO: "Clave" en lugar de "Password"
            "Setup_Completo": {"checkbox": True}, 
            "Avatar": {
                "files": [
                    {
                        "name": "avatar_genesis.png",
                        "type": "external",
                        "external": {"url": avatar_url}
                    }
                ]
            }
        }
    }
    
    try:
        res = requests.patch(url, headers=headers, json=payload, timeout=API_TIMEOUT)
        if res.status_code == 200:
            return True, "Identidad forjada correctamente."
        else:
            return False, f"Error en la forja: {res.text}"
    except Exception as e:
        return False, f"Error de conexión: {e}"

# --- NUEVA FUNCIÓN FASE 3: VERIFICADOR DE COOLDOWN ---
def verificar_cooldown_habilidad(jugador_nombre, nombre_habilidad, dias_cooldown):
    """
    Verifica si una habilidad está en enfriamiento.
    Retorna: (False, 0) si está lista.
    Retorna: (True, dias_restantes) si está bloqueada.
    """
    if dias_cooldown <= 0: return False, 0
    
    # Buscamos la última vez que se pidió esta habilidad
    url = f"https://api.notion.com/v1/databases/{DB_SOLICITUDES_ID}/query"
    
    # Filtro Táctico:
    payload = {
        "filter": {
            "and": [
                {"property": "Remitente", "title": {"equals": jugador_nombre}},
                {"property": "Tipo", "select": {"equals": "Habilidad"}},
                {"property": "Status", "select": {"does_not_equal": "Rechazado"}}, 
                {"property": "Mensaje", "rich_text": {"contains": nombre_habilidad}}
            ]
        },
        "sorts": [{"timestamp": "created_time", "direction": "descending"}], # La más reciente primero
        "page_size": 1 # Solo nos importa la última
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=3)
        if res.status_code == 200:
            results = res.json().get("results", [])
            if not results: return False, 0 # Nunca usada
            
            # Calcular tiempo
            ultima_fecha_str = results[0]["created_time"] # ISO 8601 UTC
            ultima_fecha = datetime.fromisoformat(ultima_fecha_str.replace('Z', '+00:00'))
            
            ahora = datetime.now(pytz.utc)
            diferencia = ahora - ultima_fecha
            
            if diferencia.days < dias_cooldown:
                restante = dias_cooldown - diferencia.days
                return True, restante
            
    except: pass # Si falla API, asumimos desbloqueada por seguridad
    
    return False, 0
