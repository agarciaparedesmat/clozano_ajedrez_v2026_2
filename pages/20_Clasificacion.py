# pages/20_Clasificacion.py
# -*- coding: utf-8 -*-
import io
import streamlit as st
import pandas as pd

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
)

st.set_page_config(page_title="Clasificación", page_icon="🏆", layout="wide")
from lib.ui import page_header; page_header("🏆 Clasificación", "Tabla en tiempo real (rondas publicadas)")


#st.title("🏆 Clasificación")

cfg = load_config()
n = int(cfg.get("rondas", 5))

# -------------------------------------------------------
# Cargar jugadores
# -------------------------------------------------------
jug_path = f"{DATA_DIR}/jugadores.csv"
players = read_players_from_csv(jug_path)
if not players:
    st.info("Aún no hay jugadores cargados.")
    st.stop()

# -------------------------------------------------------
# Detectar rondas existentes/publicadas
# -------------------------------------------------------
round_nums = sorted(list_round_files(n))
if not round_nums:
    st.info("Aún no hay rondas generadas.")
    st.stop()

publicadas = [i for i in round_nums if is_published(i)]
ronda_actual = max(publicadas) if publicadas else None
generadas = len(round_nums)
total_plan = n

# -------------------------------------------------------
# Chips de estado + navegación a Rondas
# -------------------------------------------------------
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    if ronda_actual is not None:
        st.success(f"⭐ Ronda ACTUAL: **Ronda {ronda_actual}**")
    else:
        st.warning("Sin rondas publicadas.")
with c2:
    st.info(f"📣 Publicadas: **{len(publicadas)} / {total_plan}**  ·  🗂️ Generadas: **{generadas}**")
with c3:
    if st.button("🔗 Ir a Rondas", use_container_width=True):
        try:
            st.switch_page("pages/10_Rondas.py")
        except Exception:
            st.session_state["goto_round"] = ronda_actual
            st.warning("Abre la pestaña **Rondas** desde la barra lateral.")
    try:
        st.page_link("pages/10_Rondas.py", label="Abrir Rondas", icon="📄")
    except Exception:
        pass

st.divider()

# -------------------------------------------------------
# Recalcular clasificación (solo PUBLICADAS)
# -------------------------------------------------------
BYE_DEFAULT = 1.0  # coherente con Admin
for i in publicadas:
    dfp = read_csv_safe(round_file(i))
    players = apply_results(players, dfp, bye_points=BYE_DEFAULT)

df_st = compute_standings(players)

# Tabla de clasificación
st.markdown("### Tabla")
if df_st is None or df_st.empty:
    st.info("Sin datos de clasificación todavía.")
else:
    st.dataframe(
        df_st[["pos", "nombre", "curso", "grupo", "puntos", "buchholz", "pj"]],
        use_container_width=True,
        hide_index=True,
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

    # Descarga CSV
    csv_buf = io.StringIO()
    df_st.to_csv(csv_buf, index=False, encoding="utf-8")
    st.download_button(
        "⬇️ Descargar clasificación (CSV)",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name="clasificacion.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.divider()

# -------------------------------------------------------
# Navegación rápida a resultados de rondas publicadas
# -------------------------------------------------------
st.markdown("### Resultados por ronda (publicadas)")

if not publicadas:
    st.info("No hay rondas publicadas para mostrar resultados.")
    st.stop()

cols = st.columns([2, 3])
with cols[0]:
    goto = st.selectbox(
        "Ir a la ronda publicada…",
        options=[f"Ronda {i}" for i in publicadas],
        index=len(publicadas) - 1 if ronda_actual is None else publicadas.index(ronda_actual),
    )
with cols[1]:
    st.caption("Atajos:")
    btn_cols = st.columns(min(len(publicadas), 10))
    for idx, i in enumerate(publicadas):
        if idx % 10 == 0 and idx > 0:
            btn_cols = st.columns(min(len(publicadas) - idx, 10))
        if btn_cols[idx % 10].button(f"R{i}", key=f"btn_show_R{i}"):
            st.session_state["show_round_in_standings"] = i
            st.experimental_rerun()

# Selección desde el selectbox
try:
    sel_from_select = int(goto.split()[-1])
    st.session_state["show_round_in_standings"] = sel_from_select
except Exception:
    pass

show_i = st.session_state.get("show_round_in_standings", ronda_actual or publicadas[-1])

# -------------------------------------------------------
# Helpers
# -------------------------------------------------------
def _normalize_result_series(s: pd.Series) -> pd.Series:
    """Convierte None/nan/'None'/'nan'/'N/A' en '' y recorta espacios."""
    return (
        s.astype(str)
         .str.strip()
         .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )

# -------------------------------------------------------
# Render de resultados de la ronda seleccionada
# -------------------------------------------------------
def render_round_results(i: int):
    path = round_file(i)
    df = read_csv_safe(path)
    if df is None or df.empty:
        st.info(f"Ronda {i}: sin datos.")
        return

    lm = last_modified(path)
    st.markdown(f"#### Ronda {i} — 📣 Publicada")
    st.caption(f"Archivo: `{path}` · Última modificación: {lm}")

    safe_df = df.copy()
    # Ocultar columnas internas si aparecieran
    if "seleccionar" in safe_df.columns:
        safe_df = safe_df.drop(columns=["seleccionar"])

    # Asegurar columnas
    for col in ["mesa", "blancas_nombre", "negras_nombre", "resultado", "negras_id"]:
        if col not in safe_df.columns:
            safe_df[col] = ""

    # Badge BYE
    bye_mask = (
        safe_df["negras_id"].astype(str).str.upper().eq("BYE")
        | safe_df["negras_nombre"].astype(str).str.upper().eq("BYE")
    )
    safe_df["BYE"] = bye_mask.map({True: "🟨 BYE", False: ""})

    # Orden por mesa
    try:
        safe_df["mesa"] = pd.to_numeric(safe_df["mesa"], errors="coerce")
    except Exception:
        pass
    safe_df = safe_df.sort_values(by=["mesa"], na_position="last")

    # --- NORMALIZAR resultado para la vista ---
    safe_df["resultado"] = _normalize_result_series(safe_df["resultado"])
    show_df = safe_df.copy()
    show_df.loc[show_df["resultado"] == "", "resultado"] = "—"

    show_df = show_df[["mesa", "blancas_nombre", "negras_nombre", "resultado", "BYE"]]

    st.dataframe(
        show_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "mesa": st.column_config.NumberColumn("Mesa"),
            "blancas_nombre": st.column_config.TextColumn("Blancas"),
            "negras_nombre": st.column_config.TextColumn("Negras"),
            "resultado": st.column_config.TextColumn("Resultado"),
            "BYE": st.column_config.TextColumn(""),
        },
    )

render_round_results(show_i)
