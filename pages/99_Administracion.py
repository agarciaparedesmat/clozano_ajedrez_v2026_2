from __future__ import annotations
import os
import pandas as pd
import streamlit as st
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
import datetime as _dt
# pages/99_Admin.py
# -*- coding: utf-8 -*-

import random




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

MENU = ["📋 Resumen","🧑‍🎓 Jugadores","🎲 Semilla R1","♟️ Generar","📅 Fechas","📣 Publicar","✏️ Resultados","🗑️ Eliminar","🗂️ Archivos","🧾 Config"]
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
                    save_meta(meta)

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
        fecha_ronda = st.date_input(f"📅 Fecha de celebración para Ronda {next_round}", value=default_date, key=f"fecha_ronda_R{next_round}")
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
                            save_meta(meta)

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
                    set_pub(sel, True)
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
                    set_pub(ultima_pub, False)
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
# 📅 Fecha de celebración por ronda (solo borradores)
# =========================
def _show_fechas():
    
    # Estado local y utilidades
    n = get_n_rounds()
    states = get_states(n)
    # Construir lista de rondas existentes
    existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
    st.markdown("### 📅 Fecha de celebración (solo rondas en borrador)")
    # Filtrar borradores (existen pero no publicadas)
    draft_rounds = [i for i in existing_rounds if not is_pub(i)]
    if draft_rounds:
        sel_draft = st.selectbox("Ronda en borrador a editar", draft_rounds, index=0, key="fecha_sel_round")
        # Fecha actual (ISO) si existe
        try:
            current_iso = get_round_date(sel_draft) or ""
        except Exception:
            current_iso = ""
        default_date = _dt.date.today()
        if current_iso:
            try:
                y, m_, d = map(int, current_iso.split("-"))
                default_date = _dt.date(y, m_, d)
            except Exception:
                pass
        new_date = st.date_input("Nueva fecha de celebración", value=default_date, key=f"fecha_edit_R{sel_draft}")
        if st.button("💾 Guardar fecha de la ronda", use_container_width=True, key=f"save_fecha_R{sel_draft}"):
            try:
                set_round_date(sel_draft, new_date.isoformat())
                try:
                    pretty = format_date_es(new_date.isoformat())
                except Exception:
                    pretty = new_date.isoformat()
                st.success(f"Fecha guardada para Ronda {sel_draft}: {pretty}")
            except Exception as e:
                st.error(f"No se pudo guardar la fecha: {e}")
    else:
        st.info("No hay rondas en borrador para editar fecha.")
    
# =========================
# Resultados y clasificación (solo PUBLICADAS)
# =========================
def _show_resultados():
    st.markdown("### ✏️ Resultados y clasificación (solo PUBLICADAS)")

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

                # Guardar CSV
                df_to_save.to_csv(outp, index=False, encoding="utf-8")
                add_log("save_results", sel_r, actor, _log_msg("Resultados actualizados"))

                # Reset de selección en el buffer tras guardar
                df_after = read_csv_safe(outp)
                if df_after is None:
                    df_after = df_to_save.copy()
                df_after["seleccionar"] = False
                st.session_state[buf_key] = df_after

                # Recalcular clasificación
                ok, path = recalc_and_save_standings(bye_points=1.0)
                if ok:
                    st.success(f"Resultados guardados. Clasificación recalculada en `{path}`.")
                else:
                    st.warning("Resultados guardados, pero no se pudo recalcular la clasificación.")
                st.rerun()
    else:
        st.info("No hay rondas publicadas todavía.")

    st.divider()


# =========================
# Eliminar ronda (solo la última generada)
# =========================
def _show_eliminar():
    st.markdown("### 🗑️ Eliminar ronda")
    if existing_rounds:
        last_exist = max(existing_rounds)
        st.caption(f"Solo se puede **eliminar** la **última ronda generada**: **Ronda {last_exist}**.")
        warn = st.text_input(f'Escribe **ELIMINAR R{last_exist}** para confirmar', "")
        if st.button(f"Eliminar definitivamente Ronda {last_exist}", use_container_width=True) and warn.strip().upper() == f"ELIMINAR R{last_exist}":
            path = round_file(last_exist)
            try:
                os.remove(path)
                # Limpieza de meta si existe entrada de esa ronda
                meta = load_meta()
                if str(last_exist) in meta.get("rounds", {}):
                    meta["rounds"].pop(str(last_exist), None)
                    save_meta(meta)
                add_log("delete_round", last_exist, actor, _log_msg(f"{os.path.basename(path)} eliminado"))

                ok, path2 = recalc_and_save_standings(bye_points=1.0)
                if ok:
                    st.success(f"Ronda R{last_exist} eliminada. Clasificación recalculada en `{path2}`.")
                else:
                    st.info("Ronda eliminada. No se pudo recalcular la clasificación (¿sin jugadores?).")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo eliminar: {e}")
    else:
        st.info("No hay rondas para eliminar.")

    st.divider()


# =========================
# Inspector de data/
# =========================
def _show_archivos():
    st.markdown("### 🗂️ Archivos en `data/` (inspector rápido)")
    try:
        files = os.listdir(DATA_DIR)
        if files:
            rows = []
            for f in sorted(files):
                p = os.path.join(DATA_DIR, f)
                try:
                    sz = os.path.getsize(p)
                    mt = last_modified(p)
                except Exception:
                    sz, mt = 0, "—"
                rows.append({"archivo": f, "tamaño_bytes": sz, "modificado": mt})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("`data/` está vacío.")
    except Exception as e:
        st.warning(f"No se pudo listar `data/`: {e}")

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
