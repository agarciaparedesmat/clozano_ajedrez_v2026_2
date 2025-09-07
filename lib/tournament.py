
import os, json, random
from datetime import datetime
from collections import defaultdict
import pandas as pd

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
    meta["change_log"].append({"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"round": int(round_no) if round_no else 0,"action": action,"actor": actor or "Admin","details": details})
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
        p = {"id": pid,"nombre": str(row.get("nombre","")).strip(),"apellido1": str(row.get("apellido1","")).strip(),
             "apellido2": str(row.get("apellido2","")).strip(),"curso": str(row.get("curso","")).strip(),"grupo": str(row.get("grupo","")).strip(),
             "_score": 0.0,"_opponents": [],"_colors": [],"_had_bye": False,"estado": str(row.get("estado","activo")).strip().lower() or "activo"}
        players.append(p)
    return players

# ---------- Results ----------
WIN=1.0; DRAW=0.5; LOSS=0.0
def parse_bye_points(res_str, default_points=1.0):
    s = (res_str or "").replace(",", ".").strip().upper()
    if s.startswith("BYE0.5") or s.endswith("0.5") or "½" in s: return 0.5
    if s.startswith("BYE1.0") or s.endswith("1.0"): return 1.0
    if s == "BYE": return float(default_points)
    return float(default_points)

def apply_results(players, df_pairs, bye_points=1.0):
    """
    Aplica resultados a la estructura interna de jugadores.
    - Registra oponentes y colores para todas las mesas (si hay IDs válidas).
    - Actualiza _score y **_round_results** SOLO cuando hay un resultado válido.
    - BYE: no añade color, añade _round_results con (0, puntos).
    """
    id2p = {p["id"]: p for p in players}
    if df_pairs is None or df_pairs.empty: return players

    def push_round_result(pid, opp_id, pts):
        pl = id2p.get(pid)
        if pl is None: return
        pl.setdefault("_round_results", []).append((int(opp_id) if isinstance(opp_id,int) else opp_id, float(pts)))

    for _, row in df_pairs.iterrows():
        w = row.get("blancas_id","")
        b = row.get("negras_id","")
        res = str(row.get("resultado","")).strip().upper()

        # BYE
        if str(b).upper() == "BYE":
            try:
                pid = int(w)
            except:
                continue
            bp = parse_bye_points(res, default_points=bye_points)
            if pid in id2p:
                id2p[pid]["_score"] += bp
                id2p[pid]["_had_bye"] = True
                push_round_result(pid, 0, bp)  # oponente 0 = BYE
            continue

        # Mesa normal
        try:
            w = int(w); b = int(b)
        except:
            continue
        if w not in id2p or b not in id2p:  # ids no válidos
            continue

        # Registrar oponentes y colores (independiente del resultado)
        id2p[w]["_opponents"].append(b); id2p[b]["_opponents"].append(w)
        id2p[w]["_colors"].append("W");   id2p[b]["_colors"].append("B")

        # Mapear resultado a puntos
        w_pts = b_pts = None
        if res in ("1-0","1–0","+/-","+/−"):
            w_pts, b_pts = WIN, LOSS
        elif res in ("0-1","0–1","-/+","−/+"):
            w_pts, b_pts = LOSS, WIN
        elif res in ("1/2-1/2","½-½","0.5-0.5","0,5-0,5"):
            w_pts, b_pts = DRAW, DRAW
        elif res in ("BYE1.0","BYE0.5","BYE"):  # por si alguien dejó BYE en mesa normal: ignora
            continue

        # Si no hay resultado reconocido, no sumar ni registrar _round_results
        if w_pts is None or b_pts is None:
            continue

        # Actualizar puntuación y _round_results
        id2p[w]["_score"] += float(w_pts); id2p[b]["_score"] += float(b_pts)
        push_round_result(w, b, w_pts);    push_round_result(b, w, b_pts)

    return players

# ---------- Colors ----------
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

# ---------- Swiss Pairing ----------
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

# ---------- Standings ----------
def compute_standings(players):
    id2score = {p["id"]: p["_score"] for p in players}
    rows = []
    for p in players:
        sb = 0.0; opp_scores = []; prog = 0.0; cum = 0.0
        for (opp_id, res) in p.get("_round_results", []):
            if opp_id != 0:
                opp_scores.append(id2score.get(opp_id, 0.0))
                sb += float(res) * id2score.get(opp_id, 0.0)
            cum += float(res); prog += cum
        buch = sum(opp_scores); buch_c1 = sum(sorted(opp_scores)[1:]) if len(opp_scores) >= 1 else 0.0
        rows.append({"id": p["id"],"nombre": p.get("nombre",""),"apellido1": p.get("apellido1",""),"apellido2": p.get("apellido2",""),"curso": p.get("curso",""),"grupo": p.get("grupo",""),
                     "puntos": round(p["_score"], 2),"buchholz_c1": round(buch_c1, 2),"buchholz": round(buch, 2),"sonneborn_berger": round(sb, 2),"progresivo": round(prog, 2)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(by=["puntos","buchholz_c1","buchholz","sonneborn_berger","progresivo","id"], ascending=[False,False,False,False,False,True])
    return df
