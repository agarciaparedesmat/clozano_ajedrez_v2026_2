# pages/10_Rondas.py
# -*- coding: utf-8 -*-
"""
Rondas — Vista pública + descarga PDF/CSV.

Cambios solicitados:
- Fecha y hora/lugar en **una sola línea** y con **tamaño menor**.
- **Recuadro único** que agrupa Título y RONDA.
- **Colores de cabecera parametrizables** vía `config.json`:
    - pdf_header_bg       (fondo de caja Título+Ronda)        — por defecto "#F3F3F0"
    - pdf_header_border   (borde de caja Título+Ronda)         — por defecto "#C9C9C9"
    - pdf_meta_bg         (fondo de línea meta bajo la caja)   — por defecto "#FAFAFA"
Opcionales (si quieres afinar tamaños sin tocar código):
    - pdf_title_size      (por defecto 22)
    - pdf_round_size      (por defecto 20)
    - pdf_meta_size       (por defecto 13)
"""
from __future__ import annotations

import io
import os
import math
import datetime as _dt

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

# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------
def _cfg_colors(cfg: dict) -> dict:
    return {
        "header_bg":    cfg.get("pdf_header_bg", "#F3F3F0"),
        "header_border":cfg.get("pdf_header_border", "#C9C9C9"),
        "meta_bg":      cfg.get("pdf_meta_bg", "#FAFAFA"),
        "title_size":   int(cfg.get("pdf_title_size", 22)),
        "round_size":   int(cfg.get("pdf_round_size", 20)),
        "meta_size":    int(cfg.get("pdf_meta_size", 13)),
    }

def _meta_line(cfg: dict) -> str:
    fecha = (cfg.get("pdf_fecha") or "").strip()
    hl    = (cfg.get("pdf_hora_lugar") or "").strip()
    parts = []
    if cfg.get("nivel"):
        parts.append(f"<b>{cfg.get('nivel')}</b>")
    if fecha and hl:
        parts.append(f"{fecha} — {hl}")
    elif fecha or hl:
        parts.append(fecha or hl)
    return " · ".join(parts)

def _missing_results(df_pairs: pd.DataFrame) -> int:
    if "resultado" not in df_pairs.columns:
        return 0
    series = df_pairs["resultado"].fillna("").astype(str).str.strip()
    return int((series == "").sum())

def _format_names(df_pairs: pd.DataFrame) -> pd.DataFrame:
    # Asegura columnas mínimas esperadas por el motor
    cols_min = ["mesa","blancas_nombre","negras_nombre","resultado"]
    for c in cols_min:
        if c not in df_pairs.columns:
            df_pairs[c] = ""  # crea si faltan
    
    out = df_pairs.copy()
    out = out.sort_values("mesa", ascending=True)
    # Nombre ya viene pre-formateado por tournament.py, lo respetamos.
    out["Mesa"]        = out["mesa"]
    out["Blancas"]     = out["blancas_nombre"]
    out["Resultado"]   = out["resultado"].fillna("")
    out["Negras"]      = out["negras_nombre"]
    return out[["Mesa","Blancas","Resultado","Negras"]]

# ------------------------------------------------------------
# Generación de PDF (ReportLab + fallback fpdf2)
# ------------------------------------------------------------
def _pdf_reportlab(i: int, cfg: dict, df_pairs: pd.DataFrame) -> bytes | None:
    try:
        # Import pesado aquí
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
    except Exception:
        return None

    buf = io.BytesIO()

    # Documento
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=16*mm, rightMargin=16*mm, topMargin=16*mm, bottomMargin=16*mm
    )

    styles = getSampleStyleSheet()
    SERIF   = "Times-Roman"
    SERIF_B = "Times-Bold"

    # Estilos base (títulos)
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontName=SERIF_B, fontSize=22, leading=26, alignment=1, spaceAfter=0)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontName=SERIF_B, fontSize=18, leading=22, alignment=1, spaceAfter=0)
    H3 = ParagraphStyle("H3", parent=styles["Heading3"], fontName=SERIF_B, fontSize=14, leading=18, alignment=1, spaceAfter=6)
    BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontName=SERIF, fontSize=11, leading=14)

    # Paleta y tamaños desde config
    C = _cfg_colors(cfg)
    try:
        HEADER_BG     = colors.HexColor(C["header_bg"])
        HEADER_BORDER = colors.HexColor(C["header_border"])
        META_BG       = colors.HexColor(C["meta_bg"])
    except Exception:
        HEADER_BG     = colors.HexColor("#F3F3F0")
        HEADER_BORDER = colors.HexColor("#C9C9C9")
        META_BG       = colors.HexColor("#FAFAFA")

    H_TITLE = ParagraphStyle("HTITLE", parent=H1, fontSize=C["title_size"], leading=int(C["title_size"]*1.2), alignment=1)
    H_RND   = ParagraphStyle("HRND",   parent=H1, fontSize=C["round_size"], leading=int(C["round_size"]*1.2), alignment=1)
    H_META  = ParagraphStyle("HMETA",  parent=styles["Normal"], fontName=SERIF_B,
                             fontSize=C["meta_size"], leading=int(C["meta_size"]*1.3), alignment=1)

    # Cabeceras
    titulo = (cfg.get("titulo") or "TORNEO DE AJEDREZ").strip()
    anio   = (cfg.get("anio") or "").strip()
    tline  = f"{titulo} {anio}".strip()
    meta   = _meta_line(cfg)

    # Caja superior Título + Ronda
    hdr_tbl = Table(
        [[Paragraph(tline, H_TITLE)],
         [Paragraph(f"RONDA {i}", H_RND)]],
        colWidths=[doc.width]
    )
    hdr_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), HEADER_BG),
        ("BOX",       (0,0), (-1,-1), 0.9, HEADER_BORDER),
        ("ALIGN",     (0,0), (-1,-1), "CENTER"),
        ("VALIGN",    (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,0), 8),
        ("BOTTOMPADDING", (0,0), (-1,0), 6),
        ("TOPPADDING",    (0,1), (-1,1), 10),
        ("BOTTOMPADDING", (0,1), (-1,1), 10),
    ]))

    # Línea meta en una sola línea
    cab = Table([[Paragraph(meta, H_META)]], colWidths=[doc.width])
    cab.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), META_BG),
        ("BOX",        (0,0), (-1,-1), 0.5, HEADER_BORDER),
        ("ALIGN",      (0,0), (-1,-1), "CENTER"),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))

    # Título lista
    titulo_lista = Paragraph("LISTA DE EMPAREJAMIENTOS", H3)

    # Tabla de partidas
    data = _format_names(df_pairs)
    # Cabecera y cuerpo
    tbl = Table([list(data.columns)] + data.values.tolist(), colWidths=[
        18*mm, 70*mm, 22*mm, 70*mm
    ])
    tbl.setStyle(TableStyle([
        # Cabecera
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("TEXTCOLOR",  (0,0), (-1,0), colors.black),
        ("FONTNAME",   (0,0), (-1,0), SERIF_B),
        ("FONTSIZE",   (0,0), (-1,0), 12),
        ("ALIGN",      (0,0), (0,0), "CENTER"),
        ("ALIGN",      (2,0), (2,0), "CENTER"),
        ("LINEABOVE",  (0,0), (-1,0), 1.2, colors.black),   # doble línea visual: arriba y abajo
        ("LINEBELOW",  (0,0), (-1,0), 1.2, colors.black),

        # Cuerpo
        ("FONTNAME",   (0,1), (-1,-1), SERIF),
        ("FONTSIZE",   (0,1), (-1,-1), 11),
        ("ALIGN",      (0,1), (0,-1), "CENTER"),
        ("ALIGN",      (2,1), (2,-1), "CENTER"),
        ("VALIGN",     (0,1), (-1,-1), "MIDDLE"),
        ("GRID",       (0,1), (-1,-1), 0.3, colors.grey),
    ]))

    story = [hdr_tbl, cab, Spacer(1, 6), titulo_lista, tbl]

    def _footer(canvas, doc):
        # Pie simple con fecha de generación
        canvas.saveState()
        canvas.setFont(SERIF, 9)
        ts = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawRightString(doc.pagesize[0]-16*mm, 10*mm, f"Generado {ts}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()

def _pdf_fpdf(i: int, cfg: dict, df_pairs: pd.DataFrame) -> bytes | None:
    try:
        from fpdf import FPDF
    except Exception:
        return None

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Paleta y tamaños
    C = _cfg_colors(cfg)
    x, y, w, h = 15, 10, 180, 26

    # Caja superior con rectángulo
    pdf.set_draw_color(200, 200, 200)
    pdf.rect(x, y, w, h)

    pdf.set_xy(x, y+3)
    titulo = (cfg.get("titulo") or "TORNEO DE AJEDREZ").strip()
    anio   = (cfg.get("anio") or "").strip()
    tline  = f"{titulo} {anio}".strip()

    pdf.set_font("Helvetica", "B", C["title_size"])
    pdf.cell(w, 8, tline, ln=1, align="C")

    pdf.set_x(x)
    pdf.set_font("Helvetica", "B", C["round_size"])
    pdf.cell(w, 10, f"RONDA {i}", ln=1, align="C")

    # Línea meta
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", C["meta_size"])
    meta_text = _meta_line(cfg)
    pdf.cell(0, 7, meta_text, ln=1, align="C")
    pdf.ln(2)

    # Tabla
    data = _format_names(df_pairs)
    col_w = [18, 76, 22, 76]
    # Cabecera
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(col_w[0], 8, "Mesa", border=1, align="C")
    pdf.cell(col_w[1], 8, "Blancas", border=1, align="C")
    pdf.cell(col_w[2], 8, "Res.", border=1, align="C")
    pdf.cell(col_w[3], 8, "Negras", border=1, align="C")
    pdf.ln(8)

    # Cuerpo
    pdf.set_font("Helvetica", "", 11)
    for _, row in data.iterrows():
        pdf.cell(col_w[0], 7, str(row["Mesa"]), border=1, align="C")
        pdf.cell(col_w[1], 7, str(row["Blancas"]), border=1)
        pdf.cell(col_w[2], 7, str(row["Resultado"]), border=1, align="C")
        pdf.cell(col_w[3], 7, str(row["Negras"]), border=1)
        pdf.ln(7)

    # Footer
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "", 9)
    ts = _dt.datetime.now().strftime("%d/%m/%Y %H:%M")
    pdf.cell(0, 10, f"Generado {ts}", 0, 0, "R")

    return pdf.output(dest="S").encode("latin-1", errors="ignore")

def build_round_pdf(i: int, cfg: dict, df_pairs: pd.DataFrame) -> bytes | None:
    """
    Intenta ReportLab; si no está disponible, usa fpdf2; si falla, None.
    """
    pdf = _pdf_reportlab(i, cfg, df_pairs)
    if pdf:
        return pdf
    pdf = _pdf_fpdf(i, cfg, df_pairs)
    return pdf

# ------------------------------------------------------------
# Página
# ------------------------------------------------------------
cfg = load_config()
inject_base_style(cfg.get("bg_color"))

page_header(
    title=format_with_cfg("🧮 Emparejamientos — {nivel}", cfg) or "🧮 Emparejamientos",
    subtitle=format_with_cfg("{subtitulo}", cfg),
)

sidebar_title_and_nav(active="rondas")

# Determinar número de rondas planificado y rondas existentes
JUG_PATH = os.path.join(DATA_DIR, "jugadores.csv")
n_plan   = planned_rounds(cfg, JUG_PATH)
rounds   = list_round_files(n_plan)
publicas = [i for i in rounds if is_published(i)]

if not publicas:
    st.info("Aún no hay rondas publicadas.")
    st.stop()

# Estado seleccionado
sel = st.session_state.get("rondas_view_select", max(publicas))
sel = st.selectbox(
    "Ronda publicada",
    options=publicas,
    index=publicas.index(sel) if sel in publicas else len(publicas)-1,
    key="rondas_view_select",
)

# Carga de datos de la ronda seleccionada
csv_path = round_file(sel)
df_pairs = read_csv_safe(csv_path)
df_print = _format_names(df_pairs)
faltan   = _missing_results(df_pairs)

# Tarjetas resumen
c1, c2, c3 = st.columns(3)
c1.metric("Ronda", sel)
c2.metric("Partidas", len(df_print))
c3.metric("Resultados sin rellenar", faltan)

# Tabla vista
st.dataframe(df_print, use_container_width=True, hide_index=True)

# Descargas
base = f"ronda_{sel:02d}"
c4, c5 = st.columns(2)
with c4:
    st.download_button(
        "⬇️ Descargar CSV",
        data=df_pairs.to_csv(index=False).encode("utf-8"),
        file_name=f"{base}.csv",
        mime="text/csv",
        use_container_width=True,
    )
with c5:
    pdf_bytes = build_round_pdf(sel, cfg, df_pairs)
    if pdf_bytes:
        st.download_button(
            "⬇️ Descargar PDF",
            data=pdf_bytes,
            file_name=f"{base}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.caption("📄 PDF no disponible (instala reportlab o fpdf2).")

st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
