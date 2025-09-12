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

def build_crosstable_df_positions(df_st: pd.DataFrame, publicadas: list[int]) -> pd.DataFrame:
    """Devuelve una tabla de doble entrada indexada por POSICIONES.
    Cada celda es el resultado visto desde la FILA: '1', '½' o '0'.
    Si se han enfrentado varias veces, concatena con ' / '.
    Solo considera rondas PUBLICADAS.
    """
    # Mapa id -> pos (según la clasificación mostrada)
    ids = [str(r.get("id")) for _, r in df_st.iterrows()]
    pos_map = {str(r.get("id")): int(r.get("pos")) for _, r in df_st.iterrows()}

    import pandas as _pd
    positions = [pos_map[i] for i in ids]
    mat = _pd.DataFrame("", index=positions, columns=positions)

    def parse_res(s: str):
        if not s:
            return None, None
        r = str(s).strip().replace("–", "-").replace("—", "-").replace(" ", "")
        r = r.replace("½", "0.5").replace(",", ".")
        if r.upper().startswith("BYE"):
            return None, None
        if r == "1-0":
            return "1", "0"
        if r == "0-1":
            return "0", "1"
        if r in ("0.5-0.5", "0.5-0.5"):
            return "½", "½"
        return None, None

    for rnd in (publicadas or []):
        dfp = read_csv_safe(round_file(rnd))
        if dfp is None or dfp.empty:
            continue
        for _, row in dfp.iterrows():
            wid = str(row.get("blancas_id", "")).strip()
            bid = str(row.get("negras_id", "")).strip()
            res = row.get("resultado", "")
            if not wid or not bid:
                continue
            if wid not in pos_map or bid not in pos_map:
                continue
            sw, sb = parse_res(res)
            if sw is None:
                continue

            pw, pb = pos_map[wid], pos_map[bid]
            prev_wb = mat.at[pw, pb]
            prev_bw = mat.at[pb, pw]
            mat.at[pw, pb] = (prev_wb + " / " if prev_wb else "") + sw
            mat.at[pb, pw] = (prev_bw + " / " if prev_bw else "") + sb

    for pid in ids:
        p = pos_map[pid]
        mat.at[p, p] = "—"

    # Ordenar por posición por si acaso
    mat = mat.sort_index().reindex(sorted(mat.columns), axis=1)
    return mat


def build_standings_pdf(df_st, cfg, ronda_actual, show_bh=True):
    """
    Genera un PDF de CLASIFICACIÓN con la estética de Rondas:
    - Bandas de color, tipografías (Old Standard / Playfair si existen), marco exterior
    - Línea previa a la tabla: 'CLASIFICACIÓN DEL TORNEO (tras ronda N)'
    """
    try:
        # ---------- ReportLab principal ----------
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import io, os

        # Paleta (como en Rondas)
        VERDE     = colors.HexColor("#d9ead3")
        MELOCOTON = colors.HexColor("#f7e1d5")
        AZUL      = colors.HexColor("#cfe2f3")

        # Registrar fuentes (igual que en Rondas)
        def _register_fonts():
            basep = os.path.join("assets", "fonts")
            ok = False
            try:
                if os.path.exists(os.path.join(basep, "OldStandard-Regular.ttf")):
                    pdfmetrics.registerFont(TTFont("OldStd",   os.path.join(basep, "OldStandard-Regular.ttf")))
                    if os.path.exists(os.path.join(basep, "OldStandard-Bold.ttf")):
                        pdfmetrics.registerFont(TTFont("OldStd-B", os.path.join(basep, "OldStandard-Bold.ttf")))
                    ok = True
                if os.path.exists(os.path.join(basep, "PlayfairDisplay-Regular.ttf")):
                    pdfmetrics.registerFont(TTFont("Playfair",   os.path.join(basep, "PlayfairDisplay-Regular.ttf")))
                    if os.path.exists(os.path.join(basep, "PlayfairDisplay-Bold.ttf")):
                        pdfmetrics.registerFont(TTFont("Playfair-B", os.path.join(basep, "PlayfairDisplay-Bold.ttf")))
                    ok = True
            except Exception:
                pass
            return ok

        has_custom = _register_fonts()
        SERIF    = "OldStd"     if has_custom else "Times-Roman"
        SERIF_B  = "OldStd-B"   if has_custom else "Times-Bold"
        DISPLAY  = "Playfair-B" if has_custom else SERIF_B

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            leftMargin=17*mm, rightMargin=17*mm,
            topMargin=14*mm, bottomMargin=14*mm
        )

        # Marco exterior (como en Rondas)
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

        styles = getSampleStyleSheet()
        H1 = ParagraphStyle("H1", parent=styles["Normal"], fontName=SERIF_B, fontSize=18, leading=22, alignment=1, spaceAfter=2)
        H3 = ParagraphStyle("H3", parent=styles["Normal"], fontName=SERIF_B, fontSize=16, leading=20, alignment=1, spaceBefore=2, spaceAfter=4)

        titulo = (cfg.get("titulo") or "TORNEO DE AJEDREZ").strip()
        anio   = (cfg.get("anio") or "").strip()
        nivel  = (cfg.get("nivel") or "").strip()

        # Bandas (como en Rondas)
        band1 = Table([[Paragraph(f"{titulo} {anio}".strip(), H1)]], colWidths=[doc.width])
        band1.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), VERDE),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        band2 = Table([[Paragraph(nivel or "", H1)]], colWidths=[doc.width])
        band2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), MELOCOTON),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 12),
        ]))

        # Línea previa a la tabla
        linea = f"CLASIFICACIÓN DEL TORNEO (tras ronda {ronda_actual})" if ronda_actual else "CLASIFICACIÓN DEL TORNEO"
        titulo_lista = Table([[Paragraph(linea, H3)]], colWidths=[doc.width])
        titulo_lista.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        # Tabla de clasificación (dinámica con/sin Buchholz)
        has_bh = bool(show_bh and ("buchholz" in df_st.columns))
        if has_bh:
            head = ["POS", "JUGADOR/A", "CURSO", "GRUPO", "PTS", "BUCHHOLZ", "PJ"]
        else:
            head = ["POS", "JUGADOR/A", "CURSO", "GRUPO", "PTS", "PJ"]
        data = [head, [""] * len(head)]
        for _, r in df_st.iterrows():
            row = [str(r.get("pos","")), str(r.get("nombre","")), str(r.get("curso","")), str(r.get("grupo","")), str(r.get("puntos",""))]
            if has_bh:
                row.append(str(r.get("buchholz","")))
            row.append(str(r.get("pj","")))
            data.append(row)
        from reportlab.platypus import Table as RLTable
        widths = [14*mm, 70*mm, 22*mm, 22*mm, 18*mm, 28*mm, 12*mm] if has_bh else [14*mm, 82*mm, 24*mm, 24*mm, 20*mm, 14*mm]
        t = RLTable(data, colWidths=widths, repeatRows=2)
        t.setStyle(TableStyle([
            # cabecera
            ("FONT", (0,0), (-1,0), SERIF_B, 11.5),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("VALIGN", (0,0), (-1,0), "MIDDLE"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 6),

            # doble línea real bajo cabecera
            ("LINEBELOW", (0,0), (-1,0), 1.3, colors.black),
            ("LINEBELOW", (0,1), (-1,1), 0.6, colors.black),
            ("TOPPADDING", (0,1), (-1,1), 0),
            ("BOTTOMPADDING", (0,1), (-1,1), 0),
            ("FONTSIZE", (0,1), (-1,1), 1),
            ("ROWHEIGHTS", (0,1), (-1,1), 2),

            # cuerpo
            ("LEFTPADDING", (0,2), (-1,-1), 6),
            ("RIGHTPADDING", (0,2), (-1,-1), 6),
            ("ALIGN", (0,2), (-1,-1), "CENTER"),
            ("ALIGN", (1,2), (1,-1), "LEFT"),
            ("VALIGN", (0,2), (-1,-1), "MIDDLE"),
            ("GRID", (0,2), (-1,-1), 0.4, colors.lightgrey),
        ]))

        story = [band1, band2, titulo_lista, t]
        doc.build(story, onFirstPage=_draw_frame, onLaterPages=_draw_frame)
        return buf.getvalue()

    except Exception:
        # ---------- FPDF fallback ----------
        try:
            from fpdf import FPDF
            pdf = FPDF(orientation="P", unit="mm", format="A4")
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()

            titulo = (cfg.get("titulo") or "TORNEO DE AJEDREZ").strip()
            anio   = (cfg.get("anio") or "").strip()
            nivel  = (cfg.get("nivel") or "").strip()

            pdf.set_font("Helvetica", "B", 18)
            pdf.cell(0, 10, f"{titulo} {anio}".strip(), ln=1, align="C")
            pdf.set_font("Helvetica", "B", 20)
            if nivel:
                pdf.cell(0, 10, nivel, ln=1, align="C")

            linea = f"CLASIFICACIÓN DEL TORNEO (tras ronda {ronda_actual})" if ronda_actual else "CLASIFICACIÓN DEL TORNEO"
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 8, linea, ln=1, align="C")
            pdf.ln(1)

            headers = (["POS","JUGADOR/A","CURSO","GRUPO","PTS","BUCHHOLZ","PJ"] if (show_bh and ("buchholz" in df_st.columns)) else ["POS","JUGADOR/A","CURSO","GRUPO","PTS","PJ"])
            widths  = ([14,70,22,22,18,28,12] if "BUCHHOLZ" in headers else [14,82,24,24,20,14])
            pdf.set_font("Helvetica", "B", 11)
            x0 = pdf.get_x()
            for h, w in zip(headers, widths): pdf.cell(w, 8, h, border=1, align="C")
            pdf.ln(8)
            x1 = x0 + sum(widths); y1 = pdf.get_y()
            pdf.set_draw_color(0,0,0); pdf.set_line_width(0.6); pdf.line(x0, y1, x1, y1)
            pdf.set_line_width(0.2); pdf.line(x0, y1 + 1.2, x1, y1 + 1.2)

            pdf.set_font("Helvetica", "", 11)
            for _, r in df_st.iterrows():
                cells = [str(r.get("pos","")), str(r.get("nombre","")), str(r.get("curso","")), str(r.get("grupo","")), str(r.get("puntos",""))]
                if "BUCHHOLZ" in headers: cells.append(str(r.get("buchholz","")))
                cells.append(str(r.get("pj","")))
                aligns = ["C", "L"] + ["C"]*(len(headers)-2)
                for c, w, a in zip(cells, widths, aligns):
                    pdf.cell(w, 7, (c or "")[:64], border=1, align=a)
                pdf.ln(7)

            return bytes(pdf.output(dest="S"))
        except Exception:
            return None


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

st.markdown(f"### Clasificación del torneo (tras ronda {ronda_actual})")
if df_st is None or df_st.empty:
    st.info("Sin datos de clasificación todavía.")
else:
    
    # Selector para mostrar/ocultar Buchholz
    show_bh = st.checkbox(
        "Mostrar BUCHHOLZ (para desempates)",
        value=st.session_state.get("show_bh", True),
        key="show_bh",
        help="Muestra la columna Buchholz, el PDF con Buchholz y el desglose por rivales."
    )
    show_bh = bool(st.session_state["show_bh"])

    

    # Columnas a mostrar según preferencia
    cols = ["pos", "nombre", "curso", "grupo", "puntos", "pj"]
    if show_bh and "buchholz" in df_st.columns:
        cols = ["pos", "nombre", "curso", "grupo", "puntos", "buchholz", "pj"]

    # column_config dinámico para no referenciar columnas ausentes
    col_config = {
        "pos": st.column_config.NumberColumn("Pos"),
        "nombre": st.column_config.TextColumn("Jugador/a"),
        "curso": st.column_config.TextColumn("Curso"),
        "grupo": st.column_config.TextColumn("Grupo"),
        "puntos": st.column_config.NumberColumn("Puntos"),
        "pj": st.column_config.NumberColumn("PJ"),
    }
    if "buchholz" in cols:
        col_config["buchholz"] = st.column_config.NumberColumn("Buchholz")
    st.dataframe(
        df_st[cols],
        use_container_width=True, hide_index=True,
        column_config=col_config,
    )

    # Descargas CSV + PDF en la misma línea

    c_csv, c_pdf = st.columns([1, 1])

    with c_csv:
        csv_buf = io.StringIO()
        # Si usas selector de columnas (p.ej. cols), usa df_st[cols]
        df_st[cols].to_csv(csv_buf, index=False, encoding="utf-8")
        st.download_button(
            "⬇️ Descargar clasificación (CSV)",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name=f"clasificacion_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with c_pdf:
        # Si usas selector de columnas y/o show_bh, ajusta la llamada:
        # pdf_bytes = build_standings_pdf(df_st[cols], cfg, ronda_actual, show_bh=show_bh)
        pdf_bytes = build_standings_pdf(df_st[cols], cfg, ronda_actual, show_bh=show_bh)

        # ✔️ Comprobación robusta (evita falsos negativos)
        if isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 0:
            st.download_button(
                "📄 Descargar clasificación (PDF)",
                data=pdf_bytes,
                file_name=f"clasificacion_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption("📄 PDF no disponible (instala reportlab o fpdf2).")
  
   


    
    # —— Cuadro del torneo (doble entrada por posiciones) ——
    if "show_ct" not in st.session_state:
        st.session_state["show_ct"] = False

    if st.button("Mostrar cuadro del torneo", use_container_width=True, key="btn_ctoggle"):
        st.session_state["show_ct"] = not st.session_state["show_ct"]

    if st.session_state["show_ct"]:
        with st.expander("Cuadro del torneo (doble entrada por posiciones)", expanded=True):
            try:
                ct_df = build_crosstable_df_positions(df_st, publicadas)
                st.dataframe(ct_df, use_container_width=True)
            except Exception as e:
                st.error(f"No se pudo construir el cuadro: {e}")

    if st.session_state.get("show_bh", True):
        with st.expander("Desglose de Buchholz", expanded=False):
            # ——— Desglose de Buchholz ———
            st.markdown("#### 🔎 Ver desglose de Buchholz")
            try:
                # Opciones: etiqueta visible -> id interno
                _opts = {f"{row['nombre']} (Pos {int(row['pos'])}, {row['puntos']} pts)": row["id"] for _, row in df_st.iterrows()}
            except Exception:
                _opts = {str(row["nombre"]): row["id"] for _, row in df_st.iterrows()}

            sel_label = st.selectbox("Jugador", list(_opts.keys()), index=0, key="bh_player_select")

            if st.button("🔎 Ver desglose de Buchholz", use_container_width=True, key="btn_bh_breakdown"):
                pid = _opts.get(sel_label)
                if pid and pid in players:
                    # Puntos actuales por jugador (tras aplicar rondas publicadas)
                    pts_map = {p: float(info.get("points", 0.0)) for p, info in players.items()}
                    opos = players[pid].get("opponents", []) or []
                    rows = []
                    total = 0.0
                    for oid in opos:
                        info_o = players.get(oid, {})
                        nombre_o = info_o.get("nombre", oid)
                        p = float(pts_map.get(oid, 0.0))
                        total += p
                        rows.append({"Rival": nombre_o, "Puntos actuales": p})
                    import pandas as _pd
                    df_bh = _pd.DataFrame(rows)
                    if df_bh.empty:
                        st.info("Este jugador todavía no tiene rivales para calcular Buchholz.")
                    else:
                        st.dataframe(df_bh, use_container_width=True, hide_index=True,
                                     column_config={
                                         "Rival": st.column_config.TextColumn("Rival"),
                                         "Puntos actuales": st.column_config.NumberColumn("Puntos actuales", format="%.2f"),
                                     })
                        st.metric("Buchholz", f"{total:.2f}")
                else:
                    st.warning("No se ha podido localizar el jugador seleccionado.")


st.divider()
st.caption(format_with_cfg("Vista pública de emparejamientos y resultados — {nivel} ({anio})", cfg))
