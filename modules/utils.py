import streamlit as st
import json
import os
import random
import re
from datetime import datetime
import pytz

# --- FUNCIONES DE CARGA DE ASSETS ---
@st.cache_data
def cargar_lottie_seguro(path):
    if not path or not os.path.exists(path): return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except: return None

def cargar_imagen_circular(image_path, size=(150, 150)):
    # Placeholder si necesitas procesamiento de imágenes
    return image_path

# --- GENERADOR DE LOOT (LÓGICA) ---
def generar_loot():
    rand_val = random.random()
    if rand_val < 0.05:
        tier = "Legendario"
        stats = {"AP": random.randint(100, 200), "MP": random.randint(50, 100), "VP": random.randint(5, 10)}
        icon = "👑"
    elif rand_val < 0.20:
        tier = "Épico"
        stats = {"AP": random.randint(50, 90), "MP": random.randint(20, 40), "VP": random.randint(2, 5)}
        icon = "💠"
    elif rand_val < 0.50:
        tier = "Raro"
        stats = {"AP": random.randint(20, 40), "MP": random.randint(10, 20), "VP": 1}
        icon = "💼"
    else:
        tier = "Común"
        stats = {"AP": random.randint(5, 15), "MP": random.randint(5, 10), "VP": 0}
        icon = "📦"
    return tier, stats, icon

# --- HELPERS DE NOTION (YA EXISTENTES) ---
def get_notion_text(props, name, default=""):
    try:
        prop = props.get(name, {})
        content_list = prop.get("title", []) or prop.get("rich_text", [])
        if content_list:
            return "".join([t.get("plain_text", "") for t in content_list])
        return default
    except: return default

def get_notion_number(props, name, default=0):
    try:
        val = props.get(name, {}).get("number")
        return val if val is not None else default
    except: return default

def get_notion_select(props, name, default=None):
    try:
        val = props.get(name, {}).get("select")
        return val.get("name", default) if val else default
    except: return default

def get_notion_multi_select(props, name, default_list=None):
    if default_list is None: default_list = []
    try:
        val_list = props.get(name, {}).get("multi_select", [])
        return [item.get("name") for item in val_list] if val_list else default_list
    except: return default_list

def get_notion_date(props, name, default=None):
    try:
        val = props.get(name, {}).get("date")
        return val.get("start", default) if val else default
    except: return default

def get_notion_url(props, name, default="#"):
    try:
        return props.get(name, {}).get("url", default)
    except: return default

def get_notion_checkbox(props, name, default=False):
    try:
        return props.get(name, {}).get("checkbox", default)
    except: return default

def get_notion_file_url(props, name, default=None):
    try:
        files = props.get(name, {}).get("files", [])
        if files:
            return files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
        return default
    except: return default

def validar_codigo_seguro(codigo):
    if not codigo: return False
    codigo = codigo.strip().upper()
    return bool(re.match(r'^[A-Z0-9-]+$', codigo))

# --- 🔥 NUEVO: HELPER DE FECHAS DEFINITIVO ---
def parsear_fecha_chile(fecha_str, formato_salida="%d/%m/%Y %H:%M"):
    """
    Convierte cualquier fecha de Notion (ISO o YYYY-MM-DD) a hora de Chile formateada.
    """
    if not fecha_str: return "Fecha desc."
    
    chile_tz = pytz.timezone('America/Santiago')
    try:
        if "T" in fecha_str: # Formato ISO con hora
            # Notion entrega UTC (Z). Reemplazamos Z y convertimos.
            dt_utc = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            dt_chile = dt_utc.astimezone(chile_tz)
            return dt_chile.strftime(formato_salida)
        else: # Solo fecha YYYY-MM-DD
            dt_naive = datetime.strptime(fecha_str, "%Y-%m-%d")
            # Asumimos que la fecha es local o medianoche
            return dt_naive.strftime("%d/%m/%Y")
    except Exception:
        return fecha_str # Si falla, devuelve el string original

def get_notion_unique_id(props, name, default=None):
    """
    Extrae el número de una propiedad 'unique_id' (ID autoincremental de Notion).
    Retorna solo el número (int).
    """
    try:
        # La estructura es: prop -> unique_id -> number
        val = props.get(name, {}).get("unique_id", {}).get("number")
        return val if val is not None else default
    except:
        return default
