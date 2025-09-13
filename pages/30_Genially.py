
# pages/30_Genially.py
# -*- coding: utf-8 -*-

import streamlit as st

from lib.ui import sidebar_title_and_nav

from streamlit.components.v1 import html

# st.set_page_config(page_title="Genially en Streamlit", layout="wide")
# inject_base_style()

# NAV personalizada debajo de la cabecera (título + nivel/año)
#sidebar_title_and_nav(extras=True)  # autodetecta páginas automáticamente
sidebar_title_and_nav(
    extras=True,
    items=[
        ("app.py", "♟️ Inicio"),
        ("pages/10_Rondas.py", "🧩 Rondas"),
        ("pages/20_Clasificacion.py", "🏆 Clasificación"),
        ("pages/99_Administracion.py", "🛠️ Administración"),
        ("pages/30_Genially.py", "♞ Genially")
    ]
)




GENIALLY_URL = "https://view.genially.com/68bfc66a46b5ebd63d00b9b0"

st.sidebar.header("Opciones de embed")
alto = st.sidebar.slider("Altura (px)", 400, 1200, 800, 50)
scroll = st.sidebar.toggle("Scroll en iframe", value=True)

html(f"""
<div style="position:relative; width:100%; height:{alto}px;">
  <iframe
    src="{GENIALLY_URL}"
    style="position:absolute; top:0; left:0; width:100%; height:100%; border:0; overflow:{'auto' if scroll else 'hidden'};"
    frameborder="0"
    allowfullscreen>
  </iframe>
</div>
""", height=alto+20)

