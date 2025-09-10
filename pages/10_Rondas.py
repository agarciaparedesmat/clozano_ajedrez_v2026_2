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

# NAV (personalizada) bajo cabecera lateral
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

# ---------- estado inicial seguro ----------
if "rondas_view_select" not in st.session_state:
    st.session_state["rondas_view_select"] = ronda_actual

# Si algún botón ha pedido salto, aplícalo ANTES de crear el selectbox
jump_to = st.session_state.pop("rondas_jump_to", None)
if isinstance(jump_to, int) and jump_to in publicadas:
    st.session_state["rondas_view_select"] = jump_to

# Si el valor guardado ya no es válido, corrígelo
if st.session_state["rondas_view_select"] not in publicadas:
    st.session_state["rondas_view_select"] = ronda_actual

# ---------- selector + botonera numérica ----------
current_round = st.session_state["rondas_view_select"]
sel = st.selectbox(
    "Ver ronda publicada",
    options=publicadas,
    index=publicadas.index(current_round),
    format_func=lambda i: f"Ronda {i}",
    key="rondas_view_select",
)

# === Estilo “pill” para la botonera ===
PILLS_CSS = """
<style>
/* Estilo pill para los botones de la botonera (sin afectar a st.download_button) */
.stButton > button {
  border-radius: 9999px !important;
  padding: .28rem .75rem !important;
  border: 1px solid var(--border) !important;
  background: #fff !important;
  color: var(--text) !important;
  font-weight: 700 !important;
}
.stButton > button:hover {
  background: rgba(36,32,36,.06) !important;
}
</style>
"""
st.markdown(PILLS_CSS, unsafe_allow_html=True)

st.caption("Ir directo a…")
per_row = min(len(publicadas), 10)  # hasta 10 por fila
cols = st.columns(per_row)

def _request_jump(i: int):
    # Callback seguro: no toca la clave del widget directamente
    st.session_state["rondas_jump_to"] = int(i)

for idx, i in enumerate(publicadas):
    c = cols[idx % per_row]
    is_active = (i == sel)
    label = f"✓ {i}" if is_active else f"{i}"
    c.button(
        label,
        key=f"chip_R{i}",
        use_container_width=True,
        on_click=_request_jump,
        args=(i,),
    )
    if (idx + 1) % per_row == 0 and (idx + 1) < len(publicadas):
        cols = st.columns(min(per_row, len(publicadas) - (idx + 1)))

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

    # BYE: badge en línea, sin columna extra
    bye_mask = (
        safe_df["negras_id"].astype(str).str.upper().eq("BYE")
        | safe_df["negras_nombre"].astype(str).str.upper().eq("BYE")
    )
    show_df = safe_df.copy()
    show_df["negras_nombre_show"] = show_df["negras_nombre"].astype(str)
    show_df.loc[bye_mask, "negras_nombre_show"] = show_df["negras_nombre_show"].replace(
        {"": "BYE"}
    )
    show_df.loc[bye_mask, "negras_nombre_show"] = show_df["negras_nombre_show"] + "  🟨 BYE"

    # ordenar por mesa
    try:
        show_df["mesa"] = pd.to_numeric(show_df["mesa"], errors="coerce")
    except Exception:
        pass
    show_df = show_df.sort_values(by=["mesa"], na_position="last")

    # normalizar resultados para vista
    show_df["resultado"] = _normalize_result_series(show_df["resultado"])
    show_df.loc[show_df["resultado"] == "", "resultado"] = "—"

    st.dataframe(
        show_df[["mesa", "blancas_nombre", "negras_nombre_show", "resultado"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "mesa": st.column_config.NumberColumn("Mesa", help="Número de mesa"),
            "blancas_nombre": st.column_config.TextColumn("Blancas"),
            "negras_nombre_show": st.column_config.TextColumn("Negras"),
            "resultado": st.column_config.TextColumn("Resultado"),
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

st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
