# pages/00_🏠_Inicio.py
# -*- coding: utf-8 -*-
import streamlit as st

from lib.ui import page_header, hero_portada, chip
from lib.tournament import (
    load_config,
    list_round_files,
    is_published,
    r1_seed,
    round_file,
    last_modified,
)

st.set_page_config(page_title="Inicio", page_icon="🏠", layout="wide")

# Cabecera + hero
page_header("Inicio", "Bienvenido/a — Torneo suizo escolar")
hero_portada("Ajedrez en los recreos", "Consulta rondas, resultados y clasificación en tiempo real.")

# -------------------------------
# Resumen de estado (chips)
# -------------------------------
cfg = load_config()
n_plan = int(cfg.get("rondas", 5))

round_nums = sorted(list_round_files(n_plan))
generadas = len(round_nums)
publicadas = [i for i in round_nums if is_published(i)]
pub_cnt = len(publicadas)
ronda_actual = max(publicadas) if publicadas else None
seed = r1_seed()

# Última actualización: tomamos la última publicada si existe, si no la última generada
def _last_mod_text():
    target = ronda_actual if ronda_actual is not None else (round_nums[-1] if round_nums else None)
    if target is None:
        return "—"
    return last_modified(round_file(target))

st.markdown("#### Estado del torneo")

chips = st.container()
with chips:
    # Publicadas
    chip(f"📣 Publicadas: {pub_cnt} / {n_plan}", "green" if pub_cnt > 0 else ("yellow" if generadas > 0 else "red"))
    # Generadas
    chip(f"🗂️ Generadas: {generadas}", "green" if generadas == n_plan and n_plan > 0 else ("yellow" if generadas > 0 else "red"))
    # Ronda actual
    chip(f"⭐ Ronda ACTUAL: {ronda_actual if ronda_actual is not None else '—'}", "green" if ronda_actual else "yellow")
    # Semilla R1
    chip(f"🎲 Semilla R1: {seed if seed else '—'}", "green" if seed else "yellow")
    # Última actualización
    chip(f"🕒 Última actualización: {_last_mod_text()}", "yellow")

st.divider()

# -------------------------------
# Tarjetas de navegación
# -------------------------------
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

st.caption("💡 Consejo: fija esta portada como página de inicio en el navegador del aula.")
