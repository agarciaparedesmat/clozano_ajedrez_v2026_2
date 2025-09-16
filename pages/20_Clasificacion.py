
# pages/20_Clasificacion_RESTORED.py
# -*- coding: utf-8 -*-

import io, os, re
from datetime import datetime

import pandas as pd
import streamlit as st

from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from lib.ui import page_header, hero_portada, inject_base_style, sidebar_title_and_nav
from lib.tournament import (
    DATA_DIR, load_config, read_players_from_csv, read_csv_safe,
    list_round_files, round_file, apply_results, compute_standings,
    is_published, format_with_cfg, planned_rounds
)

# -----------------------------------------
# NAV personalizada (mantiene tu estilo)
# -----------------------------------------
sidebar_title_and_nav(
    extras=True,
    items=[
        ("app.py", "♟️ Inicio"),
        ("pages/10_Rondas.py", "🧩 Rondas"),
        ("pages/20_Clasificacion.py", "🏆 Clasificación"),
        ("pages/99_Administracion.py", "🛠️ Administración"),
        ("pages/30_Genially.py", "♞ Genially")
    ]
)

# -----------------------------------------
# Cabecera
# -----------------------------------------
cfg = load_config()
page_header(
    format_with_cfg("🏆 Clasificación — {nivel}", cfg),
    format_with_cfg("Curso {anio} · Solo tiene en cuenta rondas PUBLICADAS", cfg)
)

# -----------------------------------------
# Utilidades locales (compatibles con tu original)
# -----------------------------------------
def slugify(s: str) -> str:
    s = re.sub(r"\s+", "_", str(s).strip())
    s = re.sub(r"[^A-Za-z0-9_\-]+", "", s)
    return s or "torneo"


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


def build_standings_pdf(df_st: pd.DataFrame, cfg: dict, ronda_actual: int | None, show_bh: bool = True) -> bytes | None:
    'Conserva estética de tus PDFs.'
    try:
        VERDE     = colors.HexColor("#d9ead3")
        MELOCOTON = colors.HexColor("#f7e1d5")

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

        linea = f"CLASIFICACIÓN DEL TORNEO (tras ronda {ronda_actual})" if ronda_actual else "CLASIFICACIÓN DEL TORNEO"
        titulo_lista = Table([[Paragraph(linea, H3)]], colWidths=[doc.width])
        titulo_lista.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

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

        widths = [14*mm, 70*mm, 22*mm, 22*mm, 18*mm, 28*mm, 12*mm] if has_bh else [14*mm, 82*mm, 24*mm, 24*mm, 20*mm, 14*mm]
        t = Table(data, colWidths=widths, repeatRows=2)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,0), SERIF_B, 11.5),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("VALIGN", (0,0), (-1,0), "MIDDLE"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 6),
            ("LINEBELOW", (0,0), (-1,0), 1.3, colors.black),
            ("LINEBELOW", (0,1), (-1,1), 0.6, colors.black),
            ("TOPPADDING", (0,1), (-1,1), 0),
            ("BOTTOMPADDING", (0,1), (-1,1), 0),
            ("FONTSIZE", (0,1), (-1,1), 1),
            ("ROWHEIGHTS", (0,1), (-1,1), 2),
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
        return None


def build_crosstable_df_positions(df_st: pd.DataFrame, publicadas: list[int]) -> pd.DataFrame:
    'Cuadro doble entrada por POSICIONES.'
    ids = [str(r.get("id")) for _, r in df_st.iterrows()]
    pos_map = {str(r.get("id")): int(r.get("pos")) for _, r in df_st.iterrows()}
    positions = [pos_map[i] for i in ids]
    mat = pd.DataFrame("", index=positions, columns=positions)

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
            if not wid or not bid or wid not in pos_map or bid not in pos_map:
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

    mat = mat.sort_index().reindex(sorted(mat.columns), axis=1)
    return mat


def build_crosstable_pdf(ct_df: pd.DataFrame, cfg: dict, paper: str = "A4") -> bytes | None:
    'Mantiene tu estética y selector A4/A3.'
    try:
        has_custom = _register_fonts()
        SERIF_B  = "OldStd-B"   if has_custom else "Times-Bold"

        buf = io.BytesIO()
        PAPER_RL = {"A4": A4, "A3": A3}
        page_size = landscape(PAPER_RL.get(paper, A4))
        doc = SimpleDocTemplate(
            buf, pagesize=page_size,
            leftMargin=14*mm, rightMargin=14*mm,
            topMargin=12*mm, bottomMargin=12*mm
        )

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

        band1 = Table([[Paragraph(f"{titulo} {anio}".strip(), H1)]], colWidths=[doc.width])
        band1.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        band2 = Table([[Paragraph(nivel or "", H1)]], colWidths=[doc.width])
        band2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 10),
        ]))

        n = len(ct_df.columns)
        header = ["POS"] + [str(c) for c in ct_df.columns]
        data = [header, [""] * len(header)]
        for idx, row in ct_df.iterrows():
            data.append([str(idx)] + [str(x) if x is not None else "" for x in row.tolist()])

        if n > 0:
            first_w = 16*mm
            rest_w  = max(8*mm, min(12*mm, (doc.width - first_w) / n))
            widths  = [first_w] + [rest_w] * n
        else:
            widths = [doc.width]

        t = Table(data, colWidths=widths, repeatRows=2)
        t.setStyle(TableStyle([
            ("FONT", (0,0), (-1,0), SERIF_B, 11.5),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("ALIGN", (0,0), (-1,0), "CENTER"),
            ("VALIGN", (0,0), (-1,0), "MIDDLE"),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("TOPPADDING", (0,0), (-1,0), 6),
            ("LINEBELOW", (0,0), (-1,0), 1.2, colors.black),
            ("LINEBELOW", (0,1), (-1,1), 0.6, colors.black),
            ("TOPPADDING", (0,1), (-1,1), 0),
            ("BOTTOMPADDING", (0,1), (-1,1), 0),
            ("FONTSIZE", (0,1), (-1,1), 1),
            ("ROWHEIGHTS", (0,1), (-1,1), 2),
            ("LEFTPADDING", (0,2), (-1,-1), 4),
            ("RIGHTPADDING", (0,2), (-1,-1), 4),
            ("ALIGN", (0,2), (0,-1), "CENTER"),
            ("ALIGN", (1,2), (-1,-1), "CENTER"),
            ("VALIGN", (0,2), (-1,-1), "MIDDLE"),
            ("GRID", (0,2), (-1,-1), 0.35, colors.lightgrey),
        ]))

        titulo_lista = Table([[Paragraph("CUADRO DEL TORNEO (por posiciones)", H3)]], colWidths=[doc.width])
        titulo_lista.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("TOPPADDING", (0,0), (-1,-1), 6),
        ]))

        story = [band1, band2, titulo_lista, t]
        doc.build(story, onFirstPage=_draw_frame, onLaterPages=_draw_frame)
        return buf.getvalue()
    except Exception:
        return None


# -----------------------------------------
# Cálculo de standings (como tu flujo original)
# -----------------------------------------
BYE_DEFAULT = 1.0

JUG_PATH = os.path.join(DATA_DIR, "jugadores.csv")
n_plan = planned_rounds(cfg, JUG_PATH)

players = read_players_from_csv(JUG_PATH)
if not players:
    st.info("Aún no hay jugadores cargados.")
    st.stop()

round_nums = sorted(list_round_files(n_plan))
if not round_nums:
    st.info("Aún no hay rondas generadas.")
    st.stop()

publicadas = [i for i in round_nums if is_published(i)]
ronda_actual = max(publicadas) if publicadas else None

for i in publicadas:
    dfp = read_csv_safe(round_file(i))
    players = apply_results(players, dfp, bye_points=BYE_DEFAULT)

df_st = compute_standings(players)

# -----------------------------------------
# Chips/resumen superior
# -----------------------------------------
c1, c2 = st.columns([2, 2])
with c1:
    if ronda_actual is not None:
        st.success(f"⭐ Ronda ACTUAL: **Ronda {ronda_actual}**")
    else:
        st.warning("Sin rondas publicadas.")
with c2:
    st.info(f"📣 Publicadas: **{len(publicadas)} / {n_plan}** ")

st.divider()

# -----------------------------------------
# Toggle BUCHHOLZ y columnas
# -----------------------------------------
st.markdown(f"### Clasificación del torneo (tras ronda {ronda_actual})")
if df_st is None or df_st.empty:
    st.info("Sin datos de clasificación todavía.")
    st.stop()

show_bh = st.checkbox(
    "Mostrar BUCHHOLZ (para desempates)",
    value=st.session_state.get("show_bh", True),
    key="show_bh",
    help="Muestra la columna Buchholz, el PDF con Buchholz y el desglose por rivales."
)
show_bh = bool(st.session_state["show_bh"])

# -----------------------------------------
# ✅ NUEVO: toggle estadísticas avanzadas + progreso
# -----------------------------------------
show_stats = st.toggle("📊 Mostrar estadísticas avanzadas", value=True)

# Progreso (si existe en lib) o cálculo local
try:
    from lib.tournament import get_rank_progress, format_rank_progress
    rank_progress = get_rank_progress(max_rondas=10)
    df_st["Progreso 📈"] = df_st["id"].astype(str).apply(lambda pid: format_rank_progress(rank_progress.get(str(pid), [])))
except Exception:
    # Fallback: calcular posiciones por ronda con compute_standings
    prog_map = {}
    for r in range(1, (ronda_actual or 0) + 1):
        pl = read_players_from_csv(JUG_PATH)
        for i in publicadas:
            if i > r: break
            dfp = read_csv_safe(round_file(i))
            pl = apply_results(pl, dfp, bye_points=BYE_DEFAULT)
        df_r = compute_standings(pl)
        for pos, row in enumerate(df_r.itertuples(), start=1):
            pid = str(row.id)
            prog_map.setdefault(pid, []).append(pos)
    def _fmt(seq): return "→".join(str(x) for x in seq) if seq else ""
    df_st["Progreso 📈"] = df_st["id"].astype(str).apply(lambda pid: _fmt(prog_map.get(str(pid), [])))

# Stats adicionales
if show_stats:
    victorias, blancas, negras = {}, {}, {}
    for r in publicadas:
        dfp = read_csv_safe(round_file(r))
        if dfp is None or dfp.empty:
            continue
        for row in dfp.itertuples():
            b = str(getattr(row, "blancas_id", getattr(row, "blancas", "")))
            n = str(getattr(row, "negras_id", getattr(row, "negras", "")))
            res = str(getattr(row, "resultado", "")).strip()
            if not b or not n or not res or "-" not in res:
                continue
            puntos_b, puntos_n = [p.strip() for p in res.replace("–","-").split("-")]
            blancas[b] = blancas.get(b, 0) + 1
            negras[n] = negras.get(n, 0) + 1
            if puntos_b == "1":
                victorias[b] = victorias.get(b, 0) + 1
            elif puntos_n == "1":
                victorias[n] = victorias.get(n, 0) + 1

    df_st["Victorias 🏆"] = df_st["id"].astype(str).map(victorias).fillna(0).astype(int)
    df_st["⚪ Blancas"]   = df_st["id"].astype(str).map(blancas).fillna(0).astype(int)
    df_st["⚫ Negras"]    = df_st["id"].astype(str).map(negras).fillna(0).astype(int)
    df_st["🎯 Performance"] = ((df_st["puntos"] / df_st["pj"]) * 100).round(1).fillna(0).astype(str) + "%"

# -----------------------------------------
# Mostrar tabla
# -----------------------------------------
cols = ["pos", "nombre", "curso", "grupo", "puntos", "pj"]
if show_bh and "buchholz" in df_st.columns:
    cols = ["pos", "nombre", "curso", "grupo", "puntos", "buchholz", "pj"]

extra_cols = [c for c in ["Progreso 📈","Victorias 🏆","⚪ Blancas","⚫ Negras","🎯 Performance"] if c in df_st.columns]
cols_final = cols + extra_cols

col_config = {
    "pos": st.column_config.NumberColumn("Pos"),
    "nombre": st.column_config.TextColumn("Jugador/a"),
    "curso": st.column_config.TextColumn("Curso"),
    "grupo": st.column_config.TextColumn("Grupo"),
    "puntos": st.column_config.NumberColumn("Puntos"),
    "pj": st.column_config.NumberColumn("PJ"),
}
if "buchholz" in cols_final:
    col_config["buchholz"] = st.column_config.NumberColumn("Buchholz")

st.dataframe(
    df_st[cols_final],
    use_container_width=True, hide_index=True,
    column_config=col_config
)

# -----------------------------------------
# Descargas CSV + PDF
# -----------------------------------------
c_csv, c_pdf = st.columns([1, 1])

with c_csv:
    csv_buf = io.StringIO()
    df_st[cols_final].to_csv(csv_buf, index=False, encoding="utf-8")
    st.download_button(
        "⬇️ Descargar clasificación (CSV)",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name=f"clasificacion_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.csv",
        mime="text/csv",
        use_container_width=True,
    )

with c_pdf:
    pdf_bytes = build_standings_pdf(df_st[cols], cfg, ronda_actual, show_bh=show_bh)
    if isinstance(pdf_bytes, (bytes, bytearray)) and len(pdf_bytes) > 0:
        st.download_button(
            "📄 Descargar clasificación (PDF)",
            data=pdf_bytes,
            file_name=f"clasificacion_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        st.caption("📄 PDF no disponible (instala reportlab).")

st.divider()

# -----------------------------------------
# Cuadro del torneo (doble entrada por posiciones) con botones A4/A3
# -----------------------------------------
if "show_ct" not in st.session_state:
    st.session_state["show_ct"] = False

if st.button("🧮 Mostrar cuadro del torneo", use_container_width=True, key="btn_ctoggle"):
    st.session_state["show_ct"] = not st.session_state["show_ct"]

if st.session_state["show_ct"]:
    with st.expander("Cuadro del torneo (doble entrada por posiciones)", expanded=True):
        try:
            ct_df = build_crosstable_df_positions(df_st, publicadas)
            col_config_ct = {c: st.column_config.TextColumn(str(c), width=30) for c in ct_df.columns}
            st.dataframe(ct_df, use_container_width=False, column_config=col_config_ct)

            c1, c2 = st.columns(2)

            with c1:
                buf_ct = io.StringIO()
                ct_df.to_csv(buf_ct, index=True, encoding="utf-8")
                st.download_button(
                    "⬇️ Descargar cuadro (CSV)",
                    data=buf_ct.getvalue().encode("utf-8"),
                    file_name=f"cuadro_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="dl_ct_csv",
                )

            with c2:
                if "ct_pdf_paper" not in st.session_state:
                    st.session_state["ct_pdf_paper"] = "A4"

                col_dl, col_a4, col_a3 = st.columns([4, 1, 1])
                with col_a4:
                    if st.button("A4", key="ct_paper_a4"):
                        st.session_state["ct_pdf_paper"] = "A4"
                with col_a3:
                    if st.button("A3", key="ct_paper_a3"):
                        st.session_state["ct_pdf_paper"] = "A3"

                paper = st.session_state["ct_pdf_paper"]
                pdf_ct = build_crosstable_pdf(ct_df, cfg, paper=paper)

                with col_dl:
                    if isinstance(pdf_ct, (bytes, bytearray)) and len(pdf_ct) > 0:
                        st.download_button(
                            "📄 Descargar cuadro (PDF)",
                            data=pdf_ct,
                            file_name=f"cuadro_{slugify(cfg.get('nivel',''))}_{slugify(cfg.get('anio',''))}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key="dl_ct_pdf",
                        )
                    else:
                        st.caption("📄 PDF del cuadro no disponible (instala reportlab).")
        except Exception as e:
            st.error(f"No se pudo construir el cuadro: {e}")

# -----------------------------------------
# Desglose de Buchholz (se mantiene)
# -----------------------------------------
if st.session_state.get("show_bh", True):
    with st.expander("📈 Desglose de Buchholz", expanded=False):
        st.markdown("#### 📈  Ver desglose de Buchholz")
        try:
            _opts = {f"{row['nombre']} (Pos {int(row['pos'])}, {row['puntos']} pts)": row["id"] for _, row in df_st.iterrows()}
        except Exception:
            _opts = {str(row["nombre"]): row["id"] for _, row in df_st.iterrows()}

        sel_label = st.selectbox("Jugador", list(_opts.keys()), index=0, key="bh_player_select")

        if st.button("📈  Ver desglose de Buchholz", use_container_width=True, key="btn_bh_breakdown"):
            pid = _opts.get(sel_label)
            if pid and pid in players:
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
                df_bh = pd.DataFrame(rows)
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
