
import streamlit as st
from lib.tournament import load_config

st.set_page_config(page_title="Ajedrez en los recreos — IESCL", page_icon="♟️", layout="wide")

cfg = load_config()
titulo     = cfg.get("titulo", "Ajedrez en los recreos — IESCL")
anio       = cfg.get("anio", "")
subtitulo  = cfg.get("subtitulo", "Versión 9/Sept/2025")

st.title(titulo)

# si quieres mostrar el curso debajo del título principal:
if anio:
    st.subheader(f"Curso {anio}")

# y luego el subtítulo como texto auxiliar
st.caption(subtitulo)


# Ruta de la imagen en tu sistema
#ruta_imagen = "portada.png"
# Mostrar la imagen
#st.image(ruta_imagen, caption="Juega al Ajedrez en los recreos")

#st.info("Usa el menú lateral: Portada, Rondas, Clasificación y Admin.")