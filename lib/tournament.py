# lib/tournament.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import json
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ============================================================
# Rutas y utilidades básicas
# ============================================================
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

def _ensure_data_dir() -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        pass

_ensure_data_dir()

# ============================================================
# Config / Meta / Log
# ============================================================
CFG_PATH  = os.path.join(DATA_DIR, "config.json")
META_PATH = os.path.join(DATA_DIR, "meta.json")
LOG_PATH  = os.path.join(DATA_DIR, "admin_log.csv")

def load_config() -> dict:
    """Lee config.json o devuelve valores por defecto."""
    if not os.path.exists(CFG_PATH):
        return {"rondas": 5}
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"rondas": 5}

def load_meta() -> dict:
    """Lee meta.json (o dict vacío si no existe / error)."""
    if not os.path.exists(META_PATH):
        return {}
    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_meta(meta: dict) -> None:
    """Guarda meta.json (ignora errores silenciosamente)."""
    try:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def r1_seed() -> Optional[str]:
    """Devuelve la semilla guardada para R1 (si existe)."""
    m = load_meta()
    return m.get("rounds", {}).get("1", {}).get("seed")

def add_log(action: str, round_no: Optional[int], actor: str, message: str) -> None:
    """Anexa una línea al log administrativo en data/admin_log.csv."""
    try:
        cols = ["ts", "accion", "ronda", "actor", "mensaje"]
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "accion": action,
            "ronda": round_no if round_no is not None else "",
            "actor": actor or "",
            "mensaje": message or "",
        }
        exists = os.path.exists(LOG_PATH)
        df = pd.DataFrame([row], columns=cols)
        if not exists:
            df.to_csv(LOG_PATH, index=False, encoding="utf-8")
        else:
            df.to_csv(LOG_PATH, index=False, mode="a", header=False, encoding="utf-8")
    except Exception:
        pass

# ============================================================
# Lectura/Escritura CSV segura
# ============================================================
def read_csv_safe(path: str) -> Optional[pd.DataFrame]:
    """Lee un CSV en UTF-8 devolviendo DataFrame o None si no existe / error."""
    try:
        if not os.path.exists(path):
            return None
        df = pd.read_csv(
            path,
            dtype=str,
            encoding="utf-8",
            keep_default_na=False,
            na_values=[""]
        )
        return df
    except Exception:
        return None

def last_modified(path: str) -> str:
    """Fecha-hora de última modificación (ISO) o '—' si falla."""
    try:
        ts = os.path.getmtime(path)
        return datetime.fromtimestamp(ts).isoformat(sep=" ", timespec="seconds")
    except Exception:
        return "—"

# ============================================================
# Publicación robusta (meta + flag-file)
# ============================================================
def _pub_flag_path(i: int) -> str:
    """Ruta del flag-file para la ronda i."""
    return os.path.join(DATA_DIR, f"published_R{i}.flag")

def is_published(i: int) -> bool:
    """
    True si la ronda i está publicada.
    Prioridad:
      1) meta['rounds'][str(i)]['published'] == True
      2) fallback: existe el flag-file data/published_R{i}.flag
    """
    try:
        meta = load_meta()
        rinfo = meta.get("rounds", {}).get(str(i), {})
        if bool(rinfo.get("published", False)):
            return True
    except Exception:
        pass
    try:
        return os.path.exists(_pub_flag_path(i))
    except Exception:
        return False

def set_published(i: int, value: bool, seed: Optional[str] = None) -> None:
    """
    Marca/deselecciona como publicada la ronda i tanto en meta como en flag-file.
    Si 'seed' viene, se guarda (útil para R1).
    """
    # 1) meta
    try:
        meta = load_meta()
    except Exception:
        meta = {}
    rounds = meta.setdefault("rounds", {})
    r = rounds.setdefault(str(i), {})
    r["published"] = bool(value)
    if seed is not None:
        r["seed"] = seed
    try:
        save_meta(meta)
    except Exception:
        pass
    # 2) flag-file
    flag = _pub_flag_path(i)
    try:
        if value:
            open(flag, "w").close()
        else:
            if os.path.exists(flag):
                os.remove(flag)
    except Exception:
        # opcionalmente podríamos add_log del error
        pass

# ============================================================
# Helpers de rondas (rutas y listado)
# ============================================================
def round_file(i: int) -> str:
    """Ruta al CSV de emparejamientos de la ronda i."""
    return os.path.join(DATA_DIR, f"pairings_R{i}.csv")

def list_round_files(max_rounds: int | None = None) -> List[int]:
    """
    Devuelve la lista de números de ronda para los que existe 'data/pairings_R<i>.csv',
    ordenada ascendentemente. Si max_rounds está definido, filtra hasta ese número.
    """
    rounds = set()
    try:
        for fname in os.listdir(DATA_DIR):
            m = re.fullmatch(r"pairings_R(\d+)\.csv", fname)
            if m:
                rounds.add(int(m.group(1)))
    except Exception:
        return []
    out = sorted(rounds)
    if max_rounds is not None:
        out = [r for r in out if r <= max_rounds]
    return out

# ============================================================
# Nombres y jugadores
# ============================================================
def formatted_name_from_parts(nombre: str, apellido1: str, apellido2: str) -> str:
    """
    Formato para listados: 'Nombre Apellido1 A.' (inicial de apellido2 si existe).
    """
    nombre = (nombre or "").strip()
    a1 = (apellido1 or "").strip()
    a2 = (apellido2 or "").strip()
    ini2 = (a2[0] + ".") if a2 else ""
    full = " ".join([p for p in [nombre, a1, ini2] if p])
    return full.strip()

def read_players_from_csv(path: str) -> Dict[str, dict]:
    """
    Lee jugadores.csv -> dict por id con campos base y acumuladores de torneo.
    Espera columnas: id,nombre,apellido1,apellido2,curso,grupo,estado
    """
    df = read_csv_safe(path)
    if df is None or df.empty:
        return {}
    needed = ["id", "nombre", "apellido1", "apellido2", "curso", "grupo", "estado"]
    for c in needed:
        if c not in df.columns:
            if c == "estado":
                df["estado"] = "activo"
            else:
                df[c] = ""
    players: Dict[str, dict] = {}
    for _, row in df.iterrows():
        pid = str(row["id"]).strip()
        if not pid:
            continue
        players[pid] = {
            "id": pid,
            "nombre": str(row["nombre"]).strip(),
            "apellido1": str(row["apellido1"]).strip(),
            "apellido2": str(row["apellido2"]).strip(),
            "curso": str(row["curso"]).strip(),
            "grupo": str(row["grupo"]).strip(),
            "estado": (str(row["estado"]).strip().lower() or "activo"),
            # acumuladores
            "points": 0.0,
            "opponents": [],      # lista de ids
            "colors": [],         # "W"/"B" por partida jugada
            "had_bye": False,     # recibió BYE alguna vez
        }
    return players

# ============================================================
# Aplicar resultados y clasificación
# ============================================================
def _award_points_for_result(res: str, bye_default: float = 1.0) -> Tuple[float, float, Optional[float]]:
    """
    Devuelve (pts_white, pts_black, bye_points_si_hay).
    - '1-0'      -> (1.0, 0.0, None)
    - '0-1'      -> (0.0, 1.0, None)
    - '1/2-1/2'  -> (0.5, 0.5, None)
    - '+/-'      -> (1.0, 0.0, None) (incomparecencia negras)
    - '-/+'      -> (0.0, 1.0, None) (incomparecencia blancas)
    - 'BYE1.0'   -> (1.0, 0.0, 1.0)   (negras es BYE)
    - 'BYE0.5'   -> (0.5, 0.0, 0.5)
    - 'BYE'      -> (bye_default, 0.0, bye_default)
    - ''/None    -> (0.0, 0.0, None)
    """
    if not res:
        return 0.0, 0.0, None
    res = str(res).strip().upper()
    if res == "1-0": return 1.0, 0.0, None
    if res == "0-1": return 0.0, 1.0, None
    if res in {"1/2-1/2", "1/2–1/2"}: return 0.5, 0.5, None
    if res == "+/-": return 1.0, 0.0, None
    if res == "-/+": return 0.0, 1.0, None
    if res == "BYE1.0": return 1.0, 0.0, 1.0
    if res == "BYE0.5": return 0.5, 0.0, 0.5
    if res == "BYE": return bye_default, 0.0, bye_default
    return 0.0, 0.0, None

def apply_results(players: Dict[str, dict], df_pairs: Optional[pd.DataFrame], bye_points: float = 1.0) -> Dict[str, dict]:
    """
    Aplica los resultados de un CSV de emparejamientos sobre el diccionario de jugadores.
    df_pairs debe tener: mesa,blancas_id,blancas_nombre,negras_id,negras_nombre,resultado
    """
    if df_pairs is None or df_pairs.empty:
        return players

    # Asegurar columnas mínimas
    cols = ["blancas_id", "negras_id", "resultado"]
    for c in cols:
        if c not in df_pairs.columns:
            return players

    for _, row in df_pairs.iterrows():
        wid = str(row["blancas_id"]).strip()
        bid = str(row["negras_id"]).strip()
        res = str(row.get("resultado", "")).strip()

        # BYE: negras_id == 'BYE'
        if bid.upper() == "BYE":
            if wid in players:
                wpts, _, bye_pts = _award_points_for_result(res or "BYE", bye_default=bye_points)
                players[wid]["points"] += float(bye_pts if bye_pts is not None else bye_points)
                players[wid]["had_bye"] = True
                # Color: puedes decidir si cuenta para racha de colores; aquí añadimos "W"
                players[wid]["colors"].append("W")
            continue

        if wid not in players or bid not in players:
            # Algún id no está en jugadores -> saltamos
            continue

        w_add, b_add, _ = _award_points_for_result(res, bye_default=bye_points)
        players[wid]["points"] += float(w_add)
        players[bid]["points"] += float(b_add)

        # Oponentes (si deseas añadir solo con resultado, condiciona a res != "")
        if wid not in players[bid]["opponents"]:
            players[bid]["opponents"].append(wid)
        if bid not in players[wid]["opponents"]:
            players[wid]["opponents"].append(bid)

        # Historial de colores
        players[wid]["colors"].append("W")
        players[bid]["colors"].append("B")

    return players

def compute_standings(players: Dict[str, dict]) -> pd.DataFrame:
    """
    Devuelve un DataFrame de clasificación con:
      pos, id, nombre, curso, grupo, puntos, buchholz, pj
    Orden: puntos desc, buchholz desc, nombre asc
    """
    if not players:
        return pd.DataFrame(columns=["pos","id","nombre","curso","grupo","puntos","buchholz","pj"])

    # Mapa de puntos finales por id:
    pts_map = {pid: float(info.get("points", 0.0)) for pid, info in players.items()}

    rows = []
    for pid, info in players.items():
        opos = info.get("opponents", []) or []
        buch = sum(pts_map.get(oid, 0.0) for oid in opos)
        nombre_fmt = formatted_name_from_parts(info.get("nombre",""), info.get("apellido1",""), info.get("apellido2",""))
        pj = len([c for c in info.get("colors", []) if c in ("W","B")]) + (1 if info.get("had_bye") else 0)
        rows.append({
            "id": pid,
            "nombre": nombre_fmt,
            "curso": info.get("curso",""),
            "grupo": info.get("grupo",""),
            "puntos": round(float(info.get("points", 0.0)), 2),
            "buchholz": round(float(buch), 2),
            "pj": int(pj),
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(by=["puntos","buchholz","nombre"], ascending=[False, False, True]).reset_index(drop=True)
    df.insert(0, "pos", df.index + 1)  # ranking 1..n
    return df

# ============================================================
# Emparejador Suizo (reglas pragmáticas + “no 3 colores seguidos”)
# ============================================================
def _eligible_players(players: Dict[str, dict]) -> List[str]:
    """Jugadores en estado distinto de 'retirado'."""
    ids = []
    for pid, p in players.items():
        if str(p.get("estado", "activo")).lower() != "retirado":
            ids.append(pid)
    return ids

def _has_three_in_a_row(colors: List[str], next_color: str) -> bool:
    """Evita 3 colores seguidos para un mismo jugador."""
    if len(colors) < 2:
        return False
    return colors[-1] == next_color and colors[-2] == next_color

def _choose_bye(candidates: List[str], players: Dict[str, dict]) -> Optional[str]:
    """
    Elige quién recibe BYE:
      - Prioriza quien no lo haya tenido aún
      - Menos puntos
      - Desempate por nombre formateado (estable)
    """
    if not candidates:
        return None
    no_bye = [pid for pid in candidates if not players[pid].get("had_bye", False)]
    pool = no_bye if no_bye else candidates
    pool = sorted(pool, key=lambda pid: (
        players[pid].get("points", 0.0),
        formatted_name_from_parts(
            players[pid].get("nombre",""),
            players[pid].get("apellido1",""),
            players[pid].get("apellido2",""),
        )
    ))
    return pool[0]

def _name_of(players: Dict[str, dict], pid: str) -> str:
    p = players.get(pid, {})
    return formatted_name_from_parts(p.get("nombre",""), p.get("apellido1",""), p.get("apellido2",""))

def swiss_pair_round(players: Dict[str, dict], round_no: int, forced_bye_id: Optional[str] = None) -> pd.DataFrame:
    """
    Genera emparejamientos de la ronda `round_no` (sistema suizo, heurístico).
    Devuelve DataFrame con: mesa,blancas_id,blancas_nombre,negras_id,negras_nombre,resultado

    Reglas:
      - Orden base por puntos desc y nombre estable.
      - Empareja dentro de grupos de puntos (barajando levemente para variedad).
      - Evita repetir oponente, si es posible.
      - Evita 3 colores seguidos por jugador, si es posible.
      - BYE si impar (preferencia: quien no haya tenido BYE y menos puntos).
    Nota: es un emparejador pragmático, no un solver perfecto de suizo.
    """
    # Jugadores activos
    active_ids = _eligible_players(players)

    # Orden base por puntos desc y nombre
    active_ids.sort(key=lambda pid: (-players[pid].get("points", 0.0), _name_of(players, pid)))

    # Agrupar por puntos
    def pts(pid): return players[pid].get("points", 0.0)
    score_groups: Dict[float, List[str]] = {}
    for pid in active_ids:
        score_groups.setdefault(pts(pid), []).append(pid)

    # Barajar dentro del grupo (semilla la controla Admin antes)
    for g in score_groups.values():
        random.shuffle(g)

    # Aplanar grupos (de mayor a menor puntuación)
    grouped: List[str] = []
    for s in sorted(score_groups.keys(), reverse=True):
        grouped.extend(score_groups[s])

    # Si impar -> reservar BYE
    bye_id = None
    if len(grouped) % 2 == 1:
        if forced_bye_id and forced_bye_id in grouped:
            bye_id = forced_bye_id
        else:
            bye_id = _choose_bye(grouped, players)
        if bye_id in grouped:
            grouped.remove(bye_id)

    # Pareo “greedy” con correcciones simples
    pairings: List[Tuple[str, str]] = []
    used = set()
    i = 0
    while i < len(grouped):
        a = grouped[i]
        if a in used:
            i += 1
            continue

        best_j = None
        # 1) intentamos alguien que no haya jugado antes con 'a'
        for j in range(i + 1, len(grouped)):
            b = grouped[j]
            if b in used:
                continue
            if b not in set(players[a].get("opponents", [])):
                best_j = j
                break

        # 2) si no hay, el primer libre que encontremos
        if best_j is None:
            for j in range(i + 1, len(grouped)):
                b = grouped[j]
                if b not in used:
                    best_j = j
                    break

        if best_j is None:
            i += 1
            continue

        b = grouped[best_j]

        # Decidir colores evitando 3 seguidas
        aW_bad = _has_three_in_a_row(players[a].get("colors", []), "W")
        aB_bad = _has_three_in_a_row(players[a].get("colors", []), "B")
        bW_bad = _has_three_in_a_row(players[b].get("colors", []), "W")
        bB_bad = _has_three_in_a_row(players[b].get("colors", []), "B")

        choice = ("W", "B")  # por defecto: a con blancas
        if aW_bad and not aB_bad:
            choice = ("B", "W")
        elif not aW_bad and aB_bad:
            choice = ("W", "B")
        elif aW_bad and aB_bad:
            # si ambos malos, priorizamos evitar conflicto en b
            if bW_bad and not bB_bad:
                choice = ("W", "B")  # b negras
            elif not bW_bad and bB_bad:
                choice = ("B", "W")
        else:
            # ajustar si b tiene conflicto fuerte
            if bW_bad and not bB_bad:
                choice = ("W", "B")
            elif not bW_bad and bB_bad:
                choice = ("B", "W")

        if choice == ("W", "B"):
            pairings.append((a, b))
        else:
            pairings.append((b, a))

        used.add(a)
        used.add(b)
        i += 1

    # Construir DataFrame salida
    rows = []
    mesa = 1
    if bye_id:
        rows.append({
            "mesa": mesa,
            "blancas_id": bye_id,
            "blancas_nombre": _name_of(players, bye_id),
            "negras_id": "BYE",
            "negras_nombre": "BYE",
            "resultado": ""  # luego se podrá marcar BYE1.0 / BYE0.5 / BYE
        })
        mesa += 1

    for w, b in pairings:
        rows.append({
            "mesa": mesa,
            "blancas_id": w,
            "blancas_nombre": _name_of(players, w),
            "negras_id": b,
            "negras_nombre": _name_of(players, b),
            "resultado": ""
        })
        mesa += 1

    df = pd.DataFrame(rows, columns=["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"])
    return df

