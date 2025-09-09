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
.state-table tbody td {
  background: #fff;
}
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
# Tarjetas de navegación (misma pestaña)
# Usamos st.page_link y lo estilizamos como "card" (clickable de bloque).
# -------------------------------
CARD_CSS = """
<style>
/* Que las page_link parezcan tarjetas y ocupen todo el bloque */
.stLinkButton > a {
  display:block !important;
  text-decoration:none !important;
  color:inherit !important;
  background: var(--panel);
  border:1px solid rgba(36,32,36,0.08);
  border-radius: 14px;
  padding: 1rem 1.1rem;
  transition: transform .08s ease, box-shadow .2s ease;
  white-space: pre-line; /* respeta saltos de línea en label */
  font-weight: 800;
  font-size: 1.05rem;
}
.stLinkButton > a:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 22px rgba(36,32,36,0.10);
}
.stLinkButton > a small {
  display:block; font-weight: 500; color: var(--muted); font-size: .95rem; margin-top:.15rem;
}
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)

# Tres columnas con page_link (abre en la misma pestaña automáticamente)
c1, c2, c3 = st.columns(3)

with c1:
    try:
        st.page_link(
            "pages/10_Rondas.py",
            label="🧩 Rondas\n"
                  "Emparejamientos y resultados, con BYEs y estado por ronda.",
        )
    except Exception:
        # Fallback mínimo si tu versión no tiene page_link
        if st.button("🧩 Rondas — Abrir"):
            try:
                st.switch_page("pages/10_Rondas.py")
            except Exception:
                st.warning("Ve a Rondas desde la barra lateral, por favor.")

with c2:
    try:
        st.page_link(
            "pages/20_Clasificacion.py",
            label="🏆 Clasificación\n"
                  "Tabla en vivo (solo rondas publicadas), con Buchholz.",
        )
    except Exception:
        if st.button("🏆 Clasificación — Abrir"):
            try:
                st.switch_page("pages/20_Clasificacion.py")
            except Exception:
                st.warning("Ve a Clasificación desde la barra lateral, por favor.")

with c3:
    try:
        st.page_link(
            "pages/99_Admin.py",
            label="🛠️ Administración\n"
                  "Publicar, despublicar, editar resultados y generar rondas.",
        )
    except Exception:
        if st.button("🛠️ Administración — Abrir"):
            try:
                st.switch_page("pages/99_Admin.py")
            except Exception:
                st.warning("Ve a Administración desde la barra lateral, por favor.")
