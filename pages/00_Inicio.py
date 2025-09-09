# pages/00_🏠_Inicio.py
# -*- coding: utf-8 -*-
import streamlit as st

from lib.ui import page_header, hero_portada, chip, inject_base_style
from lib.tournament import (
    load_config,
    list_round_files,
    is_published,
    r1_seed,
    round_file,
    last_modified,
)

st.set_page_config(page_title="Inicio", page_icon="🏠", layout="wide")
inject_base_style()

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

def _last_mod_text():
    target = ronda_actual if ronda_actual is not None else (round_nums[-1] if round_nums else None)
    if target is None:
        return "—"
    return last_modified(round_file(target))

st.markdown("#### Estado del torneo")
with st.container():
    chip(f"📣 Publicadas: {pub_cnt} / {n_plan}", "green" if pub_cnt > 0 else ("yellow" if generadas > 0 else "red"))
    chip(f"🗂️ Generadas: {generadas}", "green" if generadas == n_plan and n_plan > 0 else ("yellow" if generadas > 0 else "red"))
    chip(f"⭐ Ronda ACTUAL: {ronda_actual if ronda_actual is not None else '—'}", "green" if ronda_actual else "yellow")
    chip(f"🎲 Semilla R1: {seed if seed else '—'}", "green" if seed else "yellow")
    chip(f"🕒 Última actualización: {_last_mod_text()}", "yellow")

st.divider()

# -------------------------------
# Tarjetas de navegación (clicables con ?page=...)
# Asegúrate de que tus archivos se llaman EXACTAMENTE:
#   pages/10_Rondas.py, pages/20_Clasificacion.py, pages/99_Admin.py
# -------------------------------
CARD_CSS = """
<style>
.card-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
@media (max-width: 900px){ .card-grid{ grid-template-columns: 1fr; } }
a.card-link.full {
  display:block; text-decoration:none; color:inherit;
  background: var(--panel);
  border:1px solid rgba(36,32,36,0.08);
  border-radius: 14px; padding: 1rem 1.1rem;
  transition: transform .08s ease, box-shadow .2s ease;
}
a.card-link.full:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(36,32,36,0.10);
}
.card-title { font-family:'Nunito','Inter',sans-serif; font-weight:800; font-size:1.1rem; margin:0 0 0.25rem 0;}
.card-desc  { color: var(--muted); font-size:0.95rem; margin:0; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="card-grid">
      <a class="card-link full" href="./?page=10_Rondas">
        <div class="card-title">🧩 Rondas</div>
        <p class="card-desc">Emparejamientos y resultados, con BYEs y estado por ronda.</p>
      </a>
      <a class="card-link full" href="./?page=20_Clasificacion">
        <div class="card-title">🏆 Clasificación</div>
        <p class="card-desc">Tabla en vivo (solo rondas publicadas), con Buchholz.</p>
      </a>
      <a class="card-link full" href="./?page=99_Admin">
        <div class="card-title">🛠️ Administración</div>
        <p class="card-desc">Publicar, despublicar, editar resultados y generar rondas.</p>
      </a>
    </div>
    """,
    unsafe_allow_html=True
)

# Fallback visible por si alguna vez cambia el router de Streamlit
st.caption("Si algún enlace no abre, usa la barra lateral o estos accesos:")
try:
    st.page_link("pages/10_Rondas.py", label="Ir a Rondas", icon="🧩")
    st.page_link("pages/20_Clasificacion.py", label="Ir a Clasificación", icon="🏆")
    st.page_link("pages/99_Admin.py", label="Ir a Administración", icon="🛠️")
except Exception:
    pass
