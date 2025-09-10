
import streamlit as st
from lib.tournament import load_config
from lib.ui import hero_portada, inject_base_style

st.set_page_config(page_title="Ajedrez en los recreos", page_icon="♟️", layout="wide")

cfg = load_config()

titulo     = cfg.get("titulo", "Ajedrez en los recreos")
st.title(titulo)

subtitulo  = cfg.get("subtitulo", "Torneo de Ajedrez. Emparejamientos y clasificación")
st.caption(subtitulo)

nivel     = cfg.get("nivel", "Todos")
st.title(nivel)

# si quieres mostrar el curso debajo del título principal:
anio       = cfg.get("anio", "actual")

if anio:
    st.subheader(f"Curso {anio}")

# texto auxiliar

version  = cfg.get("version", "")
st.caption(version)

# Ruta de la imagen en tu sistema
#ruta_imagen = "portada.png"
# Mostrar la imagen
#st.image(ruta_imagen, caption="Juega al Ajedrez en los recreos")

#st.info("Usa el menú lateral: Portada, Rondas, Clasificación y Admin.")