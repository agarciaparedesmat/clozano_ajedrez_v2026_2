# pages/10_Rondas.py
# -*- coding: utf-8 -*-
import io
import re
import streamlit as st
import pandas as pd

from lib.ui import page_header, inject_base_style, sidebar_title_and_nav
from lib.tournament import (
    DATA_DIR,
    load_config,
    read_csv_safe,
    list_round_files,
    last_modified,
    is_published,
    round_file,
    planned_rounds,
    format_with_cfg,
)

st.set_page_config(page_title="Rondas", page_icon="🧩", layout="wide")
inject_base_style()

# NAV personalizada (debajo del título lateral)
sidebar_title_and_nav(
    extras=True,
    items=[
        ("app.py", "♟️ Inicio"),
        ("pages/10_Rondas.py", "🧩 Rondas"),
        ("pages/20_Clasificacion.py", "🏆 Clasificación"),
        ("pages/99_Administracion.py", "🛠️ Administración"),
    ],
)

cfg = load_config()
page_header(
    format_with_cfg("🧩 Rondas — {nivel}", cfg),
    format_with_cfg("Curso {anio} · Emparejamientos y resultados (solo PUBLICADAS)", cfg),
)

# ---------- utilidades ----------
def _slugify(s: str) -> str:
    s = re.sub(r"\s+", "_", str(s or "").strip())
    return re.sub(r"[^A-Za-z0-9_\-]+", "", s) or "torneo"

def _normalize_result_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.strip()
        .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )

def _results_empty_count(df: pd.DataFrame) -> int:
    if df is None or df.empty or "resultado" not in df.columns:
        return 0
    res = _normalize_result_series(df["resultado"])
    return int((res == "").sum())

# ---------- datos de rondas ----------
JUG_PATH = f"{DATA_DIR}/jugadores.csv"
n_plan = planned_rounds(cfg, JUG_PATH)

nums = sorted(list_round_files(n_plan))
publicadas = [i for i in nums if is_published(i)]

if not publicadas:
    st.info("Aún no hay **rondas publicadas**.")
    st.stop()

ronda_actual = max(publicadas)

# ---------- selector: solo publicadas ----------
opt = publicadas
# índice por defecto = ronda actual
try:
    default_idx = opt.index(ronda_actual)
except ValueError:
    default_idx = len(opt) - 1

sel_col, prev_col, next_col = st.columns([3, 1, 1])
with sel_col:
    sel = st.selectbox(
        "Ver ronda publicada",
        options=opt,
        index=default_idx,
        format_func=lambda i: f"Ronda {i}",
        key="rondas_view_select",
    )
with prev_col:
    if st.button("◀︎ Anterior", use_container_width=True, disabled=(sel == opt[0])):
        new_idx = max(0, opt.index(sel) - 1)
        st.session_state["rondas_view_select"] = opt[new_idx]
        st.experimental_rerun()
with next_col:
    if st.button("Siguiente ▶︎", use_container_width=True, disabled=(sel == opt[-1])):
        new_idx = min(len(opt) - 1, opt.index(sel) + 1)
        st.session_state["rondas_view_select"] = opt[new_idx]
        st.experimental_rerun()

st.divider()

# ---------- render de UNA sola ronda (la seleccionada) ----------
def render_round(i: int):
    path = round_file(i)
    df = read_csv_safe(path)
    if df is None or df.empty:
        st.warning(f"No hay datos para la Ronda {i}.")
        return

    safe_df = df.copy()
    # quitar columna 'seleccionar' si existiera (solo admin)
    if "seleccionar" in safe_df.columns:
        safe_df = safe_df.drop(columns=["seleccionar"])

    # asegurar columnas básicas
    for col in ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]:
        if col not in safe_df.columns:
            safe_df[col] = ""

    empties = _results_empty_count(safe_df)
    estado = "✅ Cerrada" if empties == 0 else "📣 Publicada"
    lm = last_modified(path)

    st.markdown(f"### Ronda {i} — {estado}")
    st.caption(f"Archivo: `{path}` · Última modificación: {lm} · Resultados vacíos: {empties}")

    # marcar BYEs
    bye_mask = (
        safe_df["negras_id"].astype(str).str.upper().eq("BYE")
        | safe_df["negras_nombre"].astype(str).str.upper().eq("BYE")
    )
    safe_df["BYE"] = bye_mask.map({True: "🟨 BYE", False: ""})

    # ordenar por mesa
    try:
        safe_df["mesa"] = pd.to_numeric(safe_df["mesa"], errors="coerce")
    except Exception:
        pass
    safe_df = safe_df.sort_values(by=["mesa"], na_position="last")

    # normalizar resultados para vista
    safe_df["resultado"] = _normalize_result_series(safe_df["resultado"])
    show_df = safe_df.copy()
    show_df.loc[show_df["resultado"] == "", "resultado"] = "—"

    st.dataframe(
        show_df[["mesa", "blancas_nombre", "negras_nombre", "resultado", "BYE"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "mesa": st.column_config.NumberColumn("Mesa", help="Número de mesa"),
            "blancas_nombre": st.column_config.TextColumn("Blancas"),
            "negras_nombre": st.column_config.TextColumn("Negras"),
            "resultado": st.column_config.TextColumn("Resultado"),
            "BYE": st.column_config.TextColumn(""),
        },
    )

    # descarga CSV
    export_cols = ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]
    df_export = safe_df[export_cols].copy()
    nivel_slug = _slugify(cfg.get("nivel", ""))
    anio_slug = _slugify(cfg.get("anio", ""))
    file_name = f"ronda_{i}_{nivel_slug}_{anio_slug}.csv" if (nivel_slug or anio_slug) else f"ronda_{i}.csv"

    buf = io.StringIO()
    df_export.to_csv(buf, index=False, encoding="utf-8")
    st.download_button(
        label=f"⬇️ Descargar CSV · Ronda {i}",
        data=buf.getvalue().encode("utf-8"),
        file_name=file_name,
        mime="text/csv",
        use_container_width=True,
        key=f"dl_ronda_{i}",
    )

# pinta solo la ronda seleccionada
render_round(sel)

# pie
st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
