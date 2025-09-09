# pages/99_Admin.py
# -*- coding: utf-8 -*-
import os
import random
import pandas as pd
import streamlit as st

from lib.tournament import (
    DATA_DIR,
    load_config, load_meta, save_meta,
    read_csv_safe, last_modified,
    read_players_from_csv, apply_results, compute_standings,
    swiss_pair_round, formatted_name_from_parts,
    is_published, set_published, r1_seed, add_log,
)

st.header("🛠️ Panel de Administración")

# =========================
# Acceso (simple)
# =========================
pwd = st.text_input("Contraseña", type="password")
if not pwd or pwd != st.secrets.get("ADMIN_PASS", ""):
    st.stop()
st.success("Acceso concedido ✅")

actor = st.text_input("Tu nombre (registro de cambios)", value=st.session_state.get("actor_name", "Admin"))
st.session_state["actor_name"] = actor

cfg = load_config()
N_ROUNDS = int(cfg.get("rondas", 5))

JUG_PATH = os.path.join(DATA_DIR, "jugadores.csv")
def round_file(i: int) -> str:
    return os.path.join(DATA_DIR, f"pairings_R{i}.csv")

# =========================
# Publicación robusta (meta + flag) - alias internos
# =========================
def _pub_flag_path(i: int) -> str:
    return os.path.join(DATA_DIR, f"published_R{i}.flag")

def is_pub(i: int) -> bool:
    try:
        if is_published(i):
            return True
    except Exception:
        pass
    return os.path.exists(_pub_flag_path(i))

def set_pub(i: int, val: bool, seed=None):
    try:
        set_published(i, val, seed=seed)
    except Exception:
        pass
    fp = _pub_flag_path(i)
    try:
        if val:
            open(fp, "w").close()
        else:
            if os.path.exists(fp):
                os.remove(fp)
    except Exception:
        pass

# =========================
# Helpers de normalización/estado
# =========================
def _normalize_result_series(s: pd.Series) -> pd.Series:
    """Convierte None/nan/'None'/'nan'/'N/A' en '' y recorta espacios."""
    return (
        s.astype(str)
         .str.strip()
         .replace({"None": "", "none": "", "NaN": "", "nan": "", "N/A": "", "n/a": ""})
    )

def results_empty_count(df: pd.DataFrame | None) -> int | None:
    if df is None or df.empty or "resultado" not in df.columns:
        return None
    res = _normalize_result_series(df["resultado"])
    return int((res == "").sum())

def round_status(i: int) -> dict:
    p = round_file(i)
    df = read_csv_safe(p)
    exists = df is not None and not df.empty
    empties = results_empty_count(df) if exists else None
    pub = is_pub(i) if exists else False
    # Cerrada <=> existe & publicada & sin vacíos
    closed = exists and pub and (empties == 0)
    return {"i": i, "exists": exists, "published": pub, "empties": empties, "closed": closed, "path": p}

def status_label(s: dict) -> str:
    if not s["exists"]:
        return "—"
    if s["published"]:
        if s["empties"] == 0:
            return "✅ Cerrada"
        return "📣 Publicada"
    return "📝 Borrador"

def published_rounds_list() -> list[int]:
    return sorted([i for i in range(1, N_ROUNDS + 1) if os.path.exists(round_file(i)) and is_pub(i)])

def recalc_and_save_standings(bye_points: float = 1.0) -> tuple[bool, str]:
    """Recalcula la clasificación SOLO con rondas publicadas y guarda standings.csv."""
    players = read_players_from_csv(JUG_PATH)
    if not players:
        return False, "No se pudo leer jugadores.csv"
    pubs = published_rounds_list()
    for rno in pubs:
        dfp = read_csv_safe(round_file(rno))
        players = apply_results(players, dfp, bye_points=float(bye_points))
    df_st = compute_standings(players)
    outp = os.path.join(DATA_DIR, "standings.csv")
    df_st.to_csv(outp, index=False, encoding="utf-8")
    return True, outp

# =========================
# Carga de jugadores
# =========================
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
st.markdown("### 📋 Estado de rondas")
states = [round_status(i) for i in range(1, N_ROUNDS + 1)]
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

existing_rounds = [i for i in range(1, N_ROUNDS + 1) if os.path.exists(round_file(i))]
published_cnt = len([i for i in existing_rounds if is_pub(i)])
closed_rounds = [s["i"] for s in states if s["closed"]]

st.info(f"📣 Publicadas: **{published_cnt} / {N_ROUNDS}**  ·  🗂️ Generadas: **{len(existing_rounds)}**")
st.write(f"🔒 Rondas cerradas (publicadas y sin vacíos): **{len(closed_rounds)}** / {N_ROUNDS}")

st.divider()

# =========================
# Generar ronda siguiente (Suizo)
# =========================
st.markdown("### ♟️ Generar siguiente ronda (sistema suizo)")

# Determinar siguiente a generar
first_missing = next((i for i in range(1, N_ROUNDS + 1) if not states[i - 1]["exists"]), None)

if first_missing is None:
    st.success("✅ Todas las rondas están generadas.")
else:
    next_round = first_missing
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

                    # Guardar semilla en meta si R1
                    if next_round == 1 and seed_used is not None:
                        meta = load_meta()
                        meta.setdefault("rounds", {}).setdefault("1", {})["seed"] = seed_used
                        save_meta(meta)

                    add_log("generate_round", next_round, actor, f"pairings guardado en {outp}")

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
st.markdown("### 📣 Publicar / Despublicar rondas")

if existing_rounds:
    status_rows = [{"ronda": i, "publicada": bool(is_pub(i))} for i in existing_rounds]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    # Publicar (cualquiera que exista y no esté publicada)
    to_publish = [i for i in existing_rounds if not is_pub(i)]
    if to_publish:
        sel_pub = st.selectbox("Ronda a publicar", to_publish, index=len(to_publish) - 1, key="pub_sel")
        if st.button("Publicar ronda seleccionada", use_container_width=True):
            set_pub(sel_pub, True, seed=(r1_seed() if sel_pub == 1 else None))
            add_log("publish_round", sel_pub, actor, "Publicada desde Admin")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Ronda {sel_pub} publicada. Clasificación recalculada en `{path}`.")
            else:
                st.warning("Ronda publicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
    else:
        st.info("No hay rondas pendientes de publicar.")

    # Despublicar (solo la última publicada)
    pubs = published_rounds_list()
    if pubs:
        last_pub = max(pubs)
        st.caption(f"Solo se puede **despublicar** la **última ronda publicada**: **Ronda {last_pub}**.")
        if st.button(f"Despublicar Ronda {last_pub}", use_container_width=True):
            set_pub(last_pub, False)
            add_log("unpublish_round", last_pub, actor, "Despublicada (última publicada)")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Ronda {last_pub} despublicada. Clasificación recalculada en `{path}`.")
            else:
                st.warning("Ronda despublicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
    else:
        st.info("No hay rondas publicadas actualmente.")
else:
    st.info("Aún no hay rondas generadas.")

st.divider()

# =========================
# Resultados y clasificación (solo PUBLICADAS)
# =========================
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
            add_log("save_results", sel_r, actor, "Resultados actualizados")

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
            add_log("delete_round", last_exist, actor, f"{os.path.basename(path)} eliminado")

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
