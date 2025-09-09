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
#page_header("Inicio", "Bienvenido/a — Torneo suizo escolar")
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

# -------------------------------
# Tarjetas de navegación (clican y abren en la misma pestaña)
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

# Importante: los href usan ?page=NombreArchivoSinExtension y NO tienen target="_blank"
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

# (Quitamos los enlaces alternativos para evitar duplicidad)
