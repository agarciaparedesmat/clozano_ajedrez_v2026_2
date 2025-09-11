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
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        # Paleta (aprox. plantilla)
        VERDE     = colors.HexColor("#d9ead3")
        MELOCOTON = colors.HexColor("#f7e1d5")
        AZUL      = colors.HexColor("#cfe2f3")

        # Registrar fuentes si existen
        def _register_fonts():
            basep = os.path.join("assets", "fonts")
            ok = False
            try:
                if os.path.exists(os.path.join(basep, "OldStandard-Regular.ttf")):
                    pdfmetrics.registerFont(TTFont("OldStd", os.path.join(basep, "OldStandard-Regular.ttf")))
                    if os.path.exists(os.path.join(basep, "OldStandard-Bold.ttf")):
                        pdfmetrics.registerFont(TTFont("OldStd-B", os.path.join(basep, "OldStandard-Bold.ttf")))
                    ok = True
                if os.path.exists(os.path.join(basep, "PlayfairDisplay-Regular.ttf")):
                    pdfmetrics.registerFont(TTFont("Playfair", os.path.join(basep, "PlayfairDisplay-Regular.ttf")))
                    if os.path.exists(os.path.join(basep, "PlayfairDisplay-Bold.ttf")):
                        pdfmetrics.registerFont(TTFont("Playfair-B", os.path.join(basep, "PlayfairDisplay-Bold.ttf")))
                    ok = True
            except Exception:
                pass
            return ok

        has_custom = _register_fonts()
        SERIF    = "OldStd"   if has_custom else "Times-Roman"
        SERIF_B  = "OldStd-B" if has_custom else "Times-Bold"
        DISPLAY  = "Playfair-B" if has_custom else SERIF_B

        buf = io.BytesIO()
        # Márgenes algo más “editoriales”
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=17*mm, rightMargin=17*mm,
            topMargin=14*mm, bottomMargin=14*mm
        )

        # Marco exterior (sin numeración)
        def _draw_frame(canvas, d):
            canvas.saveState()
            canvas.setStrokeColor(colors.black)
            canvas.setLineWidth(1.1)
            x = doc.leftMargin - 5*mm
            y = doc.bottomMargin - 5*mm
            w = doc.width + 10*mm
            h = doc.height + 10*mm
            canvas.rect(x, y, w, h)
            canvas.restoreState()

        # Estilos con sangría/leading cuidados
        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=SERIF_B, fontSize=18, leading=22, alignment=1, spaceAfter=2)
        H2 = ParagraphStyle("H2", parent=styles["Normal"], fontName=DISPLAY,  fontSize=28, leading=32, alignment=1, spaceAfter=4)
        H3 = ParagraphStyle("H3", parent=styles["Normal"], fontName=SERIF_B, fontSize=16, leading=20, alignment=1, spaceBefore=2, spaceAfter=4)
        BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontName=SERIF, fontSize=11.5, leading=14.2, leftIndent=0)

        titulo = (cfg.get("titulo") or "").strip() 
        anio = (cfg.get("anio") or "").strip()
        nivel = (cfg.get("nivel") or "").strip()
        linea_fecha = (cfg.get("pdf_fecha") or "").strip()
        linea_hora  = (cfg.get("pdf_hora_lugar") or "").strip()

        # Bandas
        band1 = Table([[Paragraph(f"{titulo} {anio}" if titulo and anio else "TORNEO DE AJEDREZ", H1)]],
                      colWidths=[doc.width])
        band1.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), VERDE),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        band2 = Table([[Paragraph(f"RONDA {i}", H1)]], colWidths=[doc.width])
        band2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), MELOCOTON),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 12),
        ]))

        cab_lines = []
        if nivel:       cab_lines.append(f"<b>{nivel}</b>")
        if not include_results:
            if linea_fecha: cab_lines.append(linea_fecha)
            if linea_hora:  cab_lines.append(linea_hora)
        cab_text = "<br/>".join(cab_lines) if cab_lines else ""
        cab = Table([[Paragraph(cab_text, ParagraphStyle("CAB", fontName=SERIF_B, fontSize=20, leading=24, alignment=1))]],
                    colWidths=[doc.width])
        cab.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), AZUL),
            ("BOX", (0,0), (-1,-1), 0.5, colors.black),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 10),
            ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 10),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ]))

        titulo_lista = Table([[Paragraph("RESULTADOS" if include_results else "RESULTADOS" if include_results else "Lista de emparejamientos", H3)]], colWidths=[doc.width])
        titulo_lista.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        # Construir filas: usar Paragraph en nombres para buena ruptura de línea + sangría/padding
        rows = []
        for _, r in tbl.iterrows():
            mesa = str(r["mesa"])
            b = Paragraph(str(r["blancas_nombre_pdf"]), BODY)
            res = Paragraph(str(r["resultado_mostrar"]), ParagraphStyle("RES", parent=BODY, alignment=1))  # centrado
            n = Paragraph(str(r["negras_nombre_pdf"]), BODY)
            rows.append([mesa, b, res, n])

        data = [["Nº MESA", "BLANCAS", "RESULTADO", "NEGRAS"], ["", "", "", ""]] + rows
        widths = [20*mm, (doc.width - 40*mm)/2, 20*mm, (doc.width - 40*mm)/2]

        t = Table(data, colWidths=widths, repeatRows=2)  # repite cabecera si salta de página
        t.setStyle(TableStyle([
            # cabecera
            ("FONT", (0,0), (-1,0), SERIF_B, 11.5),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("VALIGN", (0,0), (-1,0), "MIDDLE"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 6),

            # doble línea real (cabecera → cuerpo)
            ("LINEBELOW", (0,0), (-1,0), 1.3, colors.black),  # 1ª
            ("LINEBELOW", (0,1), (-1,1), 0.6, colors.black),  # 2ª fina

            # fila separadora “fantasma”
            ("TOPPADDING", (0,1), (-1,1), 0),
            ("BOTTOMPADDING", (0,1), (-1,1), 0),
            ("FONTSIZE", (0,1), (-1,1), 1),
            ("ROWHEIGHTS", (0,1), (-1,1), 2),

            # cuerpo: padding y alineaciones
            ("LEFTPADDING", (0,2), (-1,-1), 6),
            ("RIGHTPADDING", (0,2), (-1,-1), 6),
            ("ALIGN", (0,2), (0,-1), "CENTER"),
            ("ALIGN", (2,2), (2,-1), "CENTER"),
            ("VALIGN", (0,2), (-1,-1), "MIDDLE"),

            # rejilla suave
            ("GRID", (0,2), (-1,-1), 0.4, colors.lightgrey),
        ]))

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

            anio = (cfg.get("anio") or "").strip()
            nivel = (cfg.get("nivel") or "").strip()
            linea_fecha = (cfg.get("pdf_fecha") or "").strip()
            linea_hora  = (cfg.get("pdf_hora_lugar") or "").strip()

            # cabeceras centradas
            pdf.set_font("Helvetica", "B", 18); pdf.cell(0, 10, f"TORNEO DE AJEDREZ {anio}" if anio else "TORNEO DE AJEDREZ", ln=1, align="C")
            pdf.set_font("Helvetica", "B", 24); pdf.cell(0, 10, f"RONDA {i}", ln=1, align="C")
            pdf.set_font("Helvetica", "B", 18)
            for ln in ([nivel] + ([] if include_results else [linea_fecha, linea_hora])):
                if ln: pdf.cell(0, 8, ln, ln=1, align="C")
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 16); pdf.cell(0, 8, "RESULTADOS" if include_results else "Lista de emparejamientos", ln=1, align="C"); pdf.ln(1)

            headers = ["Nº MESA", "BLANCAS", "RESULTADO", "NEGRAS"]
            widths = [20, 85, 20, 85]  # un poco más anchas las columnas de nombres
            pdf.set_font("Helvetica", "B", 11)
            x0 = pdf.get_x()
            for h, w in zip(headers, widths): pdf.cell(w, 8, h, border=1, align="C")
            pdf.ln(8)
            # doble línea
            x1 = x0 + sum(widths); y1 = pdf.get_y()
            pdf.set_draw_color(0,0,0); pdf.set_line_width(0.6); pdf.line(x0, y1, x1, y1)
            pdf.set_line_width(0.2); pdf.line(x0, y1 + 1.2, x1, y1 + 1.2)

            pdf.set_font("Helvetica", "", 11)
            for _, r in tbl.iterrows():
                cells = [str(r["mesa"]), str(r["blancas_nombre_pdf"]), str(r["resultado_mostrar"]), str(r["negras_nombre_pdf"])]
                aligns = ["C", "L", "C", "L"]
                for c, w, a in zip(cells, widths, aligns):
                    pdf.cell(w, 7, c[:64], border=1, align=a)
                pdf.ln(7)

            return bytes(pdf.output(dest="S"))
        except Exception:
            return None

#--------- render de UNA sola ronda (la seleccionada) ----------
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
        show_df[["mesa", "blancas_nombre", "resultado_mostrar", "negras_nombre"]],
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
