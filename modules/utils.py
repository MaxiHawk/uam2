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
        return "Legendario", {"AP": 150, "MP": 50, "VP": 5}, "👑"
    elif roll < 0.20: # 15% Épico
        return "Épico", {"AP": 80, "MP": 20, "VP": 2}, "💠"
    elif roll < 0.50: # 30% Raro
        return "Raro", {"AP": 40, "MP": 10, "VP": 0}, "💼"
    else: # 50% Común
        return "Común", {"AP": 20, "MP": 5, "VP": 0}, "📦"
