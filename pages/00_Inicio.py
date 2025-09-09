# pages/00_🏠_Inicio.py
# -*- coding: utf-8 -*-
import streamlit as st

from lib.ui import page_header, hero_portada, inject_base_style
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
# Estado del torneo (tabla 1 línea)
# -------------------------------
cfg = load_config()
n_plan = int(cfg.get("rondas", 5))

round_nums = sorted(list_round_files(n_plan))
generadas = len(round_nums)
publicadas = [i for i in round_nums if is_published(i)]
pub_cnt = len(publicadas)
ronda_actual = max(publicadas) if publicadas else None
seed = r1_seed() or "—"

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
      <th>🎲 Semilla R1</th>
      <th>🕒 Última actualización</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>{pub_cnt} / {n_plan}</td>
      <td>{generadas}</td>
      <td>{ronda_actual if ronda_actual is not None else "—"}</td>
      <td>{seed}</td>
      <td>{last_mod}</td>
    </tr>
  </tbody>
</table>
</div>
""",
    unsafe_allow_html=True
)

st.divider()

# -------------------------------
# Tarjetas de navegación (misma pestaña, sin solaparse)
# -------------------------------
CARD_CSS = """
<style>
.app-card {
  background: var(--panel);
  border:1px solid rgba(36,32,36,0.08);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  transition: transform .08s ease, box-shadow .2s ease;
}
.app-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(36,32,36,0.10);
}
/* Título clicable (page_link) */
.app-card .stLinkButton > a {
  display:block !important;
  width:100% !important;
  text-decoration:none !important;
  color:inherit !important;
  white-space: normal !important;  /* rompe línea correctamente */
  font-weight: 800;
  font-size: 1.05rem;
  padding: .2rem 0;
  background: transparent !important;
  border: 0 !important;
  box-shadow: none !important;
}
/* Descripción bajo el título */
.app-card .desc {
  color: var(--muted);
  font-size: .95rem;
  margin-top: .25rem;
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

def card_page(title_emoji: str, title: str, desc: str, target_py: str, key: str):
    with st.container():
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        # Título clicable (misma pestaña) con page_link
        try:
            st.page_link(target_py, label=f"{title_emoji} {title}", key=f"plink_{key}")
        except Exception:
            # Fallback si tu versión no soporta page_link
            if st.button(f"{title_emoji} {title}", key=f"btn_{key}", use_container_width=True):
                try:
                    st.switch_page(target_py)
                except Exception:
                    st.warning("No se pudo cambiar de página automáticamente. Usa la barra lateral, por favor.")
        # Descripción (no clicable)
        st.markdown(f"<div class='desc'>{desc}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    card_page("🧩", "Rondas", "Emparejamientos y resultados, con BYEs y estado por ronda.", "pages/10_Rondas.py", "rondas")
with c2:
    card_page("🏆", "Clasificación", "Tabla en vivo (solo rondas publicadas), con Buchholz.", "pages/20_Clasificacion.py", "clas")
with c3:
    card_page("🛠️", "Administración", "Publicar, despublicar, editar resultados y generar rondas.", "pages/99_Admin.py", "admin")
