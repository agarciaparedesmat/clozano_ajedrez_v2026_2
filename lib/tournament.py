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


# arriba, junto a imports Zona horaria y formatos de fecha
from zoneinfo import ZoneInfo
MADRID_TZ = ZoneInfo("Europe/Madrid")

def format_ts_madrid(ts: float, with_seconds: bool = True) -> str:
    """Convierte un timestamp (epoch) a dd/mm/yyyy HH:MM[:SS] en horario de Madrid."""
    from datetime import datetime
    dt = datetime.fromtimestamp(ts, tz=MADRID_TZ)
    fmt = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return dt.strftime(fmt)

def now_madrid(with_seconds: bool = True) -> str:
    """Fecha-hora actual en Madrid, formateada dd/mm/yyyy HH:MM[:SS]."""
    from datetime import datetime
    fmt = "%d/%m/%Y %H:%M:%S" if with_seconds else "%d/%m/%Y %H:%M"
    return datetime.now(tz=MADRID_TZ).strftime(fmt)

# ============================================================
# Rutas y utilidades básicas
# ============================================================


CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
# Si estamos en lib/, BASE_DIR es el padre; si no, es el propio directorio
if os.path.basename(CURRENT_DIR) in ("lib",):
    BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
else:
    BASE_DIR = CURRENT_DIR

DATA_DIR = os.path.join(BASE_DIR, "data")

def _ensure_data_dir():
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

# ====== CONFIG: búsqueda, lectura robusta y depuración ======
_LAST_CONFIG_PATH: Optional[str] = None
_LAST_CONFIG_ERROR: Optional[str] = None
_LAST_CONFIG_RAW: Optional[str] = None

def _config_candidates() -> list[str]:
    # Preferimos data/config.json; si no existe, ./config.json (raíz del proyecto)
    return [
        os.path.join(DATA_DIR, "config.json"),   # data/config.json
        os.path.join(BASE_DIR, "config.json"),   # ./config.json (raíz del proyecto)
        os.path.join(CURRENT_DIR, "config.json") # por si se ejecuta con cwd extraño
    ]


def find_config_file() -> Optional[str]:
    for p in _config_candidates():
        if os.path.isfile(p):
            return p
    return None

def _read_text_try_encodings(path: str) -> tuple[str, str]:
    last_exc = None
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read(), enc
        except Exception as e:
            last_exc = e
    if last_exc:
        raise last_exc
    return "", "utf-8"

def _sanitize_json_like(text: str) -> str:
    """Quita comentarios // y /* */, normaliza comillas “curvas” y elimina caracteres de control.
       También quita comas colgantes antes de } o ]."""
    import re
    # quitar comentarios de una línea y de bloque
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)

    # normalizar comillas curvas a rectas
    text = (text
            .replace("\u201c", '"').replace("\u201d", '"')  # “ ”
            .replace("\u2018", "'").replace("\u2019", "'")) # ‘ ’

    # eliminar caracteres de control (excepto \t \r \n)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text)

    # quitar comas colgantes: ,  }
    text = re.sub(r",\s*(\})", r"\1", text)
    # quitar comas colgantes: ,  ]
    text = re.sub(r",\s*(\])", r"\1", text)

    return text.strip()

def load_config() -> dict:
    """Carga config.json desde data/ o raíz. Tolera comentarios/comas colgantes y BOM."""
    global _LAST_CONFIG_PATH, _LAST_CONFIG_ERROR, _LAST_CONFIG_RAW
    _LAST_CONFIG_PATH = None
    _LAST_CONFIG_ERROR = None
    _LAST_CONFIG_RAW = None

    path = find_config_file()
    if not path:
        return {}

    _LAST_CONFIG_PATH = path
    try:
        raw, enc = _read_text_try_encodings(path)
        _LAST_CONFIG_RAW = raw[:2000]  # vista previa acotada

        # 1º intento: JSON estricto
        try:
            return json.loads(raw)
        except Exception as e1:
            # 2º intento: sanitizar comentarios/comas colgantes
            try:
                clean = _sanitize_json_like(raw)
                return json.loads(clean)
            except Exception as e2:
                _LAST_CONFIG_ERROR = f"Primero {type(e1).__name__}: {e1}; tras sanitizar {type(e2).__name__}: {e2}"
                return {}
    except Exception as e:
        _LAST_CONFIG_ERROR = f"{type(e).__name__}: {e}"
        return {}

def config_path() -> str:
    """Devuelve la ruta efectiva usada para cargar config.json (o '' si no hay)."""
    return _LAST_CONFIG_PATH or ""

def config_debug() -> dict:
    """Datos de depuración para mostrar en Admin."""
    return {
        "path": _LAST_CONFIG_PATH or "",
        "error": _LAST_CONFIG_ERROR or "",
        "raw_preview": (_LAST_CONFIG_RAW or "")[:500],
    }

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
    """Guarda data/meta.json de forma atómica y sin perder campos."""
    try:
        # merge defensiva: siempre partimos de lo actual en disco
        current = load_meta()
        # mezcla superficial (para evitar borrar campos que otro haya escrito)
        if isinstance(current, dict) and isinstance(meta, dict):
            merged = {**current, **meta}
            if "rounds" in current and "rounds" in meta:
                # fusión por ronda
                merged_rounds = current["rounds"].copy()
                for k, v in meta["rounds"].items():
                    merged_rounds[k] = {**merged_rounds.get(k, {}), **v}
                merged["rounds"] = merged_rounds
            meta = merged

        # escritura (mejor si quieres usar un tmp + replace, pero vale así)
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        pass




#def save_meta(meta: dict) -> None:
#    """Guarda meta.json (ignora errores silenciosamente)."""
#    try:
#        with open(META_PATH, "w", encoding="utf-8") as f:
#            json.dump(meta, f, ensure_ascii=False, indent=2)
#    except Exception:
#        pass

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
# --------- Round date helpers (fecha de celebración por ronda) ---------
def set_round_date(i: int, date_iso: str) -> None:
    # Guarda la fecha de celebración (ISO 'YYYY-MM-DD') en meta.json para la ronda i.
    try:
        meta = load_meta()
    except Exception:
        meta = {}
    rounds = meta.setdefault("rounds", {})
    r = rounds.setdefault(str(i), {})
    r["date"] = (date_iso or "").strip()
    try:
        save_meta(meta)
    except Exception:
        pass

def get_round_date(i: int) -> str:
    # Devuelve la fecha ISO 'YYYY-MM-DD' almacenada para la ronda i (o '' si no hay).
    try:
        meta = load_meta()
        return str(meta.get("rounds", {}).get(str(i), {}).get("date", "") or "")
    except Exception:
        return ""

def format_date_es(date_iso: str) -> str:
    # Convierte 'YYYY-MM-DD' -> 'Miércoles 10/11/2025' (sin depender de locale).
    try:
        from datetime import date
        y, m, d = map(int, date_iso.split("-"))
        dt = date(y, m, d)
        dias = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
        nombre = dias[dt.weekday()]
        return f"{nombre} {dt.day:02d}/{dt.month:02d}/{dt.year}"
    except Exception:
        return ""


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
    """Fecha-hora de última modificación en horario Madrid, o '—' si falla."""
    try:
        ts = os.path.getmtime(path)
        return format_ts_madrid(ts, with_seconds=True)
    except Exception:
        return "—"



# ============================================================
# Planificación de rondas (auto por log2(N) o fijo desde config)
# ============================================================
import math

def active_players_count(path: str) -> int:
    """Cuenta jugadores 'activos' en jugadores.csv (estado != 'retirado')."""
    df = read_csv_safe(path)
    if df is None or df.empty:
        return 0
    if "estado" not in df.columns:
        return len(df)
    return int((df["estado"].astype(str).str.lower() != "retirado").sum())

def recommended_rounds(n_players: int) -> int:
    """
    Recomendación típica para suizo sin rating: ceil(log2(N)).
    Ajustes suaves:
      - si N <= 2 -> 1
      - mínimo 3 por defecto (torneo escolar)
    """
    if n_players <= 2:
        return 1
    base = math.ceil(math.log2(max(2, n_players)))
    return max(3, int(base))

def planned_rounds(cfg: dict, players_csv_path: str) -> int:
    """
    Devuelve el nº de rondas planificadas:
      - Si cfg['rondas'] es int > 0 -> usa ese valor.
      - Si cfg['rondas'] es 'auto' o falta -> ceil(log2(N activos)),
        acotado por cfg[min_rondas], cfg[max_rondas] si existen.
    """
    r = cfg.get("rondas", "auto")
    if isinstance(r, int) and r > 0:
        return int(r)

    n = active_players_count(players_csv_path)
    rec = recommended_rounds(n)
    min_r = cfg.get("min_rondas")
    max_r = cfg.get("max_rondas")
    if isinstance(min_r, int):
        rec = max(rec, min_r)
    if isinstance(max_r, int):
        rec = min(rec, max_r)
    return int(rec)

def format_with_cfg(text: str, cfg: dict) -> str:
    """Reemplaza {clave} por cfg['clave'] para cualquier clave presente."""
    if text is None:
        return ""
    def repl(m):
        key = m.group(1)
        return str(cfg.get(key, "") or "")
    return re.sub(r"\{([A-Za-z0-9_]+)\}", repl, str(text))

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
# Normalización de valores de resultado
# ============================================================
def _normalize_result_str(val: Optional[str]) -> str:
    """
    Convierte None/nan/'None'/'nan'/'N/A' en '' y recorta espacios.
    No transforma resultados válidos (1-0, 0-1, 1/2-1/2, +/- , -/+, BYE1.0, BYE0.5, BYE).
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s in {"", "NaN"}:
        return ""
    sl = s.lower()
    if sl in {"none", "nan", "n/a"}:
        return ""
    return s

# ============================================================
# Aplicar resultados y clasificación
# ============================================================
def _award_points_for_result(res: str, bye_default: float = 1.0) -> Tuple[float, float, Optional[float]]:
    """
    Devuelve (pts_white, pts_black, bye_points_si_hay).
    - '1-0'      -> (1.0, 0.0, None)
    - '0-1'      -> (0.0, 1.0, None)
    - '1/2-1/2'  -> (0.5, 0.5, None)
    - '+/-'      -> (1.0, 0.0, None)
    - '-/+'      -> (0.0, 1.0, None)
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
        # --- NORMALIZAR resultado ---
        res = _normalize_result_str(row.get("resultado", ""))

        # BYE: negras_id == 'BYE'
        if bid.upper() == "BYE":
            if wid in players:
                # Si res está vacío, trátalo como 'BYE' con el bye_default indicado
                wpts, _, bye_pts = _award_points_for_result(res if res else "BYE", bye_default=bye_points)
                players[wid]["points"] += float(bye_pts if bye_pts is not None else bye_points)
                players[wid]["had_bye"] = True
                # (opcional) contar BYE como 'W' para el control de rachas de color
                players[wid]["colors"].append("W")
            continue

        if wid not in players or bid not in players:
            # Algún id no está en jugadores -> saltamos
            continue

        w_add, b_add, _ = _award_points_for_result(res, bye_default=bye_points)
        players[wid]["points"] += float(w_add)
        players[bid]["points"] += float(b_add)

        # Oponentes (si prefieres solo cuando haya resultado, condiciona a res != "")
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

# --------------------------
# NUEVO: Seguimiento de progreso ronda a ronda
# --------------------------

def get_rank_progress(max_rondas: int = 7) -> dict[str, list[int]]:
    """
    Devuelve un diccionario:
        { "IDJugador1": [posición R1, R2, ...], ... }

    Si no hay datos suficientes para una ronda, se omite esa posición.
    """
    from lib.tournament import get_standings
    progress = {}
    for ronda in range(1, max_rondas + 1):
        try:
            standings = get_standings(upto_round=ronda)
            for pos, row in enumerate(standings.itertuples(), start=1):
                pid = str(row.id)
                if pid not in progress:
                    progress[pid] = []
                progress[pid].append(pos)
        except Exception:
            # Si hay error (ej: no hay datos suficientes), salta
            continue
    return progress

def format_rank_progress(rank_list: list[int]) -> str:
    """
    Convierte [4, 2, 1, 2] → "4→2→1→2"
    """
    if not rank_list:
        return ""
    return "→".join(str(x) for x in rank_list)


# === Meta: diagnóstico y reparación segura ===
from typing import NamedTuple, Optional
import os, re
import pandas as pd

def _results_empty_count_core(df: Optional[pd.DataFrame]) -> Optional[int]:
    if df is None or df.empty or "resultado" not in df.columns:
        return None
    res = (
        df["resultado"].astype(str).str.strip()
          .replace({"None":"", "none":"", "NaN":"", "nan":"", "N/A":"", "n/a":""})
    )
    return int((res == "").sum())

class MetaDiag(NamedTuple):
    existing_rounds: list[int]
    meta_rounds: list[int]
    missing_in_meta: list[int]
    flag_mismatch: list[int]     # rondas donde meta['published'] != realidad
    closed_mismatch: list[int]   # rondas donde meta['closed'] != (pub && empties==0)
    orphan_flags: list[int]      # flags sin CSV o incoherentes
    summary: dict                # contadores varios

def diagnose_meta() -> MetaDiag:
    meta = load_meta() or {}
    rounds_meta = meta.get("rounds", {}) if isinstance(meta, dict) else {}

    # Rondas con CSV
    try:
        existing = [int(re.findall(r"\d+", f)[0]) for f in os.listdir(DATA_DIR)
                    if re.fullmatch(r"pairings_R\d+\.csv", f)]
    except Exception:
        existing = []
    existing = sorted(existing)

    # Rondas en meta
    meta_rounds = sorted([int(k) for k in rounds_meta.keys() if str(k).isdigit()])

    # Faltantes en meta
    missing = [i for i in existing if str(i) not in rounds_meta]

    flag_mm, closed_mm, orphan = [], [], []

    for i in existing:
        r = rounds_meta.get(str(i), {})
        # Real publicado (lo que “vive” hoy)
        real_pub = is_published(i)
        meta_pub = bool(r.get("published", False))
        if meta_pub != real_pub:
            flag_mm.append(i)

        # Vacíos reales
        dfp = read_csv_safe(round_file(i))
        empties = _results_empty_count_core(dfp)
        real_closed = bool(real_pub and (empties == 0))
        if bool(r.get("closed", False)) != real_closed:
            closed_mm.append(i)

    # Flags huérfanos o inconsistentes (no hay CSV o meta final NO debería publicarse)
    for f in os.listdir(DATA_DIR):
        m = re.fullmatch(r"published_R(\d+)\.flag", f)
        if not m:
            continue
        i = int(m.group(1))
        if i not in existing:
            orphan.append(i)

    return MetaDiag(
        existing_rounds=existing,
        meta_rounds=meta_rounds,
        missing_in_meta=missing,
        flag_mismatch=flag_mm,
        closed_mismatch=closed_mm,
        orphan_flags=sorted(orphan),
        summary={
            "existing": len(existing),
            "in_meta": len(meta_rounds),
            "missing": len(missing),
            "flag_mismatch": len(flag_mm),
            "closed_mismatch": len(closed_mm),
            "orphan_flags": len(orphan),
        }
    )

def repair_meta(
    create_missing: bool = True,
    sync_flags: bool = True,
    fix_closed: bool = True,
    remove_orphan_flags: bool = True,
    preserve_dates: bool = True,
) -> dict:
    """
    Aplica una reparación 'segura':
      - crea entradas faltantes (si existe CSV),
      - sincroniza published (meta + flag) con la realidad actual,
      - recalcula 'closed',
      - elimina flags huérfanos (sin CSV),
      - preserva 'date' existente si faltase en la nueva versión.
    Devuelve un resumen de cambios aplicados.
    """
    diag = diagnose_meta()
    meta = load_meta() or {}
    rounds = meta.setdefault("rounds", {})

    applied = {"created": 0, "published_sync": 0, "closed_fixed": 0, "flags_removed": 0}

    # 1) completar entradas
    if create_missing:
        for i in diag.missing_in_meta:
            rounds.setdefault(str(i), {"published": False, "closed": False})
            applied["created"] += 1

    # 2) published/flags
    if sync_flags:
        for i in diag.existing_rounds:
            real_pub = is_published(i)  # realidad actual
            # deja published en meta + flag coherentes (usa set_published del core)
            set_published(i, real_pub)
            # (set_published ya guarda meta + flag)
            applied["published_sync"] += int(i in diag.flag_mismatch)

    # 3) closed
    if fix_closed:
        for i in diag.existing_rounds:
            dfp = read_csv_safe(round_file(i))
            empties = _results_empty_count_core(dfp)
            real_pub = is_published(i)
            real_closed = bool(real_pub and (empties == 0))
            r = rounds.setdefault(str(i), {})
            if r.get("closed") != real_closed:
                r["closed"] = real_closed
                applied["closed_fixed"] += 1

    # 4) limpiar flags huérfanos
    if remove_orphan_flags:
        for i in diag.orphan_flags:
            fp = os.path.join(DATA_DIR, f"published_R{i}.flag")
            if os.path.exists(fp):
                try:
                    os.remove(fp)
                    applied["flags_removed"] += 1
                except Exception:
                    pass

    # 5) guardar meta (preservando dates si procede)
    if preserve_dates:
        # fusiona preservando date existente cuando no venga
        save_meta(meta)  # save_meta ya mergea por ronda sin perder campos
    else:
        save_meta(meta)

    return {"diag": diag._asdict(), "applied": applied}
