# pages/20_Clasificacion.py
# -*- coding: utf-8 -*-
import io, re
import streamlit as st
import pandas as pd

from lib.ui import page_header
from lib.ui import hero_portada, inject_base_style, sidebar_title_and_nav

from lib.tournament import (
    DATA_DIR,
    load_config,
    read_players_from_csv,
    read_csv_safe,
    list_round_files,
    round_file,
    is_published,
    apply_results,
    compute_standings,
    last_modified,
    planned_rounds,
    format_with_cfg,
)

# NAV personalizada debajo de la cabecera (título + nivel/año)
#sidebar_title_and_nav(extras=True)  # autodetecta páginas automáticamente
sidebar_title_and_nav(
    extras=True,
    items=[
        ("app.py", "♟️ Inicio"),
        ("pages/10_Rondas.py", "🧩 Rondas"),
        ("pages/20_Clasificacion.py", "🏆 Clasificación"),
        ("pages/99_Administracion.py", "🛠️ Administración")
    ]
)

# Cabecera con nivel/año

cfg = load_config()
page_header(format_with_cfg("🏆 Clasificación — {nivel}", cfg), format_with_cfg("Curso {anio} · Solo tiene en cuenta rondas PUBLICADAS", cfg))

# Helpers
def slugify(s: str) -> str:
    s = re.sub(r"\s+", "_", str(s).strip())
    s = re.sub(r"[^A-Za-z0-9_\\-]+", "", s)
    return s or "torneo"

# Nº de rondas planificado
JUG_PATH = f"{DATA_DIR}/jugadores.csv"
n = planned_rounds(cfg, JUG_PATH)

# Cargar jugadores
jug_path = f"{DATA_DIR}/jugadores.csv"
players = read_players_from_csv(jug_path)
if not players:
    st.info("Aún no hay jugadores cargados.")
    st.stop()

# Rondas
round_nums = sorted(list_round_files(n))
if not round_nums:
    st.info("Aún no hay rondas generadas.")
    st.stop()

publicadas = [i for i in round_nums if is_published(i)]
ronda_actual = max(publicadas) if publicadas else None
generadas = len(round_nums)
total_plan = n

# Chips
c1, c2= st.columns([2, 2])
with c1:
    if ronda_actual is not None:
        st.success(f"⭐ Ronda ACTUAL: **Ronda {ronda_actual}**")
    else:
        st.warning("Sin rondas publicadas.")
with c2:
    st.info(f"📣 Publicadas: **{len(publicadas)} / {total_plan}** ")


st.divider()

# Recalcular clasificación (solo publicadas)
BYE_DEFAULT = 1.0
for i in publicadas:
    dfp = read_csv_safe(round_file(i))
    players = apply_results(players, dfp, bye_points=BYE_DEFAULT)

df_st = compute_standings(players)

st.markdown("### Tabla")
if df_st is None or df_st.empty:
    st.info("Sin datos de clasificación todavía.")
else:
    st.dataframe(
        df_st[["pos", "nombre", "curso", "grupo", "puntos", "buchholz", "pj"]],
        use_container_width=True, hide_index=True,
        column_config={
            "pos": st.column_config.NumberColumn("Pos"),
            "nombre": st.column_config.TextColumn("Jugador/a"),
            "curso": st.column_config.TextColumn("Curso"),
            "grupo": st.column_config.TextColumn("Grupo"),
            "puntos": st.column_config.NumberColumn("Puntos"),
            "buchholz": st.column_config.NumberColumn("Buchholz"),
            "pj": st.column_config.NumberColumn("PJ"),
        },
    )

    # Descarga CSV con nivel/año en el nombre
    csv_buf = io.StringIO()
    df_st.to_csv(csv_buf, index=False, encoding="utf-8")
    fn = f"clasificacion_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.csv"
    st.download_button(
        "⬇️ Descargar clasificación (CSV)",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name=fn,
        mime="text/csv",
        use_container_width=True,
    )


st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
