
import streamlit as st
from lib.tournament import load_config

st.set_page_config(page_title="Ajedrez en los recreos — IESCL", page_icon="♟️", layout="wide")
cfg = load_config()
st.title(cfg.get("titulo","Ajedrez en los recreos — IESCL"))
st.title(cfg.get("titulo","Curso 2025-2026"))
st.caption(cfg.get("subtitulo","Versión 9/Sept/2025"))

# Ruta de la imagen en tu sistema
#ruta_imagen = "portada.png"
# Mostrar la imagen
#st.image(ruta_imagen, caption="Juega al Ajedrez en los recreos")

#st.info("Usa el menú lateral: Portada, Rondas, Clasificación y Admin.")
