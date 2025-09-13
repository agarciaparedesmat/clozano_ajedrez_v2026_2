
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

ratio = st.sidebar.selectbox("Relación de aspecto", ["21:9", "32:9", "16:9", "Personalizada"])
custom_pct = 0  # padding-top en %, solo si eliges 'Personalizada'

ratios = {"21:9": 100*9/21, "32:9": 100*9/32, "16:9": 56.25}
padding_pct = ratios.get(ratio, custom_pct or 35)  # 35% ≈ muy panorámico

html(f"""
<div style="position:relative; width:100%; padding-top:{padding_pct:.4f}%;">
  <iframe
    src="{GENIALLY_URL}"
    style="position:absolute; inset:0; width:100%; height:100%; border:0;"
    frameborder="0"
    allow="fullscreen"
    allowfullscreen>
  </iframe>
</div>
""", height=0)  # el alto lo da el padding-top (responsive)

