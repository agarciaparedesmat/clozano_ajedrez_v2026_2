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
n_plan = planned_rounds(cfg, JUG_PATH)          # plan de rondas (auto o fijo)

round_nums = sorted(list_round_files(n_plan))   # generadas (publicadas o no)
generadas = len(round_nums)
publicadas = [i for i in round_nums if is_published(i)]
ronda_actual = max(publicadas) if publicadas else None
total_plan = n_plan

# ---------- RESUMEN (chips) ----------
c1, c2 = st.columns([2, 2])
with c1:
    if ronda_actual is not None:
        st.success(f"⭐ Ronda ACTUAL: **Ronda {ronda_actual}**")
    else:
        st.warning("Sin rondas publicadas.")
with c2:
    st.info(f"📣 Publicadas: **{len(publicadas)} / {total_plan}**")

st.divider()

# Si no hay publicadas, terminar aquí (la vista pública no enseña borradores)
if not publicadas:
    st.stop()

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

# ---------- selector + botonera numérica EN UNA SOLA LÍNEA ----------
# (colores del selector – cambia THEME si quieres)
THEME = "amber"
_palette = {
    "blue":  {"bg": "#DCEBFF","hover": "#E9F2FF","border": "#1D4ED8","border_hover":"#1743BD","icon":"#1743BD","ring":"rgba(29,78,216,.25)","text":"#0B3B8F"},
    "green": {"bg": "#E6F6EA","hover": "#EEF9F1","border": "#16A34A","border_hover":"#14833F","icon":"#14833F","ring":"rgba(22,163,74,.25)","text":"#0F5132"},
    "amber": {"bg": "#FFF1D6","hover": "#FFF6E6","border": "#D97706","border_hover":"#B75E03","icon":"#B75E03","ring":"rgba(217,119,6,.25)","text":"#8A4B00"},
}
c = _palette.get(THEME, _palette["blue"])
st.markdown(f"""
<style>
/* Selectbook estilizado SOLO en esta página */
[data-testid="stSelectbox"] div[role="combobox"] {{
  background: {c['bg']} !important; border: 2px solid {c['border']} !important;
  border-radius: 12px !important; padding: 2px 8px !important;
  color: {c['text']} !important; font-weight: 700 !important;
}}
[data-testid="stSelectbox"] div[role="combobox"]:hover {{
  background: {c['hover']} !important; border-color: {c['border_hover']} !important;
}}
[data-testid="stSelectbox"] div[role="combobox"]:focus-within {{
  box-shadow: 0 0 0 3px {c['ring']} !important;
}}
[data-testid="stSelectbox"] svg {{ color: {c['icon']} !important; }}

/* Pills de la botonera (no afecta a download_button) */
._chips_row .stButton > button {{
  border-radius: 9999px !important; padding: .28rem .75rem !important;
  border: 1px solid var(--border) !important; background: #fff !important;
  color: var(--text) !important; font-weight: 700 !important;
}}
._chips_row .stButton > button:hover {{
  background: rgba(36,32,36,.06) !important;
}}
</style>
""", unsafe_allow_html=True)

# Fila con 3 columnas: [etiqueta] [selector] [chips]
c_lbl, c_sel, c_chips = st.columns([1.1, 1.8, 5.1])
with c_lbl:
    st.markdown("**Ver ronda publicada**")

current_round = st.session_state["rondas_view_select"]
with c_sel:
    sel = st.selectbox(
        label="Ver ronda publicada",
        options=publicadas,
        index=publicadas.index(current_round),
        format_func=lambda i: f"Ronda {i}",
        key="rondas_view_select",
        label_visibility="collapsed",
    )

with c_chips:
    st.markdown("**Ir directo a…**")
    per_row = min(len(publicadas), 12)
    chip_cols = st.columns(per_row, gap="small")

    def _request_jump(i: int):
        st.session_state["rondas_jump_to"] = int(i)

    for idx, i in enumerate(publicadas):
        col = chip_cols[idx % per_row]
        is_active = (i == sel)
        label = f"✓ {i}" if is_active else f"{i}"
        col.button(
            label,
            key=f"chip_R{i}",
            use_container_width=True,
            on_click=_request_jump,
            args=(i,),
        )

st.divider()

# ---------- PDF builder ----------
def build_round_pdf(i: int, table_df: pd.DataFrame, cfg: dict, include_results: bool = True) -> bytes | None:
    """
    Devuelve bytes PDF de la ronda usando reportlab si está disponible,
    y si no, intenta fpdf2 como fallback. Si no hay ninguna, devuelve None.
    include_results=True -> imprime resultado; False -> deja hueco ":".
    """
    # Normalizar datos para la tabla del PDF
    tbl = table_df.copy()
    tbl = tbl[["mesa", "blancas_nombre", "negras_nombre", "resultado_mostrar"]].copy()
    tbl = tbl.fillna("")
    if not include_results:
        tbl["resultado_mostrar"] = ":"  # hueco como en tu plantilla

    # 1) ReportLab
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.units import mm

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=15*mm, bottomMargin=15*mm)

        styles = getSampleStyleSheet()
        H = styles["Heading1"]; H.fontSize = 18; H.leading = 22
        H2 = styles["Heading2"]; H2.fontSize = 26; H2.leading = 30  # RONDA grande
        N = styles["Normal"];   N.fontSize = 12; N.leading = 14

        # Paleta aproximada de tu ejemplo
        verde = colors.HexColor("#d9ead3")
        melocoton = colors.HexColor("#f7e1d5")
        azul = colors.HexColor("#cfe2f3")

        anio = (cfg.get("anio") or "").strip()
        nivel = (cfg.get("nivel") or "").strip()
        linea_fecha = (cfg.get("pdf_fecha") or "").strip()
        linea_hora  = (cfg.get("pdf_hora_lugar") or "").strip()

        # Banda 1 (verde): TORNEO DE AJEDREZ {anio}
        band1 = Table([[Paragraph(f"TORNEO DE AJEDREZ {anio}" if anio else "TORNEO DE AJEDREZ", H)]],
                      colWidths=[doc.width])
        band1.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), verde),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        # Banda 2 (melocotón): RONDA {i}
        band2 = Table([[Paragraph(f"RONDA {i}", H2)]], colWidths=[doc.width])
        band2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), melocoton),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 10),
        ]))

        # Banda 3 (azul): izquierda NIVEL grande, derecha fecha + hora/aula
        right_text = "<br/>".join([t for t in [linea_fecha, linea_hora] if t])
        left_par = Paragraph(f"<b>{nivel}</b>" if nivel else "", ParagraphStyle("L", fontSize=24, leading=28))
        right_par = Paragraph(right_text, ParagraphStyle("R", fontSize=14, leading=18, alignment=1))  # centered
        band3 = Table([[left_par, right_par]], colWidths=[doc.width*0.35, doc.width*0.65])
        band3.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), azul),
            ("BOX", (0,0), (-1,-1), 0.5, colors.black),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
            ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))

        # Título de sección
        sec = Table([[Paragraph("<b>Lista de emparejamientos</b>", styles["Title"])]], colWidths=[doc.width])
        sec.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        # Tabla principal
        data = [["Nº MESA", "BLANCAS", "NEGRAS", "RESULTADO"]] + tbl.values.tolist()
        t = Table(data, colWidths=[20*mm, 60*mm, 60*mm, 25*mm])
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,0), "Helvetica-Bold", 11),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (0,-1), "CENTER"),
            ("ALIGN", (3,0), (3,-1), "CENTER"),
            ("GRID", (0,0), (-1,-1), 0.5, colors.lightgrey),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ]))

        story = [band1, band2, band3, Spacer(1, 6), sec, t]
        doc.build(story)
        return buf.getvalue()
    except Exception:
        pass

    # 2) FPDF (fallback simplificado)
    try:
        from fpdf import FPDF

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=12)

        anio = (cfg.get("anio") or "").strip()
        nivel = (cfg.get("nivel") or "").strip()
        linea_fecha = (cfg.get("pdf_fecha") or "").strip()
        linea_hora  = (cfg.get("pdf_hora_lugar") or "").strip()

        # Bandas simples (sin color de fondo complejo en fpdf para mantenerlo ligero)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, f"TORNEO DE AJEDREZ {anio}" if anio else "TORNEO DE AJEDREZ", ln=1, align="C")
        pdf.set_font("Helvetica", "B", 24); pdf.cell(0, 10, f"RONDA {i}", ln=1, align="C")
        if nivel or linea_fecha or linea_hora:
            pdf.set_font("Helvetica", "", 14)
            pdf.cell(0, 8, nivel, ln=1, align="L")
            pdf.cell(0, 7, linea_fecha, ln=1, align="R")
            pdf.cell(0, 7, linea_hora, ln=1, align="R")
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 14); pdf.cell(0, 8, "Lista de emparejamientos", ln=1, align="C")
        pdf.ln(1)

        # Cabecera tabla
        pdf.set_font("Helvetica", "B", 11)
        headers = ["Nº MESA", "BLANCAS", "NEGRAS", "RESULTADO"]
        widths = [20, 75, 75, 20]
        for h, w in zip(headers, widths):
            pdf.cell(w, 8, h, border=1, align="C")
        pdf.ln(8)

        # Filas
        pdf.set_font("Helvetica", "", 11)
        for _, row in tbl.iterrows():
            cells = [str(row["mesa"]), str(row["blancas_nombre"]), str(row["negras_nombre"]), str(row["resultado_mostrar"])]
            for c, w in zip(cells, widths):
                pdf.cell(w, 7, c[:60], border=1)
            pdf.ln(7)

        return bytes(pdf.output(dest="S"))
    except Exception:
        return None

# ---------- render de UNA sola ronda (la seleccionada) ----------
def render_round(i: int):
    path = round_file(i)
    df = read_csv_safe(path)
    if df is None or df.empty:
        st.warning(f"No hay datos para la Ronda {i}.")
        return

    safe_df = df.copy()
    if "seleccionar" in safe_df.columns:  # columna solo usada en admin
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

    # ordenar por mesa (para vista y export)
    try:
        safe_df["mesa"] = pd.to_numeric(safe_df["mesa"], errors="coerce")
    except Exception:
        pass
    safe_df = safe_df.sort_values(by=["mesa"], na_position="last")

    # ---- BYE y resultado mostrado (badge en RESULTADO) ----
    bye_mask = (
        safe_df["blancas_id"].astype(str).str.upper().eq("BYE")
        | safe_df["blancas_nombre"].astype(str).str.upper().eq("BYE")
        | safe_df["negras_id"].astype(str).str.upper().eq("BYE")
        | safe_df["negras_nombre"].astype(str).str.upper().eq("BYE")
    )

    show_df = safe_df.copy()
    show_df["resultado_mostrar"] = _normalize_result_series(show_df["resultado"])
    show_df.loc[show_df["resultado_mostrar"] == "", "resultado_mostrar"] = "—"
    show_df.loc[bye_mask, "resultado_mostrar"] = show_df["resultado_mostrar"] + "  🟨 BYE"

    # normalizar resultados crudos para export
    safe_df["resultado"] = _normalize_result_series(safe_df["resultado"])

    # ---- TABLA EN PANTALLA (4 columnas limpias) ----
    st.dataframe(
        show_df[["mesa", "blancas_nombre", "negras_nombre", "resultado_mostrar"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "mesa": st.column_config.NumberColumn("Mesa", help="Número de mesa"),
            "blancas_nombre": st.column_config.TextColumn("Blancas"),
            "negras_nombre": st.column_config.TextColumn("Negras"),
            "resultado_mostrar": st.column_config.TextColumn("Resultado"),
        },
    )

    # ---- OPCIÓN PDF: incluir resultados o dejar hueco ----
    include_results = st.checkbox("Incluir resultados en el PDF", value=True, key=f"pdf_include_results_R{i}")

    # ---- DESCARGAS CSV + PDF (misma línea) ----
    export_cols = ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]
    df_export = safe_df[export_cols].copy()

    nivel_slug = _slugify(cfg.get("nivel", ""))
    anio_slug = _slugify(cfg.get("anio", ""))
    base = f"ronda_{i}"
    if nivel_slug or anio_slug:
        base = f"{base}_{nivel_slug}_{anio_slug}"

    # CSV
    buf_csv = io.StringIO()
    df_export.to_csv(buf_csv, index=False, encoding="utf-8")

    # PDF
    pdf_bytes = build_round_pdf(i, show_df, cfg, include_results=include_results)

    col_csv, col_pdf = st.columns(2)
    with col_csv:
        st.download_button(
            label=f"⬇️ CSV · Ronda {i}",
            data=buf_csv.getvalue().encode("utf-8"),
            file_name=f"{base}.csv",
            mime="text/csv",
            use_container_width=True,
            key=f"dl_csv_ronda_{i}",
        )
    with col_pdf:
        if pdf_bytes:
            st.download_button(
                label=f"📄 PDF · Ronda {i}",
                data=pdf_bytes,
                file_name=f"{base}.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_pdf_ronda_{i}",
            )
        else:
            st.caption("📄 PDF no disponible (instala reportlab o fpdf2).")

# pinta solo la ronda seleccionada
render_round(sel)

st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
