# pages/00_🏠_Inicio.py
# -*- coding: utf-8 -*-
import streamlit as st

from lib.ui import hero_portada, inject_base_style
from lib.tournament import (
    DATA_DIR,
    load_config,
    list_round_files,
    is_published,
    round_file,
    last_modified,
    planned_rounds,
    format_with_cfg,
)

st.set_page_config(page_title="Inicio", page_icon="🏠", layout="wide")
inject_base_style()

# Config y contexto
cfg = load_config()
titulo = cfg.get("titulo", "Ajedrez en los recreos")
nivel = cfg.get("nivel", "Todos")
anio = cfg.get("anio", "")
JUG_PATH = f"{DATA_DIR}/jugadores.csv"
n_plan = planned_rounds(cfg, JUG_PATH)

# Portada (hero con nivel/año)
hero_portada(
    format_with_cfg("{titulo} — {nivel}", cfg),
    format_with_cfg("Curso {anio} — Consulta rondas, resultados y clasificación en tiempo real.", cfg)
)

# Estado (tabla 1 línea)
round_nums = sorted(list_round_files(n_plan))
generadas = len(round_nums)
publicadas = [i for i in round_nums if is_published(i)]
pub_cnt = len(publicadas)
ronda_actual = max(publicadas) if publicadas else None

def _last_mod_text():
    target = ronda_actual if ronda_actual is not None else (round_nums[-1] if round_nums else None)
    if target is None:
        return "—"
    return last_modified(round_file(target))

last_mod = _last_mod_text()

TABLE_CSS = """
<style>
.state-wrap { overflow-x: auto; margin: .25rem 0 1rem 0; }
.state-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}
.state-table th, .state-table td {
  border: 1px solid rgba(36,32,36,0.10);
  padding: .45rem .6rem;
  white-space: nowrap;
  text-align: left;
}
.state-table thead th {
  background: rgba(115,192,238,0.12);
  font-weight: 700;
}
.state-table tbody td { background: #fff; }
</style>
"""
st.markdown(TABLE_CSS, unsafe_allow_html=True)

st.markdown(
    f"""
<div class="state-wrap">
<table class="state-table">
  <thead>
    <tr>
      <th>📣 Publicadas</th>
      <th>🗂️ Generadas</th>
      <th>⭐ Ronda ACTUAL</th>
      <th>🕒 Última actualización</th>
      <th>🧭 Plan de rondas</th>
      <th>🎓 Nivel</th>
      <th>📅 Año</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>{pub_cnt}</td>
      <td>{generadas}</td>
      <td>{ronda_actual if ronda_actual is not None else "—"}</td>
      <td>{last_mod}</td>
      <td>{n_plan}</td>
      <td>{nivel}</td>
      <td>{anio}</td>
    </tr>
  </tbody>
</table>
</div>
""",
    unsafe_allow_html=True
)

st.divider()

# Tarjetas (misma pestaña, sin superposición)
CARD_CSS = """
<style>
.stLinkButton { width: 100% !important; }
.stLinkButton > a {
  display: block !important;
  width: 100% !important;
  text-decoration: none !important;
  color: inherit !important;
  white-space: normal !important;
  background: var(--panel) !important;
  border: 1px solid rgba(36,32,36,0.08) !important;
  border-radius: 14px !important;
  padding: 1rem 1.1rem !important;
  font-weight: 800 !important;
  font-size: 1.05rem !important;
  box-shadow: none !important;
  transition: transform .08s ease, box-shadow .2s ease;
}
.stLinkButton > a:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(36,32,36,0.10);
}
.card-desc  {
  color: var(--muted);
  font-size: .95rem;
  margin-top: .35rem;
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

def card_page(title_emoji: str, title: str, desc: str, target_py: str, key: str):
    try:
        st.page_link(target_py, label=f"{title_emoji} {format_with_cfg(title, cfg)}", key=f"plink_{key}")
    except Exception:
        if st.button(f"{title_emoji} {format_with_cfg(title, cfg)}", key=f"btn_{key}", use_container_width=True):
            try:
                st.switch_page(target_py)
            except Exception:
                st.warning("No se pudo cambiar de página automáticamente. Usa la barra lateral, por favor.")
    st.markdown(f"<div class='card-desc'>{format_with_cfg(desc, cfg)}</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    card_page("🧩", "Rondas — {nivel}", "Emparejamientos y resultados, con BYEs y estado por ronda.", "pages/10_Rondas.py", "rondas")
with c2:
    card_page("🏆", "Clasificación — {nivel}", "Tabla en vivo (solo rondas publicadas), con Buchholz.", "pages/20_Clasificacion.py", "clas")
with c3:
    card_page("🛠️", "Administración — {nivel}", "Publicar, despublicar, editar resultados y generar rondas.", "pages/99_Admin.py", "admin")
