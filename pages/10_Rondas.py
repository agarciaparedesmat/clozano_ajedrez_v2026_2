# pages/10_Rondas.py
# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd

from lib.ui import page_header
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

# Cabecera con nivel/año
cfg = load_config()
page_header(format_with_cfg("Rondas — {nivel}", cfg), format_with_cfg("Curso {anio} · Emparejamientos y resultados", cfg))

# Nº de rondas planificado (auto o fijo)
JUG_PATH = f"{DATA_DIR}/jugadores.csv"
n = planned_rounds(cfg, JUG_PATH)

# Cargar rondas existentes
round_nums = list_round_files(n)
if not round_nums:
    st.info("Aún no hay rondas generadas.")
    st.stop()
round_nums = sorted(round_nums)

publicadas = [i for i in round_nums if is_published(i)]
ronda_actual = max(publicadas) if publicadas else None
generadas = len(round_nums)
total_plan = n

# Chips
c1, c2, c3 = st.columns([2, 2, 2])
with c1:
    if ronda_actual is not None:
        st.success(f"⭐ Ronda ACTUAL: **Ronda {ronda_actual}**")
    else:
        st.warning("Sin rondas publicadas.")
with c2:
    st.info(f"📣 Publicadas: **{len(publicadas)} / {total_plan}**  ·  🗂️ Generadas: **{generadas}**")
with c3:
    try:
        st.page_link("pages/20_Clasificacion.py", label="Abrir Clasificación", icon="🏆")
    except Exception:
        pass

st.divider()

# Filtro
modo = st.radio("Mostrar", ["Todas", "Solo publicadas", "Solo no publicadas"], horizontal=True, index=0)

# Navegación rápida
cols = st.columns([2, 3])
with cols[0]:
    goto = st.selectbox("Ir a la ronda…", ["(ninguna)"] + [f"Ronda {i}" for i in round_nums], index=0)
with cols[1]:
    st.caption("Atajos:")
    btn_cols = st.columns(min(len(round_nums), 10))
    for idx, i in enumerate(round_nums):
        if idx % 10 == 0 and idx > 0:
            btn_cols = st.columns(min(len(round_nums) - idx, 10))
        if btn_cols[idx % 10].button(f"R{i}", key=f"btn_goto_R{i}"):
            st.session_state["goto_round"] = i
            st.experimental_rerun()

if goto != "(ninguna)":
    try:
        st.session_state["goto_round"] = int(goto.split()[-1])
    except Exception:
        pass
goto_round = st.session_state.get("goto_round")

# Helpers de normalización (como ya tenías)
def _normalize_result_series(s: pd.Series) -> pd.Series:
    return (
        s.astype(str).str.strip()
         .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )
def _results_empty_count(df: pd.DataFrame) -> int:
    if df is None or df.empty or "resultado" not in df.columns:
        return 0
    res = _normalize_result_series(df["resultado"])
    return int((res == "").sum())

def render_round(i: int, etiqueta_extra: str = ""):
    path = round_file(i)
    df = read_csv_safe(path)
    pub = is_published(i)
    if df is None or df.empty:
        return

    safe_df = df.copy()
    if "seleccionar" in safe_df.columns:
        safe_df = safe_df.drop(columns=["seleccionar"])

    for col in ["mesa", "blancas_nombre", "negras_nombre", "resultado", "negras_id"]:
        if col not in safe_df.columns:
            safe_df[col] = ""

    empties = _results_empty_count(safe_df)
    estado = "✅ Cerrada" if (pub and empties == 0) else ("📣 Publicada" if pub else "📝 Borrador")
    lm = last_modified(path)
    titulo = f"### Ronda {i} — {estado}"
    if etiqueta_extra:
        titulo += f" — {etiqueta_extra}"
    st.markdown(titulo)
    st.caption(f"Archivo: `{path}` · Última modificación: {lm} · Resultados vacíos: {empties}")

    bye_mask = (safe_df["negras_id"].astype(str).str.upper().eq("BYE")
                | safe_df["negras_nombre"].astype(str).str.upper().eq("BYE"))
    safe_df["BYE"] = bye_mask.map({True: "🟨 BYE", False: ""})

    try:
        safe_df["mesa"] = pd.to_numeric(safe_df["mesa"], errors="coerce")
    except Exception:
        pass
    safe_df = safe_df.sort_values(by=["mesa"], na_position="last")

    safe_df["resultado"] = _normalize_result_series(safe_df["resultado"])
    show_df = safe_df.copy()
    show_df.loc[show_df["resultado"] == "", "resultado"] = "—"
    show_df = show_df[["mesa", "blancas_nombre", "negras_nombre", "resultado", "BYE"]]

    st.dataframe(
        show_df, use_container_width=True, hide_index=True,
        column_config={
            "mesa": st.column_config.NumberColumn("Mesa", help="Número de mesa"),
            "blancas_nombre": st.column_config.TextColumn("Blancas"),
            "negras_nombre": st.column_config.TextColumn("Negras"),
            "resultado": st.column_config.TextColumn("Resultado"),
            "BYE": st.column_config.TextColumn(""),
        },
    )

def filtro_permite(i: int) -> bool:
    pub = is_published(i)
    if modo == "Solo publicadas" and not pub:
        return False
    if modo == "Solo no publicadas" and pub:
        return False
    return True

pintadas = set()
if goto_round is not None:
    if filtro_permite(goto_round):
        st.info(f"🔎 Vista prioritaria: Ronda {goto_round}")
        render_round(goto_round, etiqueta_extra="⤴️ Seleccionada")
        pintadas.add(goto_round)
        st.divider()
    else:
        st.warning(f"La Ronda {goto_round} no encaja con el filtro “{modo}”.")

if ronda_actual is not None and filtro_permite(ronda_actual) and ronda_actual not in pintadas:
    st.success(f"⭐ Ronda ACTUAL: Ronda {ronda_actual}")
    render_round(ronda_actual, etiqueta_extra="⭐ Ronda ACTUAL")
    pintadas.add(ronda_actual)
    st.divider()

for i in round_nums:
    if i in pintadas: continue
    if not filtro_permite(i): continue
    render_round(i)

st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
