
import streamlit as st
from lib.tournament import load_config

st.set_page_config(page_title="Torneo Suizo Escolar v7 Baseline", page_icon="♟️", layout="wide")
cfg = load_config()
st.title(cfg.get("titulo","Torneo Suizo — IES"))
st.caption(cfg.get("subtitulo",""))
st.info("Usa el menú lateral (Pages): Portada, Rondas, Clasificación y Admin.")
