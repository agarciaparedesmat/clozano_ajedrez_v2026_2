# pages/00_🏠_Inicio.py
# -*- coding: utf-8 -*-
import streamlit as st
from lib.ui import page_header, hero_portada

st.set_page_config(page_title="Inicio", page_icon="🏠", layout="wide")

page_header("Inicio", "Bienvenido/a — Torneo suizo escolar")
hero_portada("Ajedrez en los recreos", "Consulta rondas, resultados y clasificación en tiempo real.")

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(
        """
        <a class="card-link" href="./10_Rondas">
          <div class="card-title">🧩 Rondas</div>
          <p class="card-desc">Emparejamientos y resultados, con BYEs y estado por ronda.</p>
        </a>
        """,
        unsafe_allow_html=True
    )
with c2:
    st.markdown(
        """
        <a class="card-link" href="./20_Clasificacion">
          <div class="card-title">🏆 Clasificación</div>
          <p class="card-desc">Tabla en vivo (solo rondas publicadas), con Buchholz.</p>
        </a>
        """,
        unsafe_allow_html=True
    )
with c3:
    st.markdown(
        """
        <a class="card-link" href="./99_Admin">
          <div class="card-title">🛠️ Administración</div>
          <p class="card-desc">Publicar, despublicar, editar resultados y generar rondas.</p>
        </a>
        """,
        unsafe_allow_html=True
    )

st.caption("💡 Consejo: Puedes fijar esta portada como página de inicio en el navegador del aula.")
