import streamlit as st
import json
import os
import random
from PIL import Image, ImageDraw, ImageOps

# --- CARGADOR DE ANIMACIONES (SEGURA) ---
# Esta es la versión corregida que usa json.load
def cargar_lottie_seguro(filepath):
    if not os.path.exists(filepath): return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except: return None

# --- PROCESAMIENTO DE IMÁGENES CIRCULARES ---
def cargar_imagen_circular(ruta_local, size=(150, 150)):
    if not os.path.exists(ruta_local): return None
    try:
        img = Image.open(ruta_local).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        
        # Crear máscara circular
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0) + size, fill=255)
        
        # Aplicar máscara
        output = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
        output.putalpha(mask)
        return output
    except: return None

# --- GENERADOR DE LOOT (SUMINISTROS) ---
def generar_loot():
    roll = random.random()
    if roll < 0.05: # 5% Legendario
        # AHORA RETORNA 3 COSAS: Nombre, Stats, Icono
        return "Legendario", {"AP": 150, "MP": 50, "VP": 5}, "👑"
    elif roll < 0.20: # 15% Épico
        return "Épico", {"AP": 80, "MP": 20, "VP": 2}, "💠"
    elif roll < 0.50: # 30% Raro
        return "Raro", {"AP": 40, "MP": 10, "VP": 0}, "💼"
    else: # 50% Común
        return "Común", {"AP": 20, "MP": 5, "VP": 0}, "📦"
# --- 🛠️ HELPER FUNCTIONS (HERRAMIENTAS MAESTRAS DE NOTION) ---
import re

def get_notion_text(props, name, default=""):
    """Extrae texto plano de propiedades 'title' o 'rich_text'."""
    try:
        prop = props.get(name, {})
        # Soporta tanto 'title' como 'rich_text'
        content_list = prop.get("title", []) or prop.get("rich_text", [])
        if content_list:
            return "".join([t.get("plain_text", "") for t in content_list])
        return default
    except: return default

def get_notion_number(props, name, default=0):
    """Extrae números de propiedades 'number'."""
    try:
        val = props.get(name, {}).get("number")
        return val if val is not None else default
    except: return default

def get_notion_select(props, name, default=None):
    """Extrae el nombre de una opción 'select'."""
    try:
        val = props.get(name, {}).get("select")
        return val.get("name", default) if val else default
    except: return default

def get_notion_multi_select(props, name, default_list=None):
    """Extrae una lista de nombres de 'multi_select'."""
    if default_list is None: default_list = []
    try:
        val_list = props.get(name, {}).get("multi_select", [])
        return [item.get("name") for item in val_list] if val_list else default_list
    except: return default_list

def get_notion_date(props, name, default=None):
    """Extrae la fecha de inicio de una propiedad 'date'."""
    try:
        val = props.get(name, {}).get("date")
        return val.get("start", default) if val else default
    except: return default

def get_notion_url(props, name, default="#"):
    """Extrae URL de propiedades 'url'."""
    try:
        return props.get(name, {}).get("url", default)
    except: return default

def get_notion_checkbox(props, name, default=False):
    """Extrae valor booleano de 'checkbox'."""
    try:
        return props.get(name, {}).get("checkbox", default)
    except: return default

def get_notion_file_url(props, name, default=None):
    """Extrae la URL del primer archivo en propiedades 'files'."""
    try:
        files = props.get(name, {}).get("files", [])
        if files:
            # Notion usa 'file' para internos y 'external' para externos
            return files[0].get("file", {}).get("url") or files[0].get("external", {}).get("url")
        return default
    except: return default

def validar_codigo_seguro(codigo):
    """Valida formato seguro (A-Z, 0-9, -)."""
    if not codigo: return False
    codigo = codigo.strip().upper()
    return bool(re.match(r'^[A-Z0-9-]+$', codigo))
