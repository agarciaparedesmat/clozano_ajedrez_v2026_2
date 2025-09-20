
# pages/30_Genially.py
# -*- coding: utf-8 -*-

import streamlit as st

from lib.ui import sidebar_title_and_nav

from streamlit.components.v1 import html

from lib.ui2 import login_widget, is_teacher
from lib.ui import sidebar_title_and_nav, inject_base_style  # ya lo tendrás
import streamlit as st

# st.set_page_config(page_title="Genially en Streamlit", layout="wide")
# inject_base_style()

# NAV personalizada debajo de la cabecera (título + nivel/año)
#sidebar_title_and_nav(extras=True)  # autodetecta páginas automáticamente
# --- Sidebar: login + navegación filtrada ---
with st.sidebar:
    login_widget()

nav_items = [
    ("app.py", "♟️ Inicio"),
    ("pages/10_Rondas.py", "🧩 Rondas"),
    ("pages/20_Clasificacion.py", "🏆 Clasificación"),
    ("pages/99_Administracion.py", "🛠️ Administración"),
    ("pages/30_Genially.py", "♞ Genially"),
]
# Oculta Administración a alumnado
if not is_teacher():
    nav_items = [it for it in nav_items if "99_Administracion.py" not in it[0]]

sidebar_title_and_nav(extras=True, items=nav_items)


# Compactar el marco derecho (main) para evitar scroll por padding vertical
st.markdown("""
<style>
/* Reduce el padding superior/inferior del contenedor principal */
div.block-container { 
  padding-top: 3.00rem !important; 
  padding-bottom: .30rem !important; 
}
/* Un pelín menos de separación entre bloques del main */
[data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"]{
  gap: 1.00rem !important;
}
</style>
""", unsafe_allow_html=True)


GENIALLY_URL = "https://view.genially.com/68bfc66a46b5ebd63d00b9b0"

ratio = "32:9"  # "21:9" o "16:9"
ratios = {"21:9": 100*9/21, "32:9": 100*9/32, "16:9": 56.25}
padding_pct = ratios[ratio]

# IMPORTANTE: pon un height > 0 para que Streamlit reserve espacio
html(f"""
<div style="position:relative; width:100%; padding-top:{padding_pct:.4f}%; min-height:180px;">
  <iframe
    src="{GENIALLY_URL}"
    style="position:absolute; inset:0; width:100%; height:100%; border:0;"
    frameborder="0"
    allow="fullscreen"
    allowfullscreen>
  </iframe>
</div>
""", height=420)  # ← reserva en Streamlit (ajústalo si te queda corto)
