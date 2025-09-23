# pages/99_Admin.py
# -*- coding: utf-8 -*-

from __future__ import annotations
import os
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo
from lib.ui import sidebar_title_and_nav, page_header

from lib.ui2 import is_pub, set_pub, results_empty_count, round_status, status_label, get_states
from lib.tournament import (
    DATA_DIR,
    load_config, load_meta, save_meta,
    read_csv_safe, last_modified,
    read_players_from_csv, apply_results, compute_standings,
    swiss_pair_round, formatted_name_from_parts,
    is_published, set_published, r1_seed, add_log,
    planned_rounds, format_with_cfg,  # ya estaban
    set_round_date, get_round_date, format_date_es,
    config_path, config_debug,        # <- añadidos
)

from lib.ui import page_header

import datetime as _dt


import random

# --- Fix para backups ---
import re  # necesario para re.sub en _make_backup_local

# Asegurar BASE_DIR para rutas relativas dentro del ZIP
try:
    from lib.tournament import BASE_DIR as _TB_BASE_DIR
    BASE_DIR = _TB_BASE_DIR
except Exception:
    # Fallback: carpeta padre de data/
    BASE_DIR = os.path.dirname(DATA_DIR)

# --- Defaults para el analizador estático (Pylance) ---
N_ROUNDS = None  # se resuelve en tiempo de ejecución vía get_n_rounds()
JUG_PATH = os.path.join(DATA_DIR, "jugadores.csv")

def _log_msg(msg: str) -> str:
    # Respaldo: si aún no hay cfg o formateador disponible
    try:
        return format_with_cfg(f"[{{nivel}}][{{anio}}] {msg}", get_cfg())
    except Exception:
        return str(msg)

# Normaliza la serie de resultados para que None/nan/espacios queden como vacío ""
def _normalize_result_series(s):
    return (
        s.astype(str)
         .str.strip()
         .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )


# Lista de rondas publicadas existentes (según flags/meta)
def published_rounds_list() -> list[int]:
    try:
        n = get_n_rounds()
    except Exception:
        n = 0
    res = []
    for i in range(1, n + 1):
        try:
            if os.path.exists(round_file(i)) and is_pub(i):
                res.append(i)
        except Exception:
            # ante cualquier problema, seguimos
            pass
    return res


# Salvaguarda: si por orden de carga no existiera is_pub, define un fallback mínimo
if 'is_pub' not in globals():
    def is_pub(i: int) -> bool:
        try:
            if is_published(i):
                return True
        except Exception:
            pass
        return os.path.exists(os.path.join(DATA_DIR, f"published_R{i}.flag"))

from lib.tournament import DATA_DIR, load_config, config_path, planned_rounds, round_file


def _save_meta_preserving_dates(meta_new: dict):
    """Guarda meta.json preservando dates ya existentes si meta_new no las trae."""
    try:
        current = load_meta() or {}
        cur_rounds = current.get("rounds", {}) if isinstance(current, dict) else {}
        new_rounds = meta_new.setdefault("rounds", {}) if isinstance(meta_new, dict) else {}

        # Preservar date existentes si la nueva versión no trae valor
        for k, old_r in cur_rounds.items():
            if isinstance(old_r, dict) and "date" in old_r:
                nr = new_rounds.setdefault(k, {})
                if not nr.get("date"):
                    nr["date"] = old_r["date"]

        save_meta(meta_new)
    except Exception as e:
        st.error(f"Fallo al guardar meta preservando fechas: {e}")


# =========================
# Helpers robustos de configuración/estado
# =========================
def get_cfg() -> dict:
    try:
        return cfg  # seguir usando global si ya está
    except Exception:
        return load_config()

def get_config_path() -> str:
    try:
        return config_path()
    except Exception:
        return ""

def get_jug_path() -> str:
    import os
    return os.path.join(DATA_DIR, "jugadores.csv")

def get_n_rounds() -> int:
    try:
        return int(N_ROUNDS)
    except Exception:
        pass
    try:
        _cfg = get_cfg()
        _jug = get_jug_path()
        return int(planned_rounds(_cfg, _jug))
    except Exception:
        return 0


# ===== Helpers Copias/Restore =====
def _bk_dir() -> str:
    # Carpeta local de backups
    d = os.path.join(DATA_DIR, "backups")
    os.makedirs(d, exist_ok=True)
    return d

def _now_tag() -> str:
    import datetime as _dt
    ## 2025-09-16_14-33-05
    #return _dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # Nombre de archivo: dd-mm-aaaa_HH-MM-SS (seguro en Windows/macOS/Linux)
    return _dt.datetime.now(tz=ZoneInfo("Europe/Madrid")).strftime("%d-%m-%Y_%H-%M-%S")

def _safe_zip_namelist(zf):
    # Evita "zip-slip" (entradas con rutas absolutas o que suben directorios)
    names = []
    for n in zf.namelist():
        if n.startswith("/") or ".." in n.replace("\\", "/"):
            continue
        names.append(n)
    return names

def _manifest(make: bool, label: str = "", note: str = "", extra: dict | None = None) -> dict:
    # Metadatos del backup
    m = {
        "kind": "tournament-backup",
        "version": 1,
        "created_at": _dt.datetime.now(tz=ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M:%S"),
        "label": label or "",
        "note": note or "",
    }
    if extra:
        m.update(extra)
    return m

def _collect_paths_for_backup(n_rounds: int | None = None) -> list[str]:
    # Ficheros clave a incluir; rounds dinámicas
    paths = [
        os.path.join(BASE_DIR, "config.json"),
        os.path.join(DATA_DIR, "jugadores.csv"),
        os.path.join(DATA_DIR, "standings.csv"),
        os.path.join(DATA_DIR, "meta.json"),
        os.path.join(DATA_DIR, "admin_log.csv"),
    ]
    try:
        if n_rounds is None:
            n_rounds = get_n_rounds()
    except Exception:
        n_rounds = 0
    for i in range(1, (n_rounds or 0) + 1):
        p = round_file(i)
        if os.path.exists(p):
            paths.append(p)
    # filtra existentes
    # incluir flags de publicación si existen (opcional)
    try:
        import re
        for i in range(1, (n_rounds or 0) + 1):
            pflag = os.path.join(DATA_DIR, f"published_R{i}.flag")
            if os.path.exists(pflag):
                paths.append(pflag)
    except Exception:
        pass
    
    return [p for p in paths if p and os.path.exists(p)]

def _write_zip(paths: list[str], out_path: str, manifest: dict):
    import zipfile, io, json
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # manifest
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for p in paths:
            try:
                arc = os.path.relpath(p, BASE_DIR)  # relativo al proyecto
                z.write(p, arcname=arc)
            except Exception:
                # fallback sin relpath
                z.write(p, arcname=os.path.basename(p))

def _restore_zip(
    fileobj,
    pre_snapshot: bool = True,
    preserve_dates: bool = True,
    clean_extra_pairings: bool = True,
    clean_extra_flags: bool = True,
    recalc_closed: bool = True,
) -> tuple[bool, str]:
    """
    Restaura desde un ZIP subido o una ruta.
    - pre_snapshot: crea un backup automático antes de restaurar.
    - preserve_dates: si el ZIP no trae 'date', preserva la actual.
    - clean_extra_pairings: elimina pairings_R*.csv que no estén en el ZIP.
    - clean_extra_flags: elimina published_R*.flag que no correspondan al meta restaurado.
    - recalc_closed: recalcula el campo 'closed' en meta.json restaurado.
    """
    import zipfile, tempfile, shutil, json, re

    # 0) Snapshot de seguridad
    if pre_snapshot:
        try:
            _make_backup_local(label="auto_pre_restore", note="Backup automático antes de restaurar.")
        except Exception:
            pass

    # 1) Abrir y validar ZIP
    try:
        zf = zipfile.ZipFile(fileobj)
    except Exception as e:
        return False, f"ZIP inválido: {e}"

    names = _safe_zip_namelist(zf)
    if "manifest.json" not in names:
        return False, "El ZIP no contiene manifest.json (no parece un backup válido)."
    try:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("kind") != "tournament-backup":
            return False, "El manifest no es de tipo 'tournament-backup'."
    except Exception as e:
        return False, f"Manifest ilegible: {e}"

    # 2) Extraer en tmp
    tmpdir = tempfile.mkdtemp(prefix="restore_")
    try:
        zf.extractall(tmpdir, members=names)

        # --- Mapa de ficheros estándar a restaurar
        candidates = [
            ("config.json", os.path.join(BASE_DIR, "config.json")),
            (os.path.join("data", "jugadores.csv"), os.path.join(DATA_DIR, "jugadores.csv")),
            (os.path.join("data", "standings.csv"), os.path.join(DATA_DIR, "standings.csv")),
            (os.path.join("data", "meta.json"), os.path.join(DATA_DIR, "meta.json")),
            (os.path.join("data", "admin_log.csv"), os.path.join(DATA_DIR, "admin_log.csv")),
        ]

        # Pairings del ZIP
        pairings_in_zip = set()
        for n in names:
            if n.startswith("data/") and re.match(r"data/pairings_R\d+\.csv$", n):
                pairings_in_zip.add(os.path.basename(n))
                candidates.append((n, os.path.join(DATA_DIR, os.path.basename(n))))

        # Flags del ZIP (si existen en el backup)
        flags_in_zip = set()
        for n in names:
            if n.startswith("data/") and re.match(r"data/published_R\d+\.flag$", n):
                flags_in_zip.add(os.path.basename(n))
                candidates.append((n, os.path.join(DATA_DIR, os.path.basename(n))))

        # Limpieza de pairings sobrantes
        if clean_extra_pairings:
            try:
                existing = [f for f in os.listdir(DATA_DIR) if re.match(r"pairings_R\d+\.csv$", f)]
                for f in existing:
                    if f not in pairings_in_zip:
                        try:
                            os.remove(os.path.join(DATA_DIR, f))
                        except Exception:
                            pass
            except Exception:
                pass

        # Copiar/mezclar ficheros
        meta_dest = os.path.join(DATA_DIR, "meta.json")
        for rel, dest in candidates:
            src = os.path.join(tmpdir, rel) if not os.path.isabs(rel) else rel
            if not os.path.exists(src):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)

            if preserve_dates and dest == meta_dest and os.path.exists(dest):
                # fusionar 'date' desde el meta actual
                try:
                    with open(dest, "r", encoding="utf-8") as f: cur = json.load(f)
                except Exception:
                    cur = {}
                try:
                    with open(src, "r", encoding="utf-8") as f: neu = json.load(f)
                except Exception:
                    neu = {}
                cur_rounds = cur.get("rounds", {}) if isinstance(cur, dict) else {}
                neu_rounds = neu.get("rounds", {}) if isinstance(neu, dict) else {}
                for k, old_r in cur_rounds.items():
                    if isinstance(old_r, dict) and "date" in old_r:
                        nr = neu_rounds.setdefault(k, {})
                        if not nr.get("date"):
                            nr["date"] = old_r["date"]
                neu["rounds"] = neu_rounds
                tmpw = dest + ".tmp"
                with open(tmpw, "w", encoding="utf-8") as f:
                    json.dump(neu, f, ensure_ascii=False, indent=2)
                os.replace(tmpw, dest)
            else:
                # overwrite directo
                shutil.copy2(src, dest)

        # 3) Re‐sincronizar FLAGS con el meta restaurado
        #    (esto garantiza que is_pub() refleje el estado del backup)
        #    Nota: aunque hayamos copiado flags desde el ZIP, este paso los rehace
        #    según meta restaurado, que es la fuente de verdad del backup.
        try:
            import json
            with open(meta_dest, "r", encoding="utf-8") as f:
                meta_after = json.load(f)
        except Exception:
            meta_after = {}

        rounds_meta = meta_after.get("rounds", {}) if isinstance(meta_after, dict) else {}
        # Rondas existentes según CSVs actuales
        existing_pairings = []
        try:
            existing_pairings = [
                int(re.findall(r"\d+", f)[0])
                for f in os.listdir(DATA_DIR)
                if re.match(r"pairings_R\d+\.csv$", f)
            ]
        except Exception:
            existing_pairings = []

        # Limpiar flags sobrantes si procede
        if clean_extra_flags:
            try:
                for f in os.listdir(DATA_DIR):
                    if re.match(r"published_R\d+\.flag$", f):
                        i = int(re.findall(r"\d+", f)[0])
                        # Si la ronda no existe o en meta no está publicada, eliminar flag
                        published_meta = bool(rounds_meta.get(str(i), {}).get("published", False))
                        if (i not in existing_pairings) or not published_meta:
                            try:
                                os.remove(os.path.join(DATA_DIR, f))
                            except Exception:
                                pass
            except Exception:
                pass

        # Crear/asegurar flags que dicta el meta restaurado
        for i in existing_pairings:
            published_meta = bool(rounds_meta.get(str(i), {}).get("published", False))
            fp = os.path.join(DATA_DIR, f"published_R{i}.flag")
            try:
                if published_meta:
                    open(fp, "w").close()
                else:
                    if os.path.exists(fp):
                        os.remove(fp)
            except Exception:
                pass

        # 4) Recalcular 'closed' para que cuadre con (published + sin vacíos)
        if recalc_closed:
            cambios = 0
            for i in existing_pairings:
                pub = bool(rounds_meta.get(str(i), {}).get("published", False))
                try:
                    dfp = read_csv_safe(round_file(i))
                    vacios = results_empty_count(dfp) if dfp is not None else None
                except Exception:
                    vacios = None
                closed_real = bool(pub and (vacios == 0))
                r = rounds_meta.setdefault(str(i), {})
                if r.get("closed") != closed_real:
                    r["closed"] = closed_real
                    cambios += 1
            # Escribir meta ajustado
            try:
                with open(meta_dest, "w", encoding="utf-8") as f:
                    json.dump({"rounds": rounds_meta, **{k:v for k,v in meta_after.items() if k!="rounds"}},
                              f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        return True, "Restauración completada."
    except Exception as e:
        return False, f"Error al restaurar: {e}"
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass


def _make_backup_local(label: str = "", note: str = "") -> str:
    """
    Crea un backup completo y devuelve la ruta del ZIP creado.
    """
    tag = _now_tag()
    label_clean = re.sub(r"[^A-Za-z0-9_\-]+", "_", label.strip()) if label else "backup"
    fname = f"{tag}__{label_clean}.zip"
    out_path = os.path.join(_bk_dir(), fname)
    paths = _collect_paths_for_backup()
    mf = _manifest(True, label=label, note=note, extra={"files": len(paths)})
    _write_zip(paths, out_path, mf)
    return out_path


from lib.ui2 import login_widget, require_teacher

# Sidebar: muestra el modo actual y el botón SALIR (si ya eres profe)
with st.sidebar:
    login_widget(logout_redirect_to="app.py")  # ← NO pide contraseña si ya hay sesión

# Guardia: si NO eres profe, te manda a Inicio y corta la ejecución
require_teacher(redirect_to="app.py")

st.session_state.setdefault("_meta_autofixed", False)

try:
    cfg = get_cfg()
    do_auto = bool(cfg.get("auto_fix_meta", False))
except Exception:
    do_auto = False

if do_auto and not st.session_state["_meta_autofixed"]:
    from lib.tournament import diagnose_meta, repair_meta
    d = diagnose_meta()
    if any([d.summary["missing"], d.summary["flag_mismatch"], d.summary["closed_mismatch"], d.summary["orphan_flags"]]):
        try:
            # backup rápido y reparación segura
            try: _make_backup_local(label="auto_fix", note="Auto-fix meta al entrar")
            except Exception: pass
            repair_meta(create_missing=True, sync_flags=True, fix_closed=True, remove_orphan_flags=True, preserve_dates=True)
            st.session_state["_meta_autofixed"] = True
            st.toast("Meta.json reparado automáticamente.")
        except Exception:
            pass  # nunca romper la carga de la página


# NAV personalizada debajo de la cabecera (título + nivel/año)
#sidebar_title_and_nav(extras=True)  # autodetecta páginas automáticamente
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

page_header("🛠️ Panel de Administración", "Gestión de rondas, publicación y resultados")
 

# Modo profesor activo (ya validado en la sidebar)
st.success("👩‍🏫 Modo Profesor activo")

# Clave dedicada para evitar colisiones con otras páginas
st.session_state.setdefault(
    "teacher_actor_name",
    st.session_state.get("teacher_actor_name") or st.session_state.get("actor_name") or "Admin"
)

# El widget ya se liga a la clave persistente
st.text_input("Tu nombre (registro de cambios)", key="teacher_actor_name", placeholder="Admin")

# Valor actual para usar en logs/acciones
actor = st.session_state["teacher_actor_name"]

# Sincroniza con claves usadas por el resto de módulos
st.session_state["actor_name"] = actor     # ← lo que leen Rondas/Clasificación/Genially
st.session_state["actor"] = actor          # ← por si queda código antiguo que usa 'actor'



# =========================
# Helpers de publicación robustos (meta.json + flag-file)
# =========================
def _pub_flag_path(i: int) -> str:
    return os.path.join(DATA_DIR, f"published_R{i}.flag")

def set_pub_safe(i: int, val: bool, seed=None):
    """Envuelve set_pub para asegurar que meta.json y el flag-file queden consistentes."""
    ok_meta = False
    # 1) Camino oficial
    try:
        set_pub(i, val, seed=seed)
        ok_meta = True
    except Exception:
        # 2) Fallback manual sobre meta.json
        try:
            meta = load_meta()
        except Exception:
            meta = {}
        rounds = meta.setdefault("rounds", {})
        r = rounds.setdefault(str(i), {})
        r["published"] = bool(val)
        if seed is not None:
            r["seed"] = seed
        try:
            _save_meta_preserving_dates(meta)
            ok_meta = True
        except Exception:
            pass
    # 3) Flag-file para published (fuente de verdad operativa)
    try:
        fp = _pub_flag_path(i)
        if val:
            open(fp, "w").close()
        else:
            if os.path.exists(fp):
                os.remove(fp)
    except Exception:
        pass
    return ok_meta


# =========================
# Fechas de ronda (helpers robustos con fallback a meta.json)
# =========================
from datetime import date as _date

# Guardamos referencia a las funciones originales si existen
try:
    _set_round_date_original = set_round_date  # importada desde lib.tournament
except Exception:
    _set_round_date_original = None

try:
    _get_round_date_original = get_round_date  # importada desde lib.tournament
except Exception:
    _get_round_date_original = None

def _parse_ymd(s: str | None):
    if not s:
        return None
    try:
        parts = str(s).split("-")
        if len(parts) != 3:
            return None
        y, m, d = map(int, parts)
        return _date(y, m, d)
    except Exception:
        return None

def get_round_date(i: int) -> str | None:
    """Devuelve 'YYYY-MM-DD' desde lib.tournament si es posible; si no, de meta.json."""
    if _get_round_date_original:
        try:
            v = _get_round_date_original(i)
            if v:
                return str(v)
        except Exception:
            pass
    try:
        meta = load_meta()
        return (meta.get("rounds", {}) or {}).get(str(i), {}).get("date") or None
    except Exception:
        return None

def set_round_date(i: int, dt: _date | str | None) -> None:
    """Intenta usar lib.tournament.set_round_date; si falla, guarda en meta.json."""
    if _set_round_date_original:
        try:
            _set_round_date_original(i, dt)
            return
        except Exception:
            pass
    try:
        meta = load_meta()
    except Exception:
        meta = {}
    rounds = meta.setdefault("rounds", {})
    r = rounds.setdefault(str(i), {})
    if isinstance(dt, _date):
        r["date"] = dt.isoformat()
    elif isinstance(dt, str) and dt.strip():
        p = _parse_ymd(dt.strip())
        r["date"] = p.isoformat() if p else dt.strip()
    else:
        r.pop("date", None)
    _save_meta_preserving_dates(meta)

# =========================
# Barra de menú interna (sticky)
# =========================
_STICKY_MENU_CSS = """
<style>
#admin-local-nav {
  position: sticky;
  top: 0;
  z-index: 999;
  padding: 0.25rem 0.25rem 0.5rem 0.25rem;
  background: var(--background-color);
  border-bottom: 1px solid rgba(49,51,63,0.15);
}
div[data-baseweb="radio"] > div[role="radiogroup"] {
  gap: 0.25rem !important;
  flex-wrap: wrap;
}
label[data-testid="stMarkdownContainer"] p {
  margin-bottom: 0 !important;
}
</style>
"""
st.markdown(_STICKY_MENU_CSS, unsafe_allow_html=True)

MENU = ["📋 Resumen","🧑‍🎓 Jugadores","🎲 Semilla R1","♟️ Generar","📅 Fechas","📣 Publicar","✏️ Resultados","🗑️ Eliminar","🗂️ Archivos","🧾 Config","💾 Backups"]
st.session_state.setdefault("admin_view", "📋 Resumen")
st.markdown('<div id="admin-local-nav">', unsafe_allow_html=True)
st.radio("Menú", MENU, horizontal=True, key="admin_view")
st.markdown("</div>", unsafe_allow_html=True)
view = st.session_state["admin_view"]

# =========================
# 🧾 Configuración (solo lectura)
# =========================
def _show_config():
    import json
    cfg = get_cfg()
    JUG_PATH = get_jug_path()

    st.markdown("### 🧾 Configuración (solo lectura)")

    # Mostrar JSON crudo cargado por load_config()
    try:
        st.code(json.dumps(cfg, ensure_ascii=False, indent=2), language="json")
    except Exception:
        st.write(cfg)

    # Resumen práctico
    df_j = read_csv_safe(JUG_PATH)
    activos = 0
    if df_j is not None and not df_j.empty:
        if "estado" in df_j.columns:
            activos = int((df_j["estado"].astype(str).str.lower() != "retirado").sum())
        else:
            activos = len(df_j)

    plan_mode = cfg.get("rondas", "auto")  # puede ser "auto" o un número
    min_r = cfg.get("min_rondas", "—")
    max_r = cfg.get("max_rondas", "—")
    nivel = cfg.get("nivel", "—")
    anio = cfg.get("anio", "—")

    resumen = pd.DataFrame([{
        "🎓 Nivel": nivel,
        "📅 Año": anio,
        "⚙️ rondas (config)": plan_mode,
        "⬇️ min_rondas": min_r,
        "⬆️ max_rondas": max_r,
        "🧑‍🎓 Jugadores activos": activos,
        "🧭 Plan de rondas (resuelto)": get_n_rounds(),  # calculado con planned_rounds(cfg, JUG_PATH)
    }], index=[0])

    st.dataframe(resumen, use_container_width=True, hide_index=True)

    # aviso amistoso si faltan claves
    missing = [k for k in ("nivel", "anio") if not cfg.get(k)]
    if missing:
        st.info("Sugerencia: completa estas claves en `config.json` → " + ", ".join(missing))

    st.divider()

    def round_file(i: int) -> str:
        return os.path.join(DATA_DIR, f"pairings_R{i}.csv")

    # Prefijo de contexto para el log
    def _log_msg(msg: str) -> str:
        return format_with_cfg(f"[{{nivel}}][{{anio}}] {msg}", cfg)


# =========================
# Carga de jugadores
# =========================
def _show_jugadores():
    st.markdown("### 🧑‍🎓 Cargar/actualizar jugadores")
    st.caption("Formato: id,nombre,apellido1,apellido2,curso,grupo,estado")
    jug_up = st.file_uploader("Subir/actualizar jugadores.csv", type=["csv"], key="jug_csv")
    if jug_up is not None:
        with open(JUG_PATH, "wb") as f:
            f.write(jug_up.read())
        st.success("`data/jugadores.csv` actualizado.")
        dfprev = read_csv_safe(JUG_PATH)
        if dfprev is not None and not dfprev.empty:
            st.caption(f"Jugadores cargados: {len(dfprev)}")
            st.dataframe(dfprev.head(10), use_container_width=True, hide_index=True)

    st.divider()


# =========================
# Diagnóstico de rondas
# =========================
def _show_resumen():

    # Asegurar estados locales
    states = get_states(get_n_rounds())
    st.markdown("### 📋 Estado de rondas")
    states = [round_status(i) for i in range(1, get_n_rounds() + 1)]
    diag = pd.DataFrame([
        {"Ronda": s["i"],
         "Estado": status_label(s),
         "Generada": "Sí" if s["exists"] else "No",
         "Publicada": "Sí" if s["published"] else "No",
         "Resultados vacíos": ("—" if s["empties"] is None else s["empties"]),
         "Cerrada (pub+sin vacíos)": "Sí" if s["closed"] else "No",
         "Archivo": os.path.basename(s["path"])}
        for s in states
    ])
    st.dataframe(diag, use_container_width=True, hide_index=True)

    existing_rounds = [i for i in range(1, get_n_rounds() + 1) if os.path.exists(round_file(i))]
    published_cnt = len([i for i in existing_rounds if is_pub(i)])
    closed_rounds = [s["i"] for s in states if s["closed"]]

    st.info(f"📣 Publicadas: **{published_cnt} / {get_n_rounds()}**  ·  🗂️ Generadas: **{len(existing_rounds)}**  ·  🧭 Plan: **{get_n_rounds()}**")
    st.write(f"🔒 Rondas cerradas (publicadas y sin vacíos): **{len(closed_rounds)}** / {get_n_rounds()}")

    st.divider()


# =========================
# 🎲 Semilla R1 (auditoría) + Regenerar R1 con semilla
# =========================
def _show_semilla():
    st.markdown("### 🎲 Semilla R1 (auditoría)")
    seed_val = r1_seed()
    if seed_val:
        st.caption("Semilla actualmente guardada:")
        st.code(seed_val)
    else:
        st.caption("Aún no hay semilla registrada. Se guardará al generar R1 con semilla.")

    col_a, col_b = st.columns([2, 1])
    with col_a:
        new_seed = st.text_input(
            "Nueva semilla para R1",
            value=seed_val or "",
            key="seed_r1_input",
            help="Si se deja vacío, se generará una semilla aleatoria."
        )

    with col_b:
        # Condiciones para permitir regenerar
        r1_published = is_pub(1)
        later_exist = any(os.path.exists(round_file(i)) for i in range(2, get_n_rounds() + 1))
        can_regen = (not r1_published) and (not later_exist)

        if st.button("🔁 Regenerar R1 con esta semilla", use_container_width=True, disabled=not can_regen):
            if r1_published:
                st.error("No se puede regenerar R1 porque está PUBLICADA. Despublica o elimina primero.")
            elif later_exist:
                st.error("No se puede regenerar R1 porque existen rondas posteriores generadas. Elimina R2.. antes.")
            else:
                seed_used = new_seed.strip() or f"seed-{random.randint(100000, 999999)}"
                random.seed(seed_used)

                # Estado inicial de jugadores (sin aplicar rondas previas)
                players = read_players_from_csv(JUG_PATH)
                if not players:
                    st.error("No se pudo leer `data/jugadores.csv`.")
                else:
                    # Emparejar R1 de cero con la semilla indicada
                    df_pairs = swiss_pair_round(players, 1, forced_bye_id=None)
                    outp = round_file(1)
                    df_pairs.astype(str).to_csv(outp, index=False, encoding="utf-8")

                    # Guardar semilla en meta
                    meta = load_meta()
                    meta.setdefault("rounds", {}).setdefault("1", {})["seed"] = seed_used
                    _save_meta_preserving_dates(meta)

                    add_log("regen_round1", 1, actor, _log_msg(f"R1 regenerada con seed={seed_used}"))
                    st.success(f"✅ Ronda 1 regenerada con semilla `{seed_used}`.")
                    st.rerun()

        if not can_regen:
            if r1_published:
                st.info("R1 está publicada: no se puede regenerar.")
            elif later_exist:
                st.info("Existen rondas posteriores generadas. Borra R2.. antes de regenerar R1.")

    st.divider()


# =========================
# Generar ronda siguiente (Suizo)
# =========================
def _show_generar():
    actor = (st.session_state.get("teacher_actor_name")
         or st.session_state.get("actor_name")
         or st.session_state.get("actor")
         or "admin")


    # Prefacio local para evitar NameError
    JUG_PATH = get_jug_path()

    try:
        _ = _log_msg
    except NameError:
        def _log_msg(x):
            return str(x)


    # Asegurar estados locales
    states = get_states(get_n_rounds())
    st.markdown("### ♟️ Generar siguiente ronda (sistema suizo)")

    # Determinar siguiente a generar
    first_missing = next((i for i in range(1, get_n_rounds() + 1) if not states[i - 1]["exists"]), None)

    if first_missing is None:
        st.success("✅ Todas las rondas están generadas.")
    else:
        next_round = first_missing

        # Fecha de celebración para la nueva ronda
        default_date = _dt.date.today()
        fecha_ronda = st.date_input(f"📅 Fecha de celebración para Ronda {next_round}", value=default_date, key=f"fecha_ronda_R{next_round}", format="DD/MM/YYYY")
        prev = next_round - 1
        allow_generate = True

        if prev >= 1:
            prev_state = states[prev - 1]
            if not prev_state["closed"]:
                allow_generate = False
                if not prev_state["published"]:
                    st.warning(
                        f"No se puede generar la **Ronda {next_round}** porque la **Ronda {prev}** no está publicada."
                    )
                else:
                    st.warning(
                        f"No se puede generar la **Ronda {next_round}** porque la **Ronda {prev}** tiene resultados pendientes "
                        f"({prev_state['empties']} sin completar)."
                    )
                force_key = f"force_gen_R{next_round}"
                force = st.checkbox("⚠️ Forzar generación de la siguiente ronda (solo esta vez)", value=False, key=force_key)
                if force:
                    allow_generate = True

        seed_used = None
        if next_round == 1:
            seed_input = st.text_input("Semilla de aleatoriedad para R1 (opcional)", value="")
        else:
            seed_input = ""

        st.write(f"Siguiente ronda candidata: **Ronda {next_round}**")

        if allow_generate:
            if is_pub(next_round):
                st.warning(f"La **Ronda {next_round}** ya está **PUBLICADA**. Despublícala para rehacerla.")
            else:
                if st.button(f"Generar Ronda {next_round}", use_container_width=True):
                    # Semilla para R1
                    if next_round == 1:
                        seed_used = seed_input.strip() or f"seed-{random.randint(100000, 999999)}"
                        random.seed(seed_used)

                    # Construir estado previo de jugadores aplicando R1..R(next_round-1) publicadas
                    players = read_players_from_csv(JUG_PATH)
                    if not players:
                        st.error("No se pudo leer `data/jugadores.csv`.")
                    else:
                        for rno in range(1, next_round):
                            dfp = read_csv_safe(round_file(rno))
                            players = apply_results(players, dfp, bye_points=1.0)

                        # Emparejar
                        df_pairs = swiss_pair_round(players, next_round, forced_bye_id=None)
                        outp = round_file(next_round)
                        df_pairs.astype(str).to_csv(outp, index=False, encoding="utf-8")
                        # Guardar fecha de celebración en meta.json
                        try:
                            set_round_date(next_round, fecha_ronda.isoformat())
                        except Exception:
                            pass


                        # Guardar semilla en meta si R1
                        if next_round == 1 and seed_used is not None:
                            meta = load_meta()
                            meta.setdefault("rounds", {}).setdefault("1", {})["seed"] = seed_used
                            _save_meta_preserving_dates(meta)

                        add_log("generate_round", next_round, actor, _log_msg(f"pairings guardado en {outp}"))

                        # Reset del “solo esta vez”
                        try:
                            st.session_state[f"force_gen_R{next_round}"] = False
                        except Exception:
                            pass

                        st.success(f"✅ Ronda {next_round} generada y guardada en `{outp}`")
                        st.rerun()

    st.divider()


# =========================
# Publicar / Despublicar
# =========================
def _show_publicar():

    st.markdown("### 📣 Publicar / Despublicar rondas")

    # Estados locales
    n = get_n_rounds()
    states = get_states(n)
    existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]

    unpublished = [i for i in existing_rounds if not is_pub(i)]
    published   = [i for i in existing_rounds if is_pub(i)]

    # Tabla de estado rápida
    if states:
        import pandas as pd
        diag = pd.DataFrame([
            {"Ronda": s["i"],
             "Estado": status_label(s),
             "Generada": "Sí" if s["exists"] else "No",
             "Publicada": "Sí" if s["published"] else "No",
             "Vacíos": ("—" if s["empties"] is None else s["empties"])}
            for s in states
        ])
        st.dataframe(diag, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Publicar una ronda en borrador")

    if unpublished:
        sel = st.selectbox("Ronda a publicar", unpublished, index=0, key="publicar_sel_round")
        if st.button(f"📣 Publicar Ronda {sel}", use_container_width=True, key=f"btn_publicar_R{sel}"):
            try:
                with st.spinner("Publicando y recalculando clasificación..."):
                    set_pub_safe(sel, True)
                    # Recalcular clasificación tras publicar
                    from lib.tournament import read_players_from_csv, read_csv_safe, apply_results, compute_standings
                    players = read_players_from_csv(os.path.join(DATA_DIR, "jugadores.csv"))
                    pubs = [i for i in existing_rounds if is_pub(i)]
                    for r in pubs:
                        dfp = read_csv_safe(round_file(r))
                        if dfp is not None:
                            players = apply_results(players, dfp, bye_points=1.0)
                    standings = compute_standings(players)
                    out_csv = os.path.join(DATA_DIR, "standings.csv")
                    try:
                        standings.to_csv(out_csv, index=False, encoding="utf-8-sig")
                    except Exception:
                        standings.to_csv(out_csv, index=False)
                st.toast(f"✅ Publicada Ronda {sel}")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo publicar la ronda: {e}")
    else:
        st.info("No hay rondas en borrador para publicar.")

    st.divider()
    st.markdown("#### Despublicar (solo la última publicada)")
    if published:
        ultima_pub = max(published)
        st.caption(f"Última publicada: Ronda {ultima_pub}")
        if st.button(f"↩️ Despublicar última (Ronda {ultima_pub})", use_container_width=True, key=f"btn_despublicar_{ultima_pub}"):
            try:
                with st.spinner("Despublicando y recalculando clasificación..."):
                    set_pub_safe(ultima_pub, False)
                    # Tras despublicar, recalcular clasificación con las restantes publicadas
                    from lib.tournament import read_players_from_csv, read_csv_safe, apply_results, compute_standings
                    players = read_players_from_csv(os.path.join(DATA_DIR, "jugadores.csv"))
                    pubs = [i for i in existing_rounds if is_pub(i)]
                    for r in pubs:
                        dfp = read_csv_safe(round_file(r))
                        if dfp is not None:
                            players = apply_results(players, dfp, bye_points=1.0)
                    standings = compute_standings(players)
                    out_csv = os.path.join(DATA_DIR, "standings.csv")
                    try:
                        standings.to_csv(out_csv, index=False, encoding="utf-8-sig")
                    except Exception:
                        standings.to_csv(out_csv, index=False)
                st.toast(f"↩️ Despublicada Ronda {ultima_pub}")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo despublicar: {e}")
    else:
        st.caption("No hay rondas publicadas actualmente.")

# =========================
# 📅 Fecha de celebración por ronda (solo borradores) — badges y edición solo en borradores

# =========================
# 🔎 Resumen rápido de fechas (check visual)
# =========================
def _resumen_fechas_panel():
    import datetime as _dt
    import pandas as pd

    # Contexto
    n = get_n_rounds()
    if not n:
        st.info("No hay rondas generadas todavía.")
        return

    existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
    if not existing_rounds:
        st.info("No hay rondas generadas todavía.")
        return

    # Helpers
    def _is_pub_safe(i: int) -> bool:
        try:
            return is_pub(i)
        except Exception:
            return False

    def _get_date_safe(i: int) -> str:
        try:
            return get_round_date(i) or ""
        except Exception:
            return ""

    # Construcción del dataset
    rows, by_date = [], {}
    hoy = _dt.date.today()
    for i in existing_rounds:
        f_iso = _get_date_safe(i)
        try:
            f_dt = _dt.date.fromisoformat(f_iso) if f_iso else None
        except Exception:
            f_dt = None
        publicado = _is_pub_safe(i)
        estado = "✅ Publicada" if publicado else "📝 Borrador"
        falta_fecha = (f_dt is None)
        dias = None if f_dt is None else (f_dt - hoy).days

        rows.append({
            "Ronda": i,
            "Estado": estado,
            "Fecha": f_dt,
            "Días": dias,
            "Falta fecha": "Sí" if falta_fecha else "No",
        })
        if f_dt:
            by_date.setdefault(f_dt, []).append((i, publicado))

    df = pd.DataFrame(rows).sort_values("Ronda")

    # Métricas
    tot = len(df)
    pub = (df["Estado"] == "✅ Publicada").sum()
    bor = (df["Estado"] == "📝 Borrador").sum()
    con_fecha = (df["Falta fecha"] == "No").sum()
    sin_fecha = (df["Falta fecha"] == "Sí").sum()

    # Conflictos: fechas duplicadas (multi-rondas mismo día)
    conflictos = []
    for d, lst in sorted(by_date.items()):
        if len(lst) > 1:
            conflictos.append((d, [r for r, _ in lst]))
    n_conf = len(conflictos)

    st.markdown("### 🔎 Resumen de fechas")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rondas", tot)
    c2.metric("Publicadas", pub)
    c3.metric("Borradores", bor)
    c4.metric("Con fecha", con_fecha)
    c5.metric("Sin fecha", sin_fecha)

    if n_conf > 0:
        with st.expander(f"⚠️ Conflictos de fecha: {n_conf}", expanded=True):
            for d, lst in conflictos:
                st.warning(f"{d.strftime('%d/%m/%Y')} → Rondas {', '.join(map(str, lst))}")

    # Tabla general (lectura)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ronda": st.column_config.NumberColumn(format="%d"),
            "Estado": st.column_config.TextColumn(),
            "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "Días": st.column_config.NumberColumn(help="Días desde hoy (negativo = pasado)"),
            "Falta fecha": st.column_config.TextColumn(),
        },
    )

    # Descarga CSV
    import io
    buf = io.StringIO()
    # Exportamos con Fecha ISO-friendly
    df_export = df.copy()
    df_export["Fecha"] = df_export["Fecha"].astype(str)
    df_export.to_csv(buf, index=False, encoding="utf-8")
    st.download_button(
        "⬇️ Descargar resumen (CSV)",
        data=buf.getvalue().encode("utf-8"),
        file_name="resumen_fechas_rondas.csv",
        mime="text/csv",
        use_container_width=True,
    )

# =========================
# 📅 Fecha de celebración por ronda (solo borradores) — badges y edición solo en borradores
# =========================
def _show_fechas():
    import datetime as _dt
    import pandas as pd

    # Panel de control visual primero
    _resumen_fechas_panel()

    st.markdown("### 📅 Fecha de celebración (solo rondas en borrador)")

    # --- Contexto y rondas existentes ---
    n = get_n_rounds()
    if not n:
        st.info("No hay rondas generadas todavía.")
        return

    existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
    if not existing_rounds:
        st.info("No hay rondas generadas todavía.")
        return

    # Helpers seguros
    def _is_pub_safe(i: int) -> bool:
        try:
            return is_pub(i)
        except Exception:
            return False

    def _get_date_safe(i: int) -> str:
        try:
            return get_round_date(i) or ""
        except Exception:
            return ""

    # =========================
    # 1) Editor individual (solo borradores)
    # =========================
    st.subheader("Editor individual (solo borradores)")
    draft_rounds = [i for i in existing_rounds if not _is_pub_safe(i)]
    if not draft_rounds:
        st.info("No hay rondas en borrador para editar fecha.")
    else:
        col_sel, col_badge = st.columns([2, 1])
        with col_sel:
            sel_draft = st.selectbox(
                "Ronda en borrador a editar",
                draft_rounds,
                index=0,
                key="fecha_sel_round_legacy",
            )
        with col_badge:
            st.markdown("**Estado:** 📝 Borrador")

        current_iso = _get_date_safe(sel_draft)
        default_date = _dt.date.today()
        if current_iso:
            try:
                y, m_, d = map(int, current_iso.split("-"))
                default_date = _dt.date(y, m_, d)
            except Exception:
                pass

        new_date = st.date_input(
            "Nueva fecha de celebración",
            value=default_date,
            key=f"fecha_edit_R{sel_draft}",
            format="DD/MM/YYYY",
        )

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Guardar fecha", use_container_width=True, key=f"save_fecha_R{sel_draft}"):
                try:
                    set_round_date(sel_draft, new_date.isoformat())
                    try:
                        pretty = format_date_es(new_date.isoformat())
                    except Exception:
                        pretty = new_date.strftime('%d/%m/%Y')
                    st.success(f"Fecha guardada para Ronda {sel_draft}: {pretty}")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo guardar la fecha: {e}")
        with c2:
            if st.button("🗑️ Borrar fecha", use_container_width=True, key=f"del_fecha_R{sel_draft}"):
                try:
                    set_round_date(sel_draft, None)
                    st.success(f"Fecha borrada para Ronda {sel_draft}.")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo borrar la fecha: {e}")

    st.divider()

    # =========================
    # 2) Editor rápido (tabla) — SOLO BORRADORES (editable)
    # =========================
    st.subheader("Editor rápido — Borradores (editable)")
    rows_draft, rows_pub = [], []
    for i in existing_rounds:
        fecha_iso = _get_date_safe(i)
        try:
            fecha_dt = _dt.date.fromisoformat(fecha_iso) if fecha_iso else None
        except Exception:
            fecha_dt = None
        publicado = _is_pub_safe(i)
        estado_badge = "✅ Publicada" if publicado else "📝 Borrador"
        row = {"Ronda": i, "Estado": estado_badge, "Fecha": fecha_dt}
        (rows_pub if publicado else rows_draft).append(row)

    # ---- Tabla editable (solo borradores)
    if rows_draft:
        df_draft = pd.DataFrame(rows_draft).sort_values("Ronda")
        ed = st.data_editor(
            df_draft,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ronda": st.column_config.NumberColumn(format="%d"),
                "Estado": st.column_config.TextColumn(help="Estado de la ronda: ✅ Publicada · 📝 Borrador"),
                "Fecha": st.column_config.DateColumn("Fecha (editable)", format="DD/MM/YYYY"),
            },
            disabled=["Ronda", "Estado"],  # Solo Fecha editable
            key="fechas_editor_tabla_borradores",
        )

        if st.button("💾 Guardar cambios (borradores)", use_container_width=True, key="save_fechas_tabla_borr"):
            cambios = 0
            try:
                for _, r in ed.iterrows():
                    i = int(r["Ronda"])
                    v = r["Fecha"]
                    if pd.isna(v):
                        set_round_date(i, None)
                        cambios += 1
                    else:
                        set_round_date(i, v.isoformat())  # v es datetime.date
                        cambios += 1
                st.success(f"Fechas actualizadas para {cambios} ronda(s) en borrador.")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo aplicar la actualización: {e}")
    else:
        st.info("No hay rondas en borrador.")

    st.divider()

    # =========================
    # 3) Publicadas (solo lectura)
    # =========================
    st.subheader("Rondas publicadas (solo lectura)")
    if rows_pub:
        df_pub = pd.DataFrame(rows_pub).sort_values("Ronda")
        st.dataframe(
            df_pub,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Ronda": st.column_config.NumberColumn(format="%d"),
                "Estado": st.column_config.TextColumn(),
                "Fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            },
        )
    else:
        st.caption("No hay rondas publicadas aún.")

# =========================
# Resultados y clasificación (solo PUBLICADAS)
# =========================
def _show_resultados():
    import os
    st.markdown("### ✏️ Resultados y clasificación (solo PUBLICADAS)")

    # Contexto local necesario para evitar NameError
    actor = (st.session_state.get("teacher_actor_name")
            or st.session_state.get("actor_name")
            or st.session_state.get("actor")
            or "admin")

    try:
        _ = _log_msg
    except NameError:
        def _log_msg(x):
            return str(x)

    pubs = published_rounds_list()
    if pubs:
        sel_r = st.selectbox("Ronda publicada a editar", pubs, index=len(pubs) - 1, key="res_round")
        dfp = read_csv_safe(round_file(sel_r))
        if dfp is not None:
            st.caption("Valores permitidos: 1-0, 0-1, 1/2-1/2, +/- , -/+, BYE1.0, BYE0.5, BYE")

            # Buffer editable en sesión (incluye columna 'seleccionar')
            buf_key = f"res_buf_R{sel_r}"
            if buf_key not in st.session_state:
                base_df = dfp.copy()
                if "seleccionar" not in base_df.columns:
                    base_df["seleccionar"] = False
                st.session_state[buf_key] = base_df
            else:
                # Garantizar columnas clave por si el CSV cambió
                for col in ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]:
                    if col not in st.session_state[buf_key].columns:
                        st.session_state[buf_key][col] = dfp.get(col, "")
                if "seleccionar" not in st.session_state[buf_key].columns:
                    st.session_state[buf_key]["seleccionar"] = False

            edited_now = st.data_editor(
                st.session_state[buf_key],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "seleccionar": st.column_config.CheckboxColumn("seleccionar", help="Marca filas para acciones masivas"),
                    "resultado": st.column_config.SelectboxColumn(
                        "resultado",
                        options=["", "1-0", "0-1", "1/2-1/2", "+/-", "-/+", "BYE1.0", "BYE0.5", "BYE"],
                        required=False
                    )
                },
                num_rows="fixed",
                key=f"editor_results_R{sel_r}"
            )
            st.session_state[buf_key] = edited_now.copy()

            # Controles de selección
            csel1, csel2, csel3 = st.columns(3)
            with csel1:
                if st.button("Seleccionar todo"):
                    df = st.session_state[buf_key].copy()
                    df["seleccionar"] = True
                    st.session_state[buf_key] = df
                    st.rerun()
            with csel2:
                if st.button("Quitar selección"):
                    df = st.session_state[buf_key].copy()
                    df["seleccionar"] = False
                    st.session_state[buf_key] = df
                    st.rerun()
            with csel3:
                solo_vacios = st.checkbox("Solo vacíos", value=True, key=f"solo_vacios_R{sel_r}")

            # Helpers para filtros de acciones
            def _sel(df: pd.DataFrame) -> pd.Series:
                s = df.get("seleccionar", False)
                if hasattr(s, "astype"):
                    try:
                        s = s.fillna(False).astype(bool)
                    except Exception:
                        s = s == True
                return s == True

            def _is_bye_series(df: pd.DataFrame) -> pd.Series:
                return df["negras_id"].astype(str).str.upper() == "BYE"

            def _is_empty_res(df: pd.DataFrame) -> pd.Series:
                if "resultado" not in df.columns:
                    return pd.Series([True] * len(df), index=df.index)
                res = _normalize_result_series(df["resultado"])
                return res == ""

            # Botones de acciones masivas
            a1, a2, a3, a4, a5 = st.columns(5)
            with a1:
                if st.button("Completar con tablas (½-½)"):
                    df = st.session_state[buf_key].copy()
                    sel = _sel(df); elig = ~_is_bye_series(df)
                    if solo_vacios: elig = elig & _is_empty_res(df)
                    idxs = df.index[sel & elig].tolist()
                    if not idxs:
                        st.warning("No hay filas seleccionadas (y elegibles) para completar con tablas.")
                    else:
                        df.loc[idxs, "resultado"] = "1/2-1/2"
                        st.session_state[buf_key] = df
                        st.rerun()
            with a2:
                if st.button("Ganan BLANCAS (1-0)"):
                    df = st.session_state[buf_key].copy()
                    sel = _sel(df); elig = ~_is_bye_series(df)
                    if solo_vacios: elig = elig & _is_empty_res(df)
                    idxs = df.index[sel & elig].tolist()
                    if not idxs:
                        st.warning("No hay filas seleccionadas (y elegibles) para poner 1-0.")
                    else:
                        df.loc[idxs, "resultado"] = "1-0"
                        st.session_state[buf_key] = df
                        st.rerun()
            with a3:
                if st.button("Ganan NEGRAS (0-1)"):
                    df = st.session_state[buf_key].copy()
                    sel = _sel(df); elig = ~_is_bye_series(df)
                    if solo_vacios: elig = elig & _is_empty_res(df)
                    idxs = df.index[sel & elig].tolist()
                    if not idxs:
                        st.warning("No hay filas seleccionadas (y elegibles) para poner 0-1.")
                    else:
                        df.loc[idxs, "resultado"] = "0-1"
                        st.session_state[buf_key] = df
                        st.rerun()
            with a4:
                if st.button("Completar BYEs"):
                    df = st.session_state[buf_key].copy()
                    sel = _sel(df); elig = _is_bye_series(df)
                    if solo_vacios: elig = elig & _is_empty_res(df)
                    idxs = df.index[sel & elig].tolist()
                    if not idxs:
                        st.warning("No hay filas seleccionadas (y elegibles) para completar BYEs.")
                    else:
                        df.loc[idxs, "resultado"] = "BYE1.0"
                        st.session_state[buf_key] = df
                        st.rerun()
            with a5:
                if st.button("Vaciar resultados"):
                    df = st.session_state[buf_key].copy()
                    sel = _sel(df)
                    idxs = df.index[sel].tolist()
                    if not idxs:
                        st.warning("No hay filas seleccionadas para vaciar resultados.")
                    else:
                        df.loc[idxs, "resultado"] = ""
                        st.session_state[buf_key] = df
                        st.rerun()

            # Guardar resultados (normalizados) y recalcular
            if st.button("💾 Guardar resultados de la ronda", use_container_width=True):
                outp = round_file(sel_r)
                df_to_save = st.session_state[buf_key].copy()

                # No guardar columna interna
                if "seleccionar" in df_to_save.columns:
                    df_to_save = df_to_save.drop(columns=["seleccionar"])

                # Normalizar columna resultado
                if "resultado" not in df_to_save.columns:
                    df_to_save["resultado"] = ""
                df_to_save["resultado"] = _normalize_result_series(df_to_save["resultado"])

                try:
                    with st.spinner("Guardando resultados y recalculando clasificación..."):
                        # Guardar CSV
                        df_to_save.to_csv(outp, index=False, encoding="utf-8")

                        # Log (no debe romper)
                        try:
                            add_log("save_results", sel_r, actor, _log_msg("Resultados actualizados"))
                        except Exception:
                            pass

                        # Recalcular standings (mismo patrón que en 📣 Publicar)
                        players = read_players_from_csv(os.path.join(DATA_DIR, "jugadores.csv"))
                        pubs = published_rounds_list()
                        for r in pubs:
                            dfp_pub = read_csv_safe(round_file(r))
                            if dfp_pub is not None:
                                players = apply_results(players, dfp_pub, bye_points=1.0)
                        standings = compute_standings(players)
                        out_csv = os.path.join(DATA_DIR, "standings.csv")
                        try:
                            standings.to_csv(out_csv, index=False, encoding="utf-8-sig")
                        except Exception:
                            standings.to_csv(out_csv, index=False)

                    # Reset de selección en el buffer tras guardar
                    df_after = read_csv_safe(outp)
                    if df_after is None:
                        df_after = df_to_save.copy()
                    df_after["seleccionar"] = False
                    st.session_state[buf_key] = df_after

                    st.success(f"Resultados guardados. Clasificación recalculada en `{out_csv}`.")
                    st.rerun()

                except Exception as e:
                    st.error(f"No se pudo guardar/recalcular: {e}")
    else:
        st.info("No hay rondas publicadas todavía.")

    st.divider()


# =========================
# Eliminar ronda (solo la última generada)
# =========================
def _show_eliminar():
    import os
    st.markdown("### 🗑️ Eliminar ronda")
    actor = (st.session_state.get("teacher_actor_name")
            or st.session_state.get("actor_name")
            or st.session_state.get("actor")
            or "admin")

    # Fallback local por si _log_msg aún no está definido en este punto del archivo
    try:
        _ = _log_msg
    except NameError:
        def _log_msg(x):
            return str(x)

    # Fallback local si no existe `recalc_and_save_standings`
    try:
        _ = recalc_and_save_standings  # noqa: F401
    except NameError:
        def recalc_and_save_standings(bye_points: float = 1.0):
            """Recalcula standings con las rondas PUBLICADAS y guarda en data/standings.csv.
            Devuelve (ok: bool, path_csv: str | None).
            """
            try:
                import os
                from lib.tournament import (
                    DATA_DIR, round_file, read_csv_safe,
                    read_players_from_csv, apply_results, compute_standings,
                )
                from lib.ui2 import is_pub
            except Exception:
                pass

            try:
                players = read_players_from_csv(os.path.join(DATA_DIR, "jugadores.csv"))
            except Exception:
                return (False, None)

            try:
                n = get_n_rounds()
            except Exception:
                n = 0

            pubs = []
            for i in range(1, n + 1):
                try:
                    if os.path.exists(round_file(i)) and is_pub(i):
                        pubs.append(i)
                except Exception:
                    continue

            for r in pubs:
                try:
                    dfp = read_csv_safe(round_file(r))
                    if dfp is not None and not getattr(dfp, "empty", True):
                        players = apply_results(players, dfp, bye_points=bye_points)
                except Exception:
                    pass

            try:
                standings = compute_standings(players)
                out_csv = os.path.join(DATA_DIR, "standings.csv")
                try:
                    standings.to_csv(out_csv, index=False, encoding="utf-8-sig")
                except Exception:
                    standings.to_csv(out_csv, index=False)
                return (True, out_csv)
            except Exception:
                return (False, None)

    # Asegurar lista de rondas existentes (solo las que tienen CSV en data/)
    n = get_n_rounds()
    existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]

    if not existing_rounds:
        st.info("No hay rondas para eliminar.")
        st.divider()
        return

    last_exist = max(existing_rounds)
    st.caption(f"Solo se puede **eliminar** la **última ronda generada**: **Ronda {last_exist}**.")

    warn = st.text_input(f'Escribe **ELIMINAR R{last_exist}** para confirmar', "")
    pressed = st.button(f"Eliminar definitivamente Ronda {last_exist}", use_container_width=True)

    if pressed:
        if warn.strip().upper() == f"ELIMINAR R{last_exist}":
            path = round_file(last_exist)
            try:
                with st.spinner("Eliminando ronda y recalculando clasificación..."):
                    # Borrar CSV de la ronda
                    if os.path.exists(path):
                        os.remove(path)

                    # Limpiar meta (si existe)
                    try:
                        meta = load_meta()
                        if str(last_exist) in meta.get("rounds", {}):
                            meta["rounds"].pop(str(last_exist), None)
                            _save_meta_preserving_dates(meta)
                    except Exception:
                        pass  # meta opcional

                    # Log (no debe romper si falla)
                    try:
                        add_log("delete_round", last_exist, actor, _log_msg(f"{os.path.basename(path)} eliminado"))
                    except Exception:
                        pass

                    # Recalcular clasificación
                    ok, path2 = recalc_and_save_standings(bye_points=1.0)

                if ok:
                    st.success(f"Ronda R{last_exist} eliminada. Clasificación recalculada en `{path2}`.")
                else:
                    st.info("Ronda eliminada. No se pudo recalcular la clasificación (¿sin jugadores?).")

                st.rerun()

            except Exception as e:
                st.error(f"No se pudo eliminar: {e}")
        else:
            st.warning(f'Debes escribir exactamente "ELIMINAR R{last_exist}" para confirmar.')

    st.divider()


# =========================
# Archivos (inspector + visores + descargas)
# =========================
def _show_archivos():
    import os, io, zipfile, pandas as pd, datetime as _dt, json
    def _toggle(key: str):
        st.session_state[key] = not st.session_state.get(key, False)
    
    st.markdown("### 🗂️ Archivos")

    # ---------- Inspector rápido de /data ----------
    st.markdown("########## 🗂️ Archivos en `data/` (inspector rápido)")
    def _lm(p: str) -> str:
        try:
            return _dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "—"

    col_btn, _ = st.columns([1, 6])
    label = "👁️ Mostrar inspector" if not st.session_state.get("show_inspector", False) else "🙈 Ocultar inspector"
    if col_btn.button(label, key="btn_inspector"):
        _toggle("show_inspector")

    if st.session_state.get("show_inspector"):
        try:
            files = sorted(os.listdir(DATA_DIR))
        except Exception as e:
            st.error(f"No se puede listar DATA_DIR: {e}")
            files = []

        if files:
            rows = []
            for f in files:
                p = os.path.join(DATA_DIR, f)
                try:
                    sz = os.path.getsize(p)
                    mt = _lm(p)
                except Exception:
                    sz, mt = 0, "—"
                rows.append({"archivo": f, "tamaño_bytes": sz, "modificado": mt})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption("No hay ficheros en `data/` o no es accesible.")

    # Rutas base que usaremos abajo
    _cfg_path = os.path.join(os.path.dirname(DATA_DIR), "config.json")  # ajusta si tu config vive en otra carpeta
    _meta_path = os.path.join(DATA_DIR, "meta.json")                    # cambia si tu meta tiene otro nombre
    _log_path  = os.path.join(DATA_DIR, "admin_log.csv")

    st.markdown("---")

    # ---------- Visores rápidos (solo para ficheros no visualizados en otros módulos) ----------
    st.markdown("#### 👀 Visores rápidos")

# Visor rápido: jugadores.csv
    st.markdown("##### 👥 Visor rápido: admin_log.csv")
    c1, _ = st.columns([1, 6])
    lab = "👁️ Mostrar tabla" if not st.session_state.get("show_v_admin_log", False) else "🙈 Ocultar tabla"
    if c1.button(lab, key="btn_v_admin_log"):
        _toggle("show_v_jug")
    if st.session_state.get("show_v_admin_log"):    # admin_log.csv → tabla
        if os.path.exists(_log_path):
            st.markdown("**admin_log.csv**")
            try:
                dflog = pd.read_csv(_log_path)
                st.dataframe(dflog, use_container_width=True, hide_index=True)
            except Exception as e:
                st.caption(f"No se puede leer admin_log.csv: {e}")

    # meta.json → JSON + (opcional) tabla de rondas si hay estructura 'rounds'
    if os.path.exists(_meta_path):
        # --- Visor de meta.json (seguro) ---
        st.markdown("**meta.json**")

        meta_obj = None
        import json  # import local para evitar dependencias en cabecera
        try:
            with open(_meta_path, "r", encoding="utf-8") as f:
                meta_obj = json.load(f)
        except Exception as e:
            st.caption(f"No se puede leer meta.json: {e}")
        else:
            st.json(meta_obj)

        # Construir la tabla comparativa solo si cargó bien el JSON
        rows_meta = []
        if isinstance(meta_obj, dict):
            rounds_meta = meta_obj.get("rounds", {}) or {}
            try:
                n_max = get_n_rounds()
            except Exception:
                n_max = 0

            existing = [i for i in range(1, n_max + 1) if os.path.exists(round_file(i))]
            for i in existing:
                v = rounds_meta.get(str(i), {})

                # Valores desde meta (con defaults robustos)
                pub_meta    = bool(v.get("published", False))
                date_meta   = v.get("date") or ""
                closed_meta = bool(v.get("closed", False))

                # Estado real
                try:
                    pub_real = is_pub(i)
                except Exception:
                    pub_real = False
                try:
                    dfp = read_csv_safe(round_file(i))
                    vac  = results_empty_count(dfp) if dfp is not None else None
                except Exception:
                    vac  = None
                closed_real = bool(pub_real and (vac == 0))

                # Fecha "real": lo más fideligno que tenemos es get_round_date (guarda en meta)
                try:
                    date_real = get_round_date(i) or ""
                except Exception:
                    date_real = ""

                # Ahora ya fuera del try/except, formateamos en español
                date_meta_es = _dt.date.fromisoformat(date_meta).strftime('%d/%m/%Y') if date_meta else ''
                date_real_es = _dt.date.fromisoformat(date_real).strftime('%d/%m/%Y') if date_real else ''

                rows_meta.append({
                    "Ronda": i,
                    "Fecha (meta)": date_meta_es,
                    "Fecha (real)": date_real_es,
                    "Publicado (meta)": "Sí" if pub_meta else "No",
                    "Publicado (real)": "Sí" if pub_real else "No",
                    "Cerrada (meta)": "Sí" if closed_meta else "No",
                    "Cerrada (real)": "Sí" if closed_real else "No",
                    "⚠️ Desv. closed": "🔴" if (closed_meta != closed_real) else "",
                })


        if rows_meta:
            dfm = pd.DataFrame(rows_meta)

            def _row_style(r):
                # Soporta el nombre nuevo y el antiguo por compatibilidad
                flag = r.get("⚠️ Desv. closed", r.get("desviación_closed", ""))
                bad = bool(flag)  # "🔴" -> True, cadena vacía -> False
                return ["background-color:#ffe5e5" if bad else "" for _ in r]


            #def _row_style(r):
            #    return ["background-color:#ffe5e5" if r["desviación_closed"] else "" for _ in r]
            
            st.table(dfm.style.apply(_row_style, axis=1))

    st.markdown("---")

    # ---------- Descargas ----------
    def _dl_button(label, path, mime, key):
        if os.path.exists(path):
            with open(path, "rb") as f:
                st.download_button(label, f.read(), file_name=os.path.basename(path), mime=mime, key=key)
        else:
            st.caption(f"· {os.path.basename(path)} — no existe")

    st.markdown("########## 📦 Descargas directas")


    # Fila 1
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if os.path.exists(os.path.join(DATA_DIR, "config.json")):
            with open(os.path.join(DATA_DIR, "config.json"), "rb") as f:
                st.download_button("config.json", f.read(), file_name="config.json", mime="application/json", key="dl_cfg")
    with c2:
        if os.path.exists(os.path.join(DATA_DIR, "jugadores.csv")):
            with open(os.path.join(DATA_DIR, "jugadores.csv"), "rb") as f:
                st.download_button("jugadores.csv", f.read(), file_name="jugadores.csv", mime="text/csv", key="dl_jug")
    with c3:
        if os.path.exists(os.path.join(DATA_DIR, "standings.csv")):
            with open(os.path.join(DATA_DIR, "standings.csv"), "rb") as f:
                st.download_button("standings.csv", f.read(), file_name="standings.csv", mime="text/csv", key="dl_stand")
    with c4:
        if os.path.exists(os.path.join(DATA_DIR, "meta.json")):
            with open(os.path.join(DATA_DIR, "meta.json"), "rb") as f:
                st.download_button("meta.json", f.read(), file_name="meta.json", mime="application/json", key="dl_meta")

    # Fila 2
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if os.path.exists(os.path.join(DATA_DIR, "admin_log.csv")):
            with open(os.path.join(DATA_DIR, "admin_log.csv"), "rb") as f:
                st.download_button("admin_log.csv", f.read(), file_name="admin_log.csv", mime="text/csv", key="dl_log")
    with c2:
        # flags.zip (si lo generas en memoria)
        if 'flags_zip_bytes' in st.session_state:
            st.download_button("flags.zip", st.session_state['flags_zip_bytes'],
                            file_name="flags.zip", mime="application/zip", key="dl_flags")
    # c3, c4 libres para lo que ya tengas

 
    # ---------- Rondas ----------
    st.markdown("########## ♟️ Descargar ronda (CSV)Rondas")

    c_sel, c_btn = st.columns([3, 2])
    rondas = sorted([int(x) for x in re.findall(r"R(\d+)", " ".join(os.listdir(DATA_DIR))) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{int(x)}.csv"))])
    sel_r = c_sel.selectbox("Ronda", rondas, key="dl_ronda_sel")
    csv_path = os.path.join(DATA_DIR, f"pairings_R{sel_r}.csv")
    if os.path.exists(csv_path):
        with open(csv_path, "rb") as f:
            c_btn.download_button(f"Descargar R{sel_r}.csv"", f.read(),
                                file_name=f"pairings_R{sel_r}.csv", mime="text/csv",
                                key="dl_ronda_btn")

    st.markdown("---")

   # n = get_n_rounds() if 'get_n_rounds' in globals() else 0
   # if n > 0:
   #     rondas_exist = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
   #     if rondas_exist:
   #         r_sel = st.selectbox("Ronda", rondas_exist, index=len(rondas_exist) - 1, key="dl_r_sel")
   #        _dl_button(f"Descargar R{r_sel}.csv", round_file(r_sel), "text/csv", f"dl_r{r_sel}")

    
    # --- Sustituir el bloque de utilidades meta.json por esto ---
    from lib.tournament import diagnose_meta, repair_meta

    st.markdown("#### 🛠️ Utilidades meta.json (compactas)")

    # Mostrar (persistente) el último backup creado antes de reparar
    if st.session_state.get("show_backup_dl") and st.session_state.get("last_meta_backup_bytes"):
        fname = st.session_state.get("last_meta_backup_name", "backup_torneo.zip")
        st.success("Backup creado antes de reparar.")
        st.caption(f"Archivo: **{fname}**")
        st.download_button(
            f"⬇️ Descargar {fname}",
            st.session_state["last_meta_backup_bytes"],
            file_name=fname,
            mime="application/zip",
            key="dl_meta_bk_persist",
        )
        if st.button("Ocultar aviso", key="hide_backup_notice"):
            for k in ("show_backup_dl", "last_meta_backup_bytes", "last_meta_backup_name"):
                st.session_state.pop(k, None)
            st.rerun()


    with st.expander("Diagnóstico (clic para ver detalle)", expanded=True):
        d = diagnose_meta()
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("CSV existentes", d.summary["existing"])
        c2.metric("Rondas en meta", d.summary["in_meta"])
        c3.metric("Faltan en meta", d.summary["missing"])
        c4.metric("published incoh.", d.summary["flag_mismatch"])
        c5.metric("closed incoh.", d.summary["closed_mismatch"])
        c6.metric("flags huérfanos", d.summary["orphan_flags"])

        if d.missing_in_meta: st.warning(f"Faltan en meta: {d.missing_in_meta}")
        if d.flag_mismatch:  st.warning(f"Incoherencias 'published': {d.flag_mismatch}")
        if d.closed_mismatch: st.warning(f"Incoherencias 'closed': {d.closed_mismatch}")
        if d.orphan_flags: st.info(f"Flags huérfanos: {d.orphan_flags}")

    # Opciones seguras (por defecto activas)
    st.caption("Reparación segura (preserva fechas; no borra entradas de meta).")
    colA, colB, colC, colD = st.columns(4)
    with colA: opt_create  = st.checkbox("Crear faltantes", value=True)
    with colB: opt_sync    = st.checkbox("Sincronizar published", value=True)
    with colC: opt_closed  = st.checkbox("Recalcular closed", value=True)
    with colD: opt_orphan  = st.checkbox("Eliminar flags huérfanos", value=True)


    # clave de sesión para recordar el último backup creado
    st.session_state.setdefault("last_meta_backup", None)

    pre_snap = st.checkbox("Backup antes de reparar", value=True, key="meta_pre_snap")

     
     # Reparación segura (con backup previo automático si está marcado)
    if st.button("🧯 Reparar (seguro)", type="primary", key="meta_repair"):
        try:
            backup_path = None
            if pre_snap:  # checkbox “Backup antes de reparar”
                try:
                    backup_path = _make_backup_local(label="Snapshot_auto_meta_fix", note="Backup previo a repair_meta")
                    st.session_state["last_meta_backup"] = backup_path
                except Exception:
                    pass

            res = repair_meta(
                create_missing=opt_create,
                sync_flags=opt_sync,
                fix_closed=opt_closed,
                remove_orphan_flags=opt_orphan,
                preserve_dates=True,
            )
            st.success(f"OK · aplicados: {res['applied']}")

            # Ofrece descarga del backup PREVIO (si se creó)
            path = st.session_state.get("last_meta_backup")

            # … ya hiciste repair_meta(...) y tienes backup_path si pre_snap estaba marcado ….

            # Guarda bytes/nombre del backup para poder descargar tras el rerun
            if backup_path and os.path.exists(backup_path):
                with open(backup_path, "rb") as f:
                    st.session_state["last_meta_backup_bytes"] = f.read()
                st.session_state["last_meta_backup_name"] = os.path.basename(backup_path)
                st.session_state["show_backup_dl"] = True

            st.rerun()



        except Exception as e:
            st.error(f"Fallo al reparar: {e}")

#    with st.expander("Herramientas avanzadas (con cuidado)"):
#        st.caption("Aquí podríamos añadir en el futuro acciones más agresivas (p.ej., borrar entradas de meta sin CSV). Por ahora, **no** se realizan para evitar riesgos.")

# =========================
# 💾 Copias y Restauración (local)
# =========================
def _show_backups():
    st.markdown("## 💾 Copias y Restauración (local)")

    # (En _show_backups)
       
    st.subheader("Opciones de restauración")
    pre_snapshot = st.checkbox("Snapshot automático antes de restaurar", value=True, key="opt_pre_snap")
    preserve_dates = st.checkbox("Preservar fechas actuales si el backup no las trae", value=True, key="opt_preserve_dates")
    # clean_extra = st.checkbox("Limpiar pairings que no estén en el ZIP (evita mezclar estados)", value=True 
    clean_extra_pairings = st.checkbox("Limpiar pairings no incluidos en el ZIP", value=True, key="opt_clean_pair")
    clean_extra_flags = st.checkbox("Limpiar flags de publicación no incluidos / no coherentes", value=True, key="opt_clean_flags")
    recalc_closed = st.checkbox("Recalcular 'closed' tras restaurar", 
    value=True, key="opt_recalc_closed")



    # --- Crear backup ---
    st.subheader("Crear backup")
    col1, col2 = st.columns([2, 3])
    with col1:
        label = st.text_input("Etiqueta del backup (nivel/curso/grupo)", value="", help="p.ej. 'NivelA', 'Semifinales', 'Curso2025'")
    with col2:
        note = st.text_input("Nota breve (opcional)", value="", help="Descripción corta del motivo del backup")

    if st.button("🧷 Crear backup ahora", use_container_width=True, type="primary"):
        try:
            out = _make_backup_local(label=label, note=note)
            st.success(f"Backup creado: {os.path.basename(out)}")
            with open(out, "rb") as f:
                st.download_button("⬇️ Descargar backup", data=f.read(),
                                   file_name=os.path.basename(out),
                                   mime="application/zip", use_container_width=True)
        except Exception as e:
            st.error(f"No se pudo crear el backup: {e}")

    st.divider()

    # --- Restaurar desde backup existente ---
    st.subheader("Restaurar desde backup existente")
    bdir = _bk_dir()
    files = sorted([f for f in os.listdir(bdir) if f.endswith(".zip")], reverse=True)
    if files:
        sel = st.selectbox("Selecciona backup", files, index=0, key="bk_sel")
        path = os.path.join(bdir, sel)
        # Mostrar manifest
        try:
            import zipfile, json
            with zipfile.ZipFile(path, "r") as z:
                if "manifest.json" in z.namelist():
                    manifest = json.loads(z.read("manifest.json"))
                    with st.expander("Ver manifest.json"):
                        st.json(manifest)
        except Exception:
            pass

        c1, c2 = st.columns([1, 1])
        with c1:
            with open(path, "rb") as f:
                st.download_button("⬇️ Descargar este backup", data=f.read(),
                                   file_name=os.path.basename(path),
                                   mime="application/zip", use_container_width=True)
        with c2:
            if st.button("⚠️ Restaurar este backup", use_container_width=True):
                # ... en “Restaurar este backup”
                ok, msg = _restore_zip(
                    path,
                    pre_snapshot=pre_snapshot,
                    preserve_dates=preserve_dates,
                    clean_extra_pairings=clean_extra_pairings,
                    clean_extra_flags=clean_extra_flags,
                    recalc_closed=recalc_closed
                )

            
                (st.success if ok else st.error)(msg)
                if ok:
                    st.toast("Restaurado. Recargando…")
                    st.experimental_rerun()

    else:
        st.info("No hay backups locales aún. Crea uno arriba.")

    st.divider()

    # --- Restaurar desde un ZIP local subido ---
    st.subheader("Restaurar desde ZIP local")
    up = st.file_uploader("Sube un ZIP de backup", type=["zip"], accept_multiple_files=False)
    if up is not None:
# ... y en “Restaurar desde ZIP local”
        if st.button("⚠️ Restaurar desde ZIP subido", use_container_width=True, key="restore_uploaded"):

            ok, msg = _restore_zip(
                up,
                pre_snapshot=pre_snapshot,
                preserve_dates=preserve_dates,
                clean_extra_pairings=clean_extra_pairings,
                clean_extra_flags=clean_extra_flags,
                recalc_closed=recalc_closed
            )
            (st.success if ok else st.error)(msg)
            if ok:
                st.toast("Restaurado. Recargando…")
                st.experimental_rerun()



# =========================
# Router de vistas
# =========================
if view == '🧾 Config': _show_config()
elif view == '🧑‍🎓 Jugadores': _show_jugadores()
elif view == '📋 Resumen': _show_resumen()
elif view == '🎲 Semilla R1': _show_semilla()
elif view == '♟️ Generar': _show_generar()
elif view == '📣 Publicar': _show_publicar()
elif view == '📅 Fechas': _show_fechas()
elif view == '✏️ Resultados': _show_resultados()
elif view == '🗑️ Eliminar': _show_eliminar()
elif view == '🗂️ Archivos': _show_archivos()
elif view == '💾 Backups': _show_backups()


def _debug_meta_persistencia():
    import os, json, datetime as _dt
    from lib.tournament import DATA_DIR, config_path, config_debug, load_meta, save_meta

    st.markdown("### 🧪 Diagnóstico de persistencia de meta.json")
    st.code(f"DATA_DIR = {DATA_DIR}", language="bash")
    st.code(f"config_path() = {config_path()}", language="bash")

    meta_path = os.path.join(DATA_DIR, "meta.json")
    st.code(f"meta.json en: {meta_path}", language="bash")

    try:
        mt = os.path.getmtime(meta_path)
        st.caption(f"Última modificación de meta.json: { _dt.datetime.fromtimestamp(mt) }")
    except Exception:
        st.caption("meta.json aún no existe.")

    meta_before = load_meta() or {}
    st.json(meta_before)

    st.markdown("#### Probar escritura/lectura (no destruye nada)")
    if st.button("Probar escritura no destructiva en meta.json", use_container_width=True):
        try:
            # 1) leer lo actual
            meta = load_meta() or {}
            rounds = meta.setdefault("rounds", {})
            # 2) escribir un marcador temporal bajo rounds.__diag (no afecta a rondas reales)
            import time
            rounds.setdefault("__diag", {})["ts_es"] = _dt.datetime.now(tz=ZoneInfo("Europe/Madrid")).strftime("%d/%m/%Y %H:%M:%S")

            _save_meta_preserving_dates(meta)
            # 3) releer y mostrar
            st.success("Guardado OK. Releyendo…")
            st.json(load_meta())
        except Exception as e:
            st.error(f"Fallo al guardar: {e}")
  
