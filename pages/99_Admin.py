import streamlit as st
import os
import pandas as pd
import random

from lib.tournament import (
    load_config, load_meta, save_meta, read_csv_safe, last_modified,
    read_players_from_csv, apply_results, swiss_pair_round, formatted_name_from_parts,
    is_published, set_published, r1_seed, add_log,
    compute_standings, DATA_DIR
)

st.header("Panel de Administración")

# ---------- Auth ----------
pwd = st.text_input("Contraseña", type="password")
if not pwd or pwd != st.secrets.get("ADMIN_PASS", ""):
    st.stop()
st.success("Acceso concedido ✅")

actor = st.text_input("Tu nombre (registro de cambios)", value=st.session_state.get("actor_name", "Admin"))
st.session_state["actor_name"] = actor

cfg = load_config()
n = int(cfg.get("rondas", 5))
jug_path = os.path.join(DATA_DIR, "jugadores.csv")

# ---------- Publicación robusta (meta + flag-file) ----------
def _pub_flag_path(i: int):
    return os.path.join(DATA_DIR, f"published_R{i}.flag")

def is_pub(i: int) -> bool:
    # Preferimos meta; si falla o no está, usamos flag-file
    try:
        if is_published(i):
            return True
    except Exception:
        pass
    return os.path.exists(_pub_flag_path(i))

def set_pub(i: int, val: bool, seed=None):
    # Intentamos persistir en meta y también en flag-file
    try:
        set_published(i, val, seed=seed)
    except Exception:
        pass
    fp = _pub_flag_path(i)
    if val:
        try:
            open(fp, "w").close()
        except Exception:
            pass
    else:
        try:
            if os.path.exists(fp):
                os.remove(fp)
        except Exception:
            pass

# ---------- Helpers ----------
def round_file(i): return os.path.join(DATA_DIR, f"pairings_R{i}.csv")

def results_empty_count(df):
    if df is None or df.empty or "resultado" not in df.columns: return None
    return int((df["resultado"].fillna("").astype(str).str.strip() == "").sum())

def round_status(i):
    p = round_file(i)
    df = read_csv_safe(p)
    exists = df is not None and not df.empty
    empties = results_empty_count(df) if exists else None
    pub = is_pub(i) if exists else False
    # Cerrada <=> existe & publicada & sin vacíos
    closed = exists and pub and (empties == 0)
    return {"i": i, "exists": exists, "published": pub, "empties": empties, "closed": closed, "path": p}

def status_label(s):
    if not s["exists"]:
        return "—"
    if s["published"]:
        if s["empties"] == 0:
            return "✅ Cerrada"
        return "📣 Publicada"
    return "📝 Borrador"

def published_rounds_list():
    return sorted([i for i in range(1, n+1) if os.path.exists(round_file(i)) and is_pub(i)])

def recalc_and_save_standings(bye_points=1.0):
    players = read_players_from_csv(jug_path)
    if not players: return False, "No se pudo leer jugadores.csv"
    pubs = published_rounds_list()
    for rno in pubs:
        dfp = read_csv_safe(round_file(rno))
        players = apply_results(players, dfp, bye_points=float(bye_points))
    df_st = compute_standings(players)
    outp = os.path.join(DATA_DIR, "standings.csv")
    df_st.to_csv(outp, index=False, encoding="utf-8")
    return True, outp

# ---------- Carga de jugadores ----------
st.markdown("### Emparejar (sistema suizo)")
st.caption("Formato: id,nombre,apellido1,apellido2,curso,grupo,estado")
jug_up = st.file_uploader("Subir/actualizar jugadores.csv", type=["csv"], key="jug_csv")
if jug_up is not None:
    with open(jug_path, "wb") as f:
        f.write(jug_up.read())
    st.success("jugadores.csv actualizado.")
    dfprev = read_csv_safe(jug_path)
    if dfprev is not None and not dfprev.empty:
        st.caption(f"Jugadores cargados: {len(dfprev)}")
        st.dataframe(dfprev.head(10), use_container_width=True, hide_index=True)

# ---------- Diagnóstico de rondas ----------
states = [round_status(i) for i in range(1, n+1)]
closed_rounds = [s["i"] for s in states if s["closed"]]
first_missing = next((i for i in range(1, n+1) if not states[i-1]["exists"]), None)

st.markdown("#### Estado de rondas")
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
st.write(f"Rondas cerradas: **{len(closed_rounds)}** / {n}")

# ---------- Determinar siguiente ronda a generar ----------
seed_input = ""
next_round = None
if first_missing is None:
    st.success("✅ Todas las rondas están generadas.")
else:
    next_round = first_missing
    prev = next_round - 1
    allow_generate = True
    if prev >= 1:
        prev_state = states[prev-1]
        if not prev_state["closed"]:
            allow_generate = False
            if not prev_state["published"]:
                st.warning(
                    f"No se puede generar la Ronda {next_round} porque la Ronda {prev} **no está publicada**. "
                    f"Primero **publícala** y después completa los resultados."
                )
            else:
                st.warning(
                    f"No se puede generar la Ronda {next_round} porque la Ronda {prev} **tiene resultados pendientes**. "
                    f"Faltan **{prev_state['empties']}** resultados en `pairings_R{prev}.csv`."
                )
            force_key = f"force_gen_R{next_round}"
            force = st.checkbox("⚠️ Forzar generación de la siguiente ronda (solo esta vez)", value=False, key=force_key)
            if force:
                allow_generate = True

    if next_round == 1:
        seed_input = st.text_input("Semilla de aleatoriedad para R1 (opcional)", value="")

    st.write(f"Siguiente ronda candidata: **Ronda {next_round if next_round else '—'}**")

    if allow_generate and next_round is not None:
        if is_pub(next_round):
            st.warning(f"La Ronda {next_round} ya está **PUBLICADA**. Despublícala para rehacerla.")
        else:
            if st.button(f"Generar Ronda {next_round}"):
                if next_round == 1:
                    seed_used = seed_input.strip() or "seed-" + str(random.randint(100000, 999999))
                    random.seed(seed_used)
                else:
                    seed_used = None

                players = read_players_from_csv(jug_path)
                if not players:
                    st.error("No se pudo leer `data/jugadores.csv`.")
                else:
                    for rno in range(1, next_round):
                        dfp = read_csv_safe(round_file(rno))
                        players = apply_results(players, dfp, bye_points=1.0)

                    df_pairs = swiss_pair_round(players, next_round, forced_bye_id=None)
                    outp = round_file(next_round)
                    df_pairs.astype(str).to_csv(outp, index=False, encoding="utf-8")
                    if next_round == 1 and seed_used is not None:
                        meta = load_meta(); meta.setdefault("rounds", {}).setdefault("1", {})["seed"] = seed_used; save_meta(meta)
                    add_log("auto_save_pairings_on_generate", next_round, actor, f"Guardado inicial en {outp}")
                    try:
                        st.session_state[f"force_gen_R{next_round}"] = False
                    except Exception:
                        pass
                    st.success(f"Ronda {next_round} generada y guardada en {outp}")
                    st.rerun()

st.divider()

# ---------- Publicar / Despublicar ----------
st.markdown("### Publicar / Despublicar rondas")
existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
if existing_rounds:
    status_rows = [{"ronda": i, "publicada": bool(is_pub(i))} for i in existing_rounds]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    to_publish = [i for i in existing_rounds if not is_pub(i)]
    if to_publish:
        sel_pub = st.selectbox("Ronda a publicar", to_publish, index=len(to_publish) - 1, key="pub_sel")
        if st.button("Publicar ronda seleccionada"):
            set_pub(sel_pub, True, seed=(r1_seed() if sel_pub == 1 else None))
            add_log("publish_round", sel_pub, actor, "Publicada desde sección Publicar")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok: st.success(f"Ronda {sel_pub} publicada. Clasificación recalculada y guardada en {path}")
            else: st.warning("Ronda publicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
    else:
        st.info("No hay rondas pendientes de publicar.")

    pubs = published_rounds_list()
    if pubs:
        last_pub = max(pubs)
        st.caption(f"Solo se puede **despublicar** la **última ronda publicada**, actualmente **Ronda {last_pub}**.")
        sel_unpub = last_pub
        if st.button(f"Despublicar Ronda {last_pub}"):
            set_pub(sel_unpub, False)
            add_log("unpublish_round", sel_unpub, actor, "Despublicada (última publicada)")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok: st.success(f"Ronda {sel_unpub} despublicada. Clasificación recalculada y guardada en {path}")
            else: st.warning("Ronda despublicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
    else:
        st.info("No hay rondas publicadas actualmente.")
else:
    st.info("Aún no hay rondas generadas.")

st.divider()

# ---------- Resultados y clasificación (solo PUBLICADAS) ----------
st.markdown("### Resultados y clasificación (solo PUBLICADAS)")
pubs = published_rounds_list()
if pubs:
    sel_r = st.selectbox("Ronda publicada a editar", pubs, index=len(pubs) - 1, key="res_round")
    dfp = read_csv_safe(round_file(sel_r))
    if dfp is not None:
        st.caption("Valores: 1-0, 0-1, 1/2-1/2, +/- , -/+, BYE1.0, BYE0.5, BYE")

        # --- Buffer por ronda + editor primero (para capturar selección) ---
        buf_key = f"res_buf_R{sel_r}"
        if buf_key not in st.session_state:
            base_df = dfp.copy()
            if "seleccionar" not in base_df.columns:
                base_df["seleccionar"] = False
            st.session_state[buf_key] = base_df
        else:
            for col in ["mesa","blancas_id","blancas_nombre","negras_id","negras_nombre","resultado"]:
                if col not in st.session_state[buf_key].columns:
                    st.session_state[buf_key][col] = dfp.get(col, "")
            if "seleccionar" not in st.session_state[buf_key].columns:
                st.session_state[buf_key]["seleccionar"] = False

        edited_now = st.data_editor(
            st.session_state[buf_key],
            use_container_width=True,
            hide_index=True,
            column_config={
                "seleccionar": st.column_config.CheckboxColumn("seleccionar", help="Marca las partidas a las que aplicar las acciones masivas"),
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

        def _sel(df):
            s = df.get("seleccionar", False)
            if hasattr(s, "astype"):
                try:
                    s = s.fillna(False).astype(bool)
                except Exception:
                    s = s == True
            return s == True
        def _is_bye_series(df): return df["negras_id"].astype(str).str.upper() == "BYE"
        def _is_empty_res(df): return df["resultado"].fillna("").astype(str).str.strip() == ""

        a1, a2, a3, a4, a5 = st.columns(5)
        with a1:
            if st.button("Completar con tablas (½-½)"):
                df = st.session_state[buf_key].copy()
                sel = _sel(df); elig = ~_is_bye_series(df)
                if solo_vacios: elig = elig & _is_empty_res(df)
                idxs = df.index[sel & elig].tolist()
                if not idxs: st.warning("No hay filas seleccionadas (y elegibles) para completar con tablas.")
                else:
                    df.loc[idxs, "resultado"] = "1/2-1/2"; st.session_state[buf_key] = df; st.rerun()
        with a2:
            if st.button("Ganan BLANCAS (1-0)"):
                df = st.session_state[buf_key].copy()
                sel = _sel(df); elig = ~_is_bye_series(df)
                if solo_vacios: elig = elig & _is_empty_res(df)
                idxs = df.index[sel & elig].tolist()
                if not idxs: st.warning("No hay filas seleccionadas (y elegibles) para poner 1-0.")
                else:
                    df.loc[idxs, "resultado"] = "1-0"; st.session_state[buf_key] = df; st.rerun()
        with a3:
            if st.button("Ganan NEGRAS (0-1)"):
                df = st.session_state[buf_key].copy()
                sel = _sel(df); elig = ~_is_bye_series(df)
                if solo_vacios: elig = elig & _is_empty_res(df)
                idxs = df.index[sel & elig].tolist()
                if not idxs: st.warning("No hay filas seleccionadas (y elegibles) para poner 0-1.")
                else:
                    df.loc[idxs, "resultado"] = "0-1"; st.session_state[buf_key] = df; st.rerun()
        with a4:
            if st.button("Completar BYEs"):
                df = st.session_state[buf_key].copy()
                sel = _sel(df); elig = _is_bye_series(df)
                if solo_vacios: elig = elig & _is_empty_res(df)
                idxs = df.index[sel & elig].tolist()
                if not idxs: st.warning("No hay filas seleccionadas (y elegibles) para completar BYEs.")
                else:
                    df.loc[idxs, "resultado"] = "BYE1.0"; st.session_state[buf_key] = df; st.rerun()
        with a5:
            if st.button("Vaciar resultados"):
                df = st.session_state[buf_key].copy()
                sel = _sel(df); idxs = df.index[sel].tolist()
                if not idxs: st.warning("No hay filas seleccionadas para vaciar resultados.")
                else:
                    df.loc[idxs, "resultado"] = ""; st.session_state[buf_key] = df; st.rerun()

        # Guardar (sin columna 'seleccionar' en CSV) y desmarcar tras guardar
        if st.button("Guardar resultados de la ronda"):
            outp = round_file(sel_r)
            df_to_save = st.session_state[buf_key].copy()
            if "seleccionar" in df_to_save.columns:
                df_to_save = df_to_save.drop(columns=["seleccionar"])
            df_to_save.astype(str).to_csv(outp, index=False, encoding="utf-8")
            add_log("save_results", sel_r, actor, "Resultados actualizados")
            # Reset de selección en el buffer tras guardar
            df_after = read_csv_safe(outp)
            if df_after is None:
                df_after = df_to_save.copy()
            df_after["seleccionar"] = False
            st.session_state[buf_key] = df_after
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok: st.success(f"Resultados guardados. Clasificación recalculada y guardada en {path}")
            else: st.warning("Resultados guardados, pero no se pudo recalcular la clasificación.")
            st.rerun()
else:
    st.info("No hay rondas publicadas todavía.")

st.divider()

# ---------- Eliminar ronda (solo la última existente) ----------
st.markdown("### Eliminar ronda")
existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
if existing_rounds:
    last_exist = max(existing_rounds)
    st.caption(f"Solo se puede **eliminar** la **última ronda generada**, actualmente **Ronda {last_exist}**.")
    dsel = last_exist
    warn = st.text_input(f'Escribe "ELIMINAR R{dsel}" para confirmar', "")
    if st.button(f"Eliminar definitivamente Ronda {dsel}") and warn.strip().upper() == f"ELIMINAR R{dsel}":
        path = round_file(dsel)
        try:
            os.remove(path)
            meta = load_meta()
            if str(dsel) in meta.get("rounds", {}):
                meta["rounds"].pop(str(dsel), None); save_meta(meta)
            add_log("delete_round", dsel, actor, f"pairings_R{dsel}.csv eliminado")
            ok, path2 = recalc_and_save_standings(bye_points=1.0)
            if ok: st.success(f"Ronda R{dsel} eliminada. Clasificación recalculada y guardada en {path2}")
            else: st.info("Ronda eliminada. No hay jugadores o no se pudo recalcular la clasificación.")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo eliminar: {e}")
else:
    st.info("No hay rondas para eliminar.")

st.divider()

# ---------- Inspector de data/ ----------
st.markdown("### Archivos en data/ (inspector rápido)")
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
                sz = 0
                mt = "—"
            rows.append({"archivo": f, "tamaño_bytes": sz, "modificado": mt})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("data/ está vacío.")
except Exception as e:
    st.warning(f"No se pudo listar data/: {e}")


