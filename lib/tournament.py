
    import os, json, random
    from datetime import datetime
    from collections import defaultdict
    import pandas as pd
    from io import BytesIO

    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(APP_DIR, "data")
    CONFIG_PATH = os.path.join(APP_DIR, "config.json")
    META_PATH = os.path.join(DATA_DIR, "meta.json")

    # ---------- Config & Meta ----------
    def load_config():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f: return json.load(f)

    def save_config(cfg):
        with open(CONFIG_PATH, "w", encoding="utf-8") as f: json.dump(cfg, f, ensure_ascii=False, indent=2)

    def load_meta():
        if not os.path.exists(META_PATH): return {"rounds":{}, "change_log":[]}
        with open(META_PATH, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {"rounds":{}, "change_log":[]}

    def save_meta(meta):
        with open(META_PATH, "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)

    def add_log(action, round_no, actor, details=""):
        meta = load_meta(); meta.setdefault("change_log", [])
        meta["change_log"].append({
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "round": int(round_no) if round_no else 0,
            "action": action,
            "actor": actor or "Admin",
            "details": details
        })
        save_meta(meta)

    def is_published(round_no):
        meta = load_meta(); return bool(meta.get("rounds", {}).get(str(round_no), {}).get("published", False))

    def set_published(round_no, published=True, seed=None):
        meta = load_meta(); meta.setdefault("rounds", {}); meta["rounds"].setdefault(str(round_no), {})
        meta["rounds"][str(round_no)]["published"] = bool(published)
        if seed is not None: meta["rounds"][str(round_no)]["seed"] = str(seed)
        save_meta(meta)

    def r1_seed():
        meta = load_meta(); return meta.get("rounds", {}).get("1", {}).get("seed", "")

    # ---------- IO Helpers ----------
    def read_csv_safe(path):
        if not os.path.exists(path): return None
        try: return pd.read_csv(path, dtype=str)
        except Exception: return None

    def write_csv(df, path): df.to_csv(path, index=False, encoding="utf-8")

    def last_modified(path):
        try: return datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception: return "—"

    def list_round_files(n_rondas): return [(i, os.path.join(DATA_DIR, f"pairings_R{i}.csv")) for i in range(1, n_rondas+1)]

    # ---------- Names ----------
    def formatted_name_from_parts(nombre, a1, a2):
        nombre = (nombre or '').strip(); a1 = (a1 or '').strip(); a2 = (a2 or '').strip()
        a2i = (a2[0] + '.') if a2 else ''; return " ".join([p for p in [nombre, a1, a2i] if p])

    # ---------- Players ----------
    def read_players_from_csv(csv_path):
        players = []; df = read_csv_safe(csv_path)
        if df is None or df.empty: return players
        for _, row in df.iterrows():
            try: pid = int(str(row.get("id","")).strip())
            except: continue
            p = {
                "id": pid,
                "nombre": str(row.get("nombre","")).strip(),
                "apellido1": str(row.get("apellido1","")).strip(),
                "apellido2": str(row.get("apellido2","")).strip(),
                "curso": str(row.get("curso","")).strip(),
                "grupo": str(row.get("grupo","")).strip(),
                "_score": 0.0,
                "_opponents": [],
                "_colors": [],
                "_had_bye": False,
                "estado": str(row.get("estado","activo")).strip().lower() or "activo"
            }
            players.append(p)
        return players

    # ---------- Pairings & Results ----------
    WIN=1.0; DRAW=0.5; LOSS=0.0

    def parse_bye_points(res_str, default_points=1.0):
        s = (res_str or "").replace(",", ".").strip().upper()
        if s.startswith("BYE0.5") or s.endswith("0.5") or "½" in s: return 0.5
        if s.startswith("BYE1.0") or s.endswith("1.0"): return 1.0
        if s == "BYE": return float(default_points)
        return float(default_points)

    def apply_results(players, df_pairs, bye_points=1.0):
        id2p = {p["id"]: p for p in players}
        if df_pairs is None or df_pairs.empty: return players
        for _, row in df_pairs.iterrows():
            w = row.get("blancas_id",""); b = row.get("negras_id",""); res = str(row.get("resultado","")).strip().upper()
            if str(b).upper() == "BYE":
                try:
                    pid = int(w); bp = parse_bye_points(res, default_points=bye_points)
                    id2p[pid]["_score"] += bp; id2p[pid].setdefault("_round_results", []).append((0, bp)); id2p[pid]["_had_bye"] = True
                except Exception: pass
                continue
            try: w = int(w); b = int(b)
            except Exception: continue
            id2p[w]["_opponents"].append(b); id2p[b]["_opponents"].append(w)
            id2p[w]["_colors"].append("W"); id2p[b]["_colors"].append("B")
            if res in ("1-0","1–0"): id2p[w]["_score"] += WIN; id2p[b]["_score"] += LOSS
            elif res in ("0-1","0–1"): id2p[w]["_score"] += LOSS; id2p[b]["_score"] += WIN
            elif res in ("1/2-1/2","½-½","0.5-0.5","0,5-0,5"): id2p[w]["_score"] += DRAW; id2p[b]["_score"] += DRAW
            elif res in ("+/−","+/-"): id2p[w]["_score"] += WIN; id2p[b]["_score"] += LOSS
            elif res in ("−/+","-/+"): id2p[w]["_score"] += LOSS; id2p[b]["_score"] += WIN
        return players

    def prefer_color(player):
        w = player["_colors"].count("W"); b = player["_colors"].count("B")
        if w > b: return "B"
        if b > w: return "W"
        return None

    def required_color(player):
        c = player["_colors"][-2:]
        if len(c)==2 and c[0]==c[1]=="W": return "B"
        if len(c)==2 and c[0]==c[1]=="B": return "W"
        return None

    def swiss_pair_round(players, round_no, forced_bye_id=None):
        activos = [p for p in players if str(p.get('estado','activo')).lower() != 'retirado']
        forced_bye_player = None
        if forced_bye_id is not None:
            for p in activos:
                if p["id"] == forced_bye_id: forced_bye_player = p; break
            if forced_bye_player: activos = [p for p in activos if p["id"] != forced_bye_id]
        if round_no == 1: random.shuffle(activos)
        groups = defaultdict(list)
        for p in activos: groups[p["_score"]].append(p)
        for sc in groups: groups[sc].sort(key=lambda x: x["id"])
        scores_sorted = sorted(groups.keys(), reverse=True)
        pairings = []
        def pick_opponent(p, pool):
            pref = prefer_color(p); reqp = required_color(p)
            def req_col(pl): return required_color(pl)
            cand_sorted = sorted(pool, key=lambda c: (
                c["id"] in p["_opponents"],
                0 if (reqp is None or req_col(c) != reqp) else 1,
                0 if (pref is None or prefer_color(c) != pref) else 1,
                abs(c["id"] - p["id"])
            ))
            for c in cand_sorted:
                if c["id"] not in p["_opponents"]: return c
            return cand_sorted[0] if cand_sorted else None
        carry = None
        for sc in scores_sorted:
            pool = groups[sc][:]
            if carry: pool.insert(0, carry); carry = None
            if len(pool) % 2 == 1: carry = pool.pop()
            while pool:
                p1 = pool.pop(0); opp = pick_opponent(p1, pool)
                if not opp: carry = p1; break
                pool.remove(opp)
                req1 = required_color(p1); req2 = required_color(opp)
                if req1 == "W" and req2 != "W": white, black = p1, opp
                elif req1 == "B" and req2 != "B": white, black = opp, p1
                elif req2 == "W" and req1 != "W": white, black = opp, p1
                elif req2 == "B" and req1 != "B": white, black = p1, opp
                else:
                    p1pref = prefer_color(p1); opppref = prefer_color(opp)
                    if p1pref == "W" and opppref != "W": white, black = p1, opp
                    elif p1pref == "B" and opppref != "B": white, black = opp, p1
                    else: white, black = (p1, opp) if (p1["id"] <= opp["id"]) else (opp, p1)
                pairings.append((white, black))
        if carry: pairings.append((carry, None))
        if forced_bye_player: pairings.append((forced_bye_player, None))
        rows = []; mesa = 1
        for pr in pairings:
            if pr[1] is None:
                rows.append({"mesa": mesa,"blancas_id": pr[0]["id"],"blancas_nombre": formatted_name_from_parts(pr[0]["nombre"], pr[0]["apellido1"], pr[0]["apellido2"]),"negras_id": "BYE","negras_nombre": "BYE","resultado": "BYE1.0"})
            else:
                w,b = pr
                rows.append({"mesa": mesa,"blancas_id": w["id"],"blancas_nombre": formatted_name_from_parts(w["nombre"], w["apellido1"], w["apellido2"]),"negras_id": b["id"],"negras_nombre": formatted_name_from_parts(b["nombre"], b["apellido1"], b["apellido2"]),"resultado": ""})
            mesa += 1
        return pd.DataFrame(rows)

    # ---------- PDF helpers (lazy imports) ----------
    def _lazy_pdf_imports():
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer
            from reportlab.lib.utils import ImageReader
            from PIL import Image
            return {
                "A4": A4, "mm": mm, "colors": colors,
                "SimpleDocTemplate": SimpleDocTemplate, "Table": Table, "TableStyle": TableStyle, "Spacer": Spacer,
                "ImageReader": ImageReader, "Image": Image
            }
        except Exception as e:
            return None

    def _hex_to_rgb(h): h = h.lstrip("#"); return tuple(int(h[i:i+2], 16)/255 for i in (0,2,4))

    def _faded_watermark_path(path):
        deps = _lazy_pdf_imports()
        if deps is None: return None
        Image = deps["Image"]
        try:
            src = os.path.join(APP_DIR, path)
            if not os.path.exists(src): return None
            dest = os.path.join(APP_DIR, "assets", "_wm_faded.png")
            os.makedirs(os.path.join(APP_DIR, "assets"), exist_ok=True)
            if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(src):
                return dest
            im = Image.open(src).convert("RGBA")
            r,g,b,a = im.split()
            gray = Image.merge("RGB", (r,g,b)).convert("L")
            gray = gray.point(lambda p: int(255 - (255-p)*0.3))
            faded = Image.merge("RGBA", (gray,gray,gray, a))
            alpha = a.point(lambda p: int(p*0.25))
            faded.putalpha(alpha)
            faded.save(dest)
            return dest
        except Exception:
            return None

    def _header_drawer(title1, title2="", title3="", cfg=None):
        deps = _lazy_pdf_imports()
        if deps is None:
            def _draw(*args, **kwargs): pass
            return _draw
        A4 = deps["A4"]; mm = deps["mm"]; colors = deps["colors"]; ImageReader = deps["ImageReader"]
        theme = (cfg or {}).get("pdf_theme", {})
        top_band = theme.get("top_band", "#dff0d8")
        mid_band = theme.get("middle_band", "#f6d6c6")
        lvl_band = theme.get("level_band", "#cfe3ff")
        title_color = theme.get("title_color", "#000000")
        logo_left = (cfg or {}).get("logo_left","")
        logo_right = (cfg or {}).get("logo_right","")

        rgb_top = _hex_to_rgb(top_band)
        rgb_mid = _hex_to_rgb(mid_band)
        rgb_lvl = _hex_to_rgb(lvl_band)
        rgb_text = _hex_to_rgb(title_color)

        def _draw(canv, doc):
            wm = (cfg or {}).get("pdf_watermark","")
            wm_path = _faded_watermark_path(wm) if wm else None
            if wm_path and os.path.exists(wm_path):
                w, h = doc.pagesize
                max_w = 150*mm
                img = ImageReader(wm_path)
                iw, ih = img.getSize()
                aspect = ih/iw
                draw_w = max_w; draw_h = draw_w*aspect
                x = (w - draw_w)/2; y = (h - draw_h)/2
                canv.drawImage(wm_path, x, y, width=draw_w, height=draw_h, mask='auto', preserveAspectRatio=True)

            w, h = doc.pagesize
            band_h = 18*mm
            y = h - band_h
            canv.saveState()
            canv.setFillColorRGB(*rgb_top); canv.rect(0, y, w, band_h, fill=1, stroke=0)
            y2 = y - band_h - 3*mm
            canv.setFillColorRGB(*rgb_mid); canv.rect(0, y2, w, band_h, fill=1, stroke=0)
            y3 = y2 - band_h - 3*mm
            canv.setFillColorRGB(*rgb_lvl); canv.rect(0, y3, w, band_h, fill=1, stroke=0)
            try:
                if logo_left and os.path.exists(os.path.join(APP_DIR, logo_left)):
                    canv.drawImage(os.path.join(APP_DIR, logo_left), 10*mm, y3, width=24*mm, height=24*mm, preserveAspectRatio=True, mask='auto')
            except: pass
            try:
                if logo_right and os.path.exists(os.path.join(APP_DIR, logo_right)):
                    canv.drawImage(os.path.join(APP_DIR, logo_right), w-34*mm, y3, width=24*mm, height=24*mm, preserveAspectRatio=True, mask='auto')
            except: pass
            canv.setFillColorRGB(*rgb_text)
            canv.setFont("Helvetica-Bold", 14); canv.drawCentredString(w/2, y + band_h/2 - 5, title1)
            canv.setFont("Helvetica-Bold", 13); canv.drawCentredString(w/2, y2 + band_h/2 - 5, title2)
            canv.setFont("Helvetica-Bold", 13); canv.drawCentredString(w/2, y3 + band_h/2 - 5, title3)
            canv.restoreState()
        return _draw

    def _story_header_space():
        deps = _lazy_pdf_imports()
        if deps is None: return []
        Spacer = deps["Spacer"]
        return [Spacer(0, 40*deps["mm"])]

    def _table_style(deps):
        TableStyle = deps["TableStyle"]; colors = deps["colors"]
        return TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("TEXTCOLOR", (0,0), (-1,0), colors.black),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,0), 6),
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ])

    def pdf_from_table(title_main, title_mid, title_level, data, cfg, col_widths=None):
        deps = _lazy_pdf_imports()
        if deps is None:
            # Fallback: return a TXT in-memory file explaining missing deps
            buff = BytesIO()
            buff.write(("Faltan dependencias PDF (reportlab/Pillow). instala requirements.txt para exportar.
"
                        f"Título: {title_main}
Subtítulo: {title_mid}
Nivel: {title_level}
").encode("utf-8"))
            buff.seek(0)
            return buff
        SimpleDocTemplate = deps["SimpleDocTemplate"]; Table = deps["Table"]; mm = deps["mm"]
        story = _story_header_space()
        tbl = Table(data, colWidths=col_widths)
        tbl.setStyle(_table_style(deps))
        story.append(tbl)
        header_cb = _header_drawer(title_main, title_mid, title_level, cfg=cfg)
        buff = BytesIO()
        doc = SimpleDocTemplate(buff, pagesize=deps["A4"], leftMargin=15*mm, rightMargin=15*mm, topMargin=12*mm, bottomMargin=12*mm)
        doc.build(story, onFirstPage=header_cb, onLaterPages=header_cb)
        buff.seek(0)
        return buff

    def export_pdf_pairings(round_no, df, cfg):
        nivel = cfg.get("nivel",""); cab = cfg.get("cabecera_pdf",""); anio = cfg.get("anio","")
        title1 = f"{cfg.get('titulo','Torneo de Ajedrez')} {anio}".strip()
        title2 = f"RONDA {round_no}"; title3 = f"{nivel}" + (f" — {cab}" if cab else "")
        data = [["N° MESA","BLANCAS","RESULTADO","NEGRAS"]]
        for _,r in df.iterrows():
            data.append([str(r.get("mesa","")), str(r.get("blancas_nombre","")), str(r.get("resultado","")), str(r.get("negras_nombre",""))])
        return pdf_from_table(title1, title2, title3, data, cfg, col_widths=[20,70,28,70])

    def export_pdf_results(round_no, df, cfg):
        nivel = cfg.get("nivel",""); anio = cfg.get("anio","")
        title1 = f"{cfg.get('titulo','Torneo de Ajedrez')} {anio}".strip()
        title2 = f"RONDA {round_no}"; title3 = f"{nivel} — RESULTADOS"
        data = [["N° MESA","BLANCAS","RESULTADO","NEGRAS"]]
        for _,r in df.iterrows():
            data.append([str(r.get("mesa","")), str(r.get("blancas_nombre","")), str(r.get("resultado","")), str(r.get("negras_nombre",""))])
        return pdf_from_table(title1, title2, title3, data, cfg, col_widths=[20,70,28,70])

    def export_pdf_standings(df, cfg, round_label=""):
        nivel = cfg.get("nivel",""); anio = cfg.get("anio","")
        title1 = f"{cfg.get('titulo','Torneo de Ajedrez')} {anio}".strip()
        title2 = "CLASIFICACIÓN"; title3 = f"{nivel}" + (f" — {round_label}" if round_label else "")
        data = [["Puesto","Nombre","Curso/Grupo","Puntos"]]
        if df is not None and not df.empty:
            show = df.copy()
            show["NombreFmt"] = show.apply(lambda r: formatted_name_from_parts(r.get("nombre",""), r.get("apellido1",""), r.get("apellido2","")), axis=1)
            show["CursoGrupo"] = show.apply(lambda r: f"{r.get('curso','')} {r.get('grupo','')}".strip(), axis=1)
            show = show.reset_index(drop=True)
            for i, r in show.iterrows():
                data.append([str(i+1), r["NombreFmt"], r["CursoGrupo"], str(r.get("puntos",""))])
        return pdf_from_table(title1, title2, title3, data, cfg, col_widths=[18,90,40,20])

    def export_pdf_players(jug_df, cfg):
        nivel = cfg.get("nivel",""); anio = cfg.get("anio","")
        title1 = f"{cfg.get('titulo','Torneo de Ajedrez')} {anio}".strip()
        title2 = f"{nivel}"; title3 = "LISTADO DE JUGADORES"
        data = [["N°","Nombre","Curso/Grupo"]]
        if jug_df is not None and not jug_df.empty:
            j = jug_df.copy()
            j["NombreFmt"] = j.apply(lambda r: formatted_name_from_parts(r.get("nombre",""), r.get("apellido1",""), r.get("apellido2","")), axis=1)
            j["CursoGrupo"] = j.apply(lambda r: f"{r.get('curso','')} {r.get('grupo','')}".strip(), axis=1)
            j = j.sort_values(by=["curso","grupo","apellido1","apellido2","nombre"], na_position="last")
            for idx, r in enumerate(j.itertuples(index=False), start=1):
                data.append([str(idx), getattr(r,"NombreFmt"), getattr(r,"CursoGrupo")])
        return pdf_from_table(title1, title2, title3, data, cfg, col_widths=[12,100,50])
