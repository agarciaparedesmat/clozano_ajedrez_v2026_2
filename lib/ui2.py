# lib/ui2.py
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from typing import List, Dict, Optional

import pandas as pd

# Import canonical utilities from the tournament core
from lib.tournament import (
    DATA_DIR,
    read_csv_safe,
    round_file,
    is_published,
    set_published,
)

# -------------------------
# Publicación robusta (meta + flag) - wrappers
# -------------------------
def _pub_flag_path(i: int) -> str:
    return os.path.join(DATA_DIR, f"published_R{i}.flag")

def is_pub(i: int) -> bool:
    """
    Publicado si:
      - is_published(i) del core lo indica (meta.json), o
      - existe el flag-file published_R{i}.flag (fallback robusto)
    """
    try:
        if is_published(i):
            return True
    except Exception:
        # si el core aún no está cargado, caemos al flag-file
        pass
    return os.path.exists(_pub_flag_path(i))

def set_pub(i: int, val: bool, seed: Optional[str] = None) -> None:
    """
    Sube/Baja la publicación de una ronda delegando en el core (meta.json)
    y manteniendo un flag-file de respaldo.
    """
    try:
        set_published(i, val, seed=seed)
    except Exception:
        # si falla el meta, seguimos con el flag-file igualmente
        pass

    fp = _pub_flag_path(i)
    try:
        if val:
            # crear/asegurar flag
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            open(fp, "w").close()
        else:
            # eliminar flag si existe
            if os.path.exists(fp):
                os.remove(fp)
    except Exception:
        # no impedimos el flujo por errores de E/S
        pass

# -------------------------
# Estado por ronda
# -------------------------
def _normalize_result_series(s: pd.Series) -> pd.Series:
    """Convierte None/nan/'None'/'nan'/'N/A' en '' y recorta espacios."""
    return (
        s.astype(str)
         .str.strip()
         .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )

def results_empty_count(df: Optional[pd.DataFrame]) -> Optional[int]:
    """Cuenta resultados vacíos en un CSV de emparejamientos; None si df inválido."""
    if df is None or df.empty or "resultado" not in df.columns:
        return None
    res = _normalize_result_series(df["resultado"])
    return int((res == "").sum())

def round_status(i: int) -> Dict[str, object]:
    """
    Devuelve:
      { "i": i, "exists": bool, "published": bool, "empties": int|None, "closed": bool, "path": str }
    Cerrada <=> existe & publicada & sin vacíos.
    """
    p = round_file(i)
    df = read_csv_safe(p)
    exists = df is not None and not df.empty
    empties = results_empty_count(df) if exists else None
    pub = is_pub(i) if exists else False
    closed = exists and pub and (empties == 0)
    return {"i": i, "exists": exists, "published": pub, "empties": empties, "closed": closed, "path": p}

def status_label(s: Dict[str, object]) -> str:
    if not s.get("exists"):
        return "—"
    if s.get("published"):
        if s.get("empties") == 0:
            return "✅ Cerrada"
        return "📣 Publicada"
    return "📝 Borrador"

def get_states(n_rounds: int) -> List[Dict[str, object]]:
    """Estado para todas las rondas 1..n_rounds."""
    return [round_status(i) for i in range(1, int(n_rounds) + 1)]



# --- Auth: Modo Profesor / Alumno (con badge y separador) -------------------
import os, hashlib, streamlit as st

# Claves de sesión y roles
SESSION_ROLE_KEY = "rol_usuario"
ROLE_ALUMNO = "Alumno"
ROLE_PROFESOR = "Profesor"
SHOW_LOGIN_FORM_KEY = "show_login_form"
AUTH_ERROR_KEY = "auth_error"

def _ensure_state():
    st.session_state.setdefault(SESSION_ROLE_KEY, ROLE_ALUMNO)      # ⬅️ por defecto: Alumno
    st.session_state.setdefault(SHOW_LOGIN_FORM_KEY, False)         # no mostrar login al inicio
    st.session_state.setdefault("admin_pwd", "")
    st.session_state.setdefault(AUTH_ERROR_KEY, "")

def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _admin_pass_hash() -> str:
    """
    Orden de lectura (flexible):
      1) st.secrets['auth']['admin_pass_sha256'] (hash)
      2) ENV ADMIN_PASS_SHA256 (hash)
      3) st.secrets['ADMIN_PASS'] (plano -> se hashea aquí)
      4) ENV ADMIN_PASS (plano -> se hashea aquí)
    """
    h = ""
    try:
        h = st.secrets.get("auth", {}).get("admin_pass_sha256", "")
    except Exception:
        pass
    if not h:
        h = os.environ.get("ADMIN_PASS_SHA256", "")
    if not h:
        try:
            plain = st.secrets.get("ADMIN_PASS", "")
            if plain:
                h = _sha256(plain)
        except Exception:
            pass
    if not h:
        plain = os.environ.get("ADMIN_PASS", "")
        if plain:
            h = _sha256(plain)
    return (h or "").strip().lower()

def is_teacher() -> bool:
    return st.session_state.get(SESSION_ROLE_KEY, ROLE_ALUMNO) == ROLE_PROFESOR

def set_role(role: str) -> None:
    st.session_state[SESSION_ROLE_KEY] = role

def _safe_rerun():
    # Asegura refresco inmediato (evita "doble clic")
    try:
        st.rerun()
    except Exception:
        try:
            st.experimental_rerun()
        except Exception:
            pass

def _admin_login_on_change():
    """Valida cuando se pulsa Enter en el input de contraseña."""
    pwd = st.session_state.get("admin_pwd", "")
    if pwd and _sha256(pwd) == _admin_pass_hash():
        set_role(ROLE_PROFESOR)
        st.session_state[SHOW_LOGIN_FORM_KEY] = False   # oculta formulario tras validar
        st.session_state["admin_pwd"] = ""
        st.session_state[AUTH_ERROR_KEY] = ""
        #_safe_rerun()  # refresca menú/navegación inmediatamente  (¡¡¡¡¡inneesario!!!!)
    else:
        st.session_state[AUTH_ERROR_KEY] = "Contraseña incorrecta."


def _logout():
    set_role(ROLE_ALUMNO)
    st.session_state[SHOW_LOGIN_FORM_KEY] = False
    st.session_state["admin_pwd"] = ""
    st.session_state[AUTH_ERROR_KEY] = ""
    #_safe_rerun()  # refresca menú/navegación inmediatamente  (¡¡¡¡¡inneesario!!!!)
    #_safe_rerun()  # ⬅️ evita tener que pulsar dos veces


def _logout_and_redirect(target: str | None = None):
    _logout()
    if target:
        try:
            st.switch_page(target)   # redirige inmediatamente si es posible
        except Exception:
            pass  # si no se puede, en la próxima recarga 'require_teacher' hará de escoba

def _enter_prof_request():
    # Mostrar formulario SIN cambiar a profesor
    set_role(ROLE_ALUMNO)   # por si venimos de sesión previa
    st.session_state[SHOW_LOGIN_FORM_KEY] = True
    st.session_state[AUTH_ERROR_KEY] = ""
    st.session_state["admin_pwd"] = ""

def _cancel_prof_request():
    # Cancelar y volver a Alumno siempre (sin rerun explícito)
    set_role(ROLE_ALUMNO)
    st.session_state[SHOW_LOGIN_FORM_KEY] = False
    st.session_state[AUTH_ERROR_KEY] = ""
    st.session_state["admin_pwd"] = ""


_BADGE_CSS = """
<style>
/* Badges */
.badge {display:inline-flex; align-items:center; gap:.10rem; padding:.22rem .60rem;
        border-radius:999px; font-weight:700; font-size:0.86rem; line-height:1;}
.badge.profe  {background:#e7f7ec; border:1px solid #7bd58b;}
.badge.alumno {background:#eaf2ff; border:1px solid #8ab4ff;}

/* Separador fino con muy poco margen */
.sep-thin {height:1px; background:rgba(0,0,0,.10); border:0; margin:.5rem 0 .5rem;}

/* TENSAR márgenes típicos en la sidebar */
[data-testid="stSidebar"] h4 { margin: 0 0 .25rem !important; }    /* “#### Sesión” */
[data-testid="stSidebar"] p  { margin: 0 0 .25rem !important; }    /* captions, etc. */
[data-testid="stSidebar"] .stButton { margin: .15rem 0 !important; }/* botones compactos */

/* Botones de la sidebar más pequeños y redondeados */
[data-testid="stSidebar"] .stButton > button {
  padding: .22rem .6rem !important;
  font-size: .85rem !important;
  border-radius: 999px !important;
}
</style>
"""


def login_widget(logout_redirect_to: str | None = None):
    """Coloca esto al PRINCIPIO de la sidebar en TODAS las páginas."""
    _ensure_state()
    st.markdown(_BADGE_CSS, unsafe_allow_html=True)
    st.markdown("#### 👥 Sesión")

    if is_teacher():
        # ---- Fila: badge Profesor + botón SALIR ----
        col_badge, col_btn = st.columns([0.72, 0.28])
        with col_badge:
            st.markdown('<span class="badge profe">👩‍🏫 Modo Profesor</span>', unsafe_allow_html=True)
        with col_btn:
            st.button("🚪", key="logout_btn",
                      on_click=_logout_and_redirect, kwargs={"target": logout_redirect_to})
        st.markdown('<hr class="sep-thin">', unsafe_allow_html=True)
        return

    # ---- Fila: badge Alumno + botón PROFESOR ----
    col_badge, col_btn = st.columns([0.72, 0.28])
    with col_badge:
        st.markdown('<span class="badge alumno">🎓 Modo Alumno</span>', unsafe_allow_html=True)
    with col_btn:
        st.button("👩‍🏫", key="go_prof_btn", on_click=_enter_prof_request)

    st.markdown('<hr class="sep-thin">', unsafe_allow_html=True)

    # Formulario de contraseña (solo si se ha pedido "PROFESOR")
    if st.session_state[SHOW_LOGIN_FORM_KEY]:
        st.text_input("Contraseña de profesor", type="password", key="admin_pwd", on_change=_admin_login_on_change)
        st.caption("Pulsa **Enter** para validar.")
        if st.session_state[AUTH_ERROR_KEY]:
            st.error(st.session_state[AUTH_ERROR_KEY])
        st.button("Cancelar", key="cancel_prof_btn", on_click=_cancel_prof_request)


def require_teacher(redirect_to: str | None = None):
    """
    Si no hay sesión de profesor:
      - si redirect_to está definido → intenta st.switch_page(redirect_to)
      - en cualquier caso, detiene la ejecución de esta página
    """
    if not is_teacher():
        if redirect_to:
            try:
                st.switch_page(redirect_to)
            except Exception:
                pass
        st.stop()
