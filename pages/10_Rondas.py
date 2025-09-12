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
    get_round_date,
    format_date_es,
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
    PDF con estética afinada:
    - Old Standard / Playfair si hay TTFs (fallback a Times/Helvetica)
    - Cabeceras centradas (hasta 'Lista de emparejamientos')
    - Resultado en el centro (Mesa | Blancas | RESULTADO | Negras)
    - Doble línea real bajo la cabecera de tabla
    - Marco exterior, sin numeración
    - Nombres con (curso grupo) enriqueciendo desde data/jugadores.csv
    """
    import os, io
    import pandas as pd
    from lib.tournament import DATA_DIR, read_csv_safe

    # ---------- enriquecer (curso/grupo) desde jugadores.csv ----------
    def _pick(cols, row):
        for c in cols:
            if c in row and str(row[c]).strip():
                return str(row[c]).strip()
        return ""

    def _guess_id_col(df: pd.DataFrame):
        for c in ["id", "ID", "Id", "jugador_id", "player_id", "n"]:
            if c in df.columns:
                return c
        return None

    cg_map = {}
    jpath = f"{DATA_DIR}/jugadores.csv"
    jdf = read_csv_safe(jpath)
    if jdf is not None and not jdf.empty:
        jdf = jdf.copy()
        idcol = _guess_id_col(jdf)
        if idcol:
            for _, r in jdf.iterrows():
                pid = str(r.get(idcol, "")).strip()
                if not pid:
                    continue
                curso = _pick(["curso", "nivel", "grado", "anio_curso"], r)
                grupo = _pick(["grupo", "clase", "seccion", "grupo_letra"], r)
                cg_map[pid] = " ".join([p for p in [curso, grupo] if p]).strip()

    base = table_df.copy().fillna("")
    def _name_with_cg(side: str, row: pd.Series) -> str:
        name = str(row.get(f"{side}_nombre", "")).strip()
        if name.upper() == "BYE":
            return name
        # ronda -> columnas propias
        cg_in_row = _pick([f"{side}_curso_grupo", f"{side}_nivel_grupo"], row)
        if not cg_in_row:
            curso = _pick([f"{side}_curso", f"{side}_nivel"], row)
            grupo = _pick([f"{side}_grupo", f"{side}_clase"], row)
            cg_in_row = " ".join([p for p in [curso, grupo] if p]).strip()
        if not cg_in_row:
            pid = str(row.get(f"{side}_id", "")).strip()
            cg_in_row = cg_map.get(pid, "")
        return f"{name} ({cg_in_row})" if cg_in_row else name

    base["blancas_nombre_pdf"] = base.apply(lambda r: _name_with_cg("blancas", r), axis=1)
    base["negras_nombre_pdf"]  = base.apply(lambda r: _name_with_cg("negras",  r), axis=1)

    # Orden de columnas con resultado en el centro
    tbl = base[["mesa", "blancas_nombre_pdf", "resultado_mostrar", "negras_nombre_pdf"]].copy()
    tbl = tbl.fillna("")
    if not include_results:
        tbl["resultado_mostrar"] = ":"

    
# ---------- ReportLab principal ----------
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.units import mm
        import io

        # Fuentes simples y legibles
        styles = getSampleStyleSheet()
        SERIF   = "Helvetica"
        SERIF_B = "Helvetica-Bold"
        DISPLAY = SERIF_B

        H1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=SERIF_B, fontSize=18, leading=22, alignment=1, spaceAfter=2)
        H2 = ParagraphStyle("H2", parent=styles["Normal"], fontName=DISPLAY,  fontSize=28, leading=32, alignment=1, spaceAfter=4)
        H3 = ParagraphStyle("H3", parent=styles["Normal"], fontName=SERIF_B, fontSize=16, leading=20, alignment=1, spaceBefore=2, spaceAfter=4)
        BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontName=SERIF, fontSize=11.5, leading=14.2)

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=17*mm, rightMargin=17*mm, topMargin=14*mm, bottomMargin=14*mm)

        # Bandas
        band1 = Table([[Paragraph(f"{titulo} {anio}" if titulo and anio else "TORNEO DE AJEDREZ", H1)]], colWidths=[doc.width])
        band1.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), VERDE), ("ALIGN", (0,0), (-1,-1), "CENTER"),
                                   ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6)]))

        band2 = Table([[Paragraph(f"RONDA {i}", H1)]], colWidths=[doc.width])
        band2.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), MELOCOTON), ("ALIGN", (0,0), (-1,-1), "CENTER"),
                                   ("BOTTOMPADDING", (0,0), (-1,-1), 12), ("TOPPADDING", (0,0), (-1,-1), 12)]))

        # Cabecera secundaria
        cab_lines = []
        if nivel:       cab_lines.append(f"<b>{nivel}</b>")
        if not include_results:
            if linea_fecha: cab_lines.append(linea_fecha)
            if linea_hora:  cab_lines.append(linea_hora)
        cab_text = "<br/>".join(cab_lines) if cab_lines else ""
        cab = Table([[Paragraph(cab_text, ParagraphStyle("CAB", fontName=SERIF_B, fontSize=20, leading=24, alignment=1))]], colWidths=[doc.width])
        cab.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), AZUL), ("BOX", (0,0), (-1,-1), 0.5, colors.black),
                                 ("VALIGN", (0,0), (-1,-1), "MIDDLE"), ("LEFTPADDING", (0,0), (-1,-1), 10),
                                 ("RIGHTPADDING", (0,0), (-1,-1), 10), ("TOPPADDING", (0,0), (-1,-1), 10),
                                 ("BOTTOMPADDING", (0,0), (-1,-1), 10)]))

        titulo_lista = Table([[Paragraph("RESULTADOS" if include_results else "Lista de emparejamientos", H3)]], colWidths=[doc.width])
        titulo_lista.setStyle(TableStyle([("ALIGN", (0,0), (-1,-1), "CENTER"),
                                          ("BOTTOMPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6)]))

        # Tabla datos
        head = ["Mesa", "Blancas", "Resultado", "Negras"]
        data = [head] + [[str(r["mesa"]), str(r["blancas_nombre_pdf"]), str(r["resultado_mostrar"]), str(r["negras_nombre_pdf"])] for _, r in tbl.iterrows()]
        t = Table(data, colWidths=[18*mm, 73*mm, 22*mm, 73*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("FONTNAME", (0,0), (-1,0), SERIF_B),
            ("FONTSIZE", (0,0), (-1,0), 12),
            ("ALIGN", (0,0), (0,0), "CENTER"),
            ("ALIGN", (2,0), (2,0), "CENTER"),
            ("LINEABOVE", (0,0), (-1,0), 1.2, colors.black),
            ("LINEBELOW", (0,0), (-1,0), 1.2, colors.black),
            ("FONTNAME", (0,1), (-1,-1), SERIF),
            ("FONTSIZE", (0,1), (-1,-1), 11),
            ("ALIGN", (0,1), (0,-1), "CENTER"),
            ("ALIGN", (2,1), (2,-1), "CENTER"),
            ("VALIGN", (0,1), (-1,-1), "MIDDLE"),
            ("GRID", (0,1), (-1,-1), 0.3, colors.lightgrey),
        ]))

        # Marco
        def _draw_frame(canvas, d):
            from reportlab.lib.units import mm as _mm
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1.1)
            x = doc.leftMargin - 5*_mm
            y = doc.bottomMargin - 5*_mm
            w = doc.width + 10*_mm
            h = doc.height + 10*_mm
            canvas.rect(x, y, w, h)
            canvas.restoreState()

        story = [band1, band2, cab, Spacer(1, 6), titulo_lista, t]
        doc.build(story, onFirstPage=_draw_frame, onLaterPages=_draw_frame)
        return buf.getvalue()
    except Exception:
        # ---------- FPDF fallback (simple, sin números) ----------
        try:
            from fpdf import FPDF

            pdf = FPDF(orientation="P", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            # Cabecera título + ronda
            titulo = (cfg.get("titulo") or "TORNEO DE AJEDREZ").strip()
            anio = (cfg.get("anio") or "").strip()
            nivel = (cfg.get("nivel") or "").strip()

            pdf.set_font("Helvetica", "B", 18)
            title_txt = f"{titulo} {anio}".strip() if anio else titulo
            pdf.cell(0, 10, title_txt, ln=1, align="C")
            pdf.set_font("Helvetica", "B", 24)
            pdf.cell(0, 10, f"RONDA {i}", ln=1, align="C")

            # Meta (nivel y, si NO es resultados, fecha—hora en una sola línea)
            pdf.set_font("Helvetica", "B", 14)
            if nivel:
                pdf.cell(0, 8, nivel, ln=1, align="C")
            if not include_results:
                linea_fecha = (cfg.get("pdf_fecha") or "").strip()
                linea_hora  = (cfg.get("pdf_hora_lugar") or "").strip()
                # Per-round date override
                try:
                    _iso = get_round_date(i)
                    if _iso:
                        _fmt = format_date_es(_iso)
                        if _fmt:
                            linea_fecha = _fmt
                except Exception:
                    pass
                meta_line = f"{linea_fecha} — {linea_hora}" if (linea_fecha and linea_hora) else (linea_fecha or linea_hora)
                if meta_line:
                    pdf.set_font("Helvetica", "B", 12)
                    pdf.cell(0, 7, meta_line, ln=1, align="C")
            pdf.ln(2)

            # Título de tabla
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 8, "RESULTADOS" if include_results else "Lista de emparejamientos", ln=1, align="C")
            pdf.ln(1)

            # Cabecera tabla
            col_w = [18, 76, 22, 76]
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(col_w[0], 8, "Mesa", border=1, align="C")
            pdf.cell(col_w[1], 8, "Blancas", border=1, align="C")
            pdf.cell(col_w[2], 8, "Res.", border=1, align="C")
            pdf.cell(col_w[3], 8, "Negras", border=1, align="C")
            pdf.ln(8)

            # Filas
            pdf.set_font("Helvetica", "", 11)
            # Usamos 'tbl' ya formateado arriba (mismos nombres de columnas que en ReportLab)
            for _, row in tbl.iterrows():
                pdf.cell(col_w[0], 7, str(row["mesa"]), border=1, align="C")
                pdf.cell(col_w[1], 7, str(row["blancas_nombre_pdf"]), border=1)
                pdf.cell(col_w[2], 7, str(row["resultado_mostrar"]), border=1, align="C")
                pdf.cell(col_w[3], 7, str(row["negras_nombre_pdf"]), border=1)
                pdf.ln(7)

            return pdf.output(dest="S").encode("latin-1", errors="ignore")

        except Exception:
            return None
