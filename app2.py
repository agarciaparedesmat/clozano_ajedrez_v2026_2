
import streamlit as st
from lib.tournament import load_config, format_with_cfg
from lib.ui import inject_base_style, hero_portada, sidebar_title  # ← añade sidebar_title

st.set_page_config(page_title="Ajedrez en los recreos", page_icon="♟️", layout="wide")


# ← NUEVO: título en la barra lateral

inject_base_style()  # ← NUEVO: aplica el bg_color de config.json en la raíz
sidebar_title(extras=True)  

cfg = load_config()

titulo     = cfg.get("titulo", "Ajedrez en los recreos")
st.title(titulo)

subtitulo  = cfg.get("subtitulo", "Torneo de Ajedrez. Emparejamientos y clasificación")
st.caption(subtitulo)

nivel     = cfg.get("nivel", "Todos")
st.title(nivel)  # <- si no quieres duplicar títulos, quita esta línea

anio       = cfg.get("anio", "actual")
if anio:
    st.subheader(f"Curso {anio}")

version  = cfg.get("version", "")
st.caption(version)



# Ruta de la imagen en tu sistema
#ruta_imagen = "portada.png"
# Mostrar la imagen
#st.image(ruta_imagen, caption="Juega al Ajedrez en los recreos")

#st.info("Usa el menú lateral: Portada, Rondas, Clasificación y Admin.")
