
# pages/30_Genially.py
# -*- coding: utf-8 -*-

import streamlit as st

from lib.ui import sidebar_title_and_nav

from streamlit.components.v1 import html

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

#st.set_page_config(page_title="Genially en Streamlit", layout="wide")

GENIALLY_URL = "https://view.genially.com/x68bfc66a46b5ebd63d00b9b0"  # ← pon aquí tu URL

# iframe nativo de Streamlit
st.components.v1.iframe(
    src=GENIALLY_URL,
    width=None,          # ocupa el ancho disponible
    height=700,          # ajusta a tu gusto
    scrolling=True       # útil si el contenido es más alto
)



