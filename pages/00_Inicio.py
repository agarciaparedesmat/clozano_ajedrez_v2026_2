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
chips = st.container()
with chips:
    chip(f"📣 Publicadas: {pub_cnt} / {n_plan}", "green" if pub_cnt > 0 else ("yellow" if generadas > 0 else "red"))
    chip(f"🗂️ Generadas: {generadas}", "green" if generadas == n_plan and n_plan > 0 else ("yellow" if generadas > 0 else "red"))
    chip(f"⭐ Ronda ACTUAL: {ronda_actual if ronda_actual is not None else '—'}", "green" if ronda_actual else "yellow")
    chip(f"🎲 Semilla R1: {seed if seed else '—'}", "green" if seed else "yellow")
    chip(f"🕒 Última actualización: {_last_mod_text()}", "yellow")

st.divider()

# -------------------------------
# Tarjetas de navegación (con switch_page)
# -------------------------------
c1, c2, c3 = st.columns(3)

def card(title_emoji: str, title: str, desc: str, target_py: str, key: str):
    st.markdown(
        f"""
        <div class="card-link">
          <div class="card-title">{title_emoji} {title}</div>
          <p class="card-desc">{desc}</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Botón de acción dentro de la tarjeta
    if st.button("Abrir", key=key, use_container_width=True):
        try:
            st.switch_page(target_py)  # ✅ robusto: "pages/xxx.py"
        except Exception:
            # Fallback: intenta un enlace de página si la API no existe
            try:
                st.page_link(target_py, label=f"Abrir {title}", icon="↗️")
            except Exception:
                st.warning("No se pudo cambiar de página automáticamente. Usa la barra lateral, por favor.")

with c1:
    card("🧩", "Rondas", "Emparejamientos y resultados, con BYEs y estado por ronda.", "pages/10_Rondas.py", "go_rondas")
with c2:
    card("🏆", "Clasificación", "Tabla en vivo (solo rondas publicadas), con Buchholz.", "pages/20_Clasificacion.py", "go_clas")
with c3:
    card("🛠️", "Administración", "Publicar, despublicar, editar resultados y generar rondas.", "pages/99_Admin.py", "go_admin")

st.caption("💡 Consejo: fija esta portada como página de inicio en el navegador del aula.")
