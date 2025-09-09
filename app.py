
import streamlit as st
from lib.tournament import load_config

st.set_page_config(page_title="Torneo de Ajedrez IESCL", page_icon="♟️", layout="wide")
cfg = load_config()
st.title(cfg.get("titulo","Torneo de Ajedrez — IESCL"))
st.title(cfg.get("titulo","Curso 2025-2026"))
st.caption(cfg.get("subtitulo","Versión 9/Sept/2025"))
st.info("Usa el menú lateral: Portada, Rondas, Clasificación y Admin.")
