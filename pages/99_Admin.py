
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
    pub = is_published(i) if exists else False
    closed = exists and (empties == 0)
    return {"i": i, "exists": exists, "published": pub, "empties": empties, "closed": closed, "path": p}

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
gen_rounds = [s["i"] for s in states if s["exists"]]
closed_rounds = [s["i"] for s in states if s["closed"]]
first_missing = next((i for i in range(1, n+1) if not states[i-1]["exists"]), None)
last_gen = max(gen_rounds) if gen_rounds else 0

st.markdown("#### Estado de rondas")
diag = pd.DataFrame([
    {"Ronda": s["i"],
     "Generada": "Sí" if s["exists"] else "No",
     "Publicada": "Sí" if s["published"] else "No",
     "Resultados vacíos": ("—" if s["empties"] is None else s["empties"]),
     "Cerrada (sin vacíos)": "Sí" if s["closed"] else "No",
     "Archivo": os.path.basename(s["path"])}
    for s in states
])
st.dataframe(diag, use_container_width=True, hide_index=True)
st.write(f"Rondas cerradas: **{len(closed_rounds)}** / {n}")

# ---------- Determinar siguiente ronda a generar ----------
if first_missing is None:
    st.success("✅ Todas las rondas están generadas.")
    next_round = None
else:
    next_round = first_missing
    prev = next_round - 1
    if prev >= 1:
        prev_state = states[prev-1]
        if not prev_state["closed"]:
            st.warning(f"No se puede generar la Ronda {next_round} porque la Ronda {prev} no está cerrada. "
                       f"Faltan **{prev_state['empties']}** resultados por rellenar en `pairings_R{prev}.csv`.")
            # Opción de emergencia (bajo tu responsabilidad)
            force = st.checkbox("⚠️ Forzar generación de la siguiente ronda aunque la anterior no esté cerrada", value=False)
            if not force:
                next_round = prev  # bloquea el botón de generar a la ronda pendiente
    st.write(f"Siguiente ronda candidata: **Ronda {next_round if next_round else '—'}**")

# ---------- Generar ronda ----------
if next_round is not None:
    if is_published(next_round):
        st.warning(f"La Ronda {next_round} está **PUBLICADA**. Despublícala para rehacerla.")
    else:
        if st.button(f"Generar Ronda {next_round}"):
            # Semilla solo en R1
            if next_round == 1:
                seed_input = st.text_input("Semilla de aleatoriedad (opcional)", value="", key="seed_r1")
                seed_used = seed_input.strip() or "seed-" + str(random.randint(100000, 999999))
                random.seed(seed_used)
            else:
                seed_used = None

            players = read_players_from_csv(jug_path)
            if not players:
                st.error("No se pudo leer `data/jugadores.csv`.")
            else:
                # acumular resultados publicados anteriores para el pairing
                for rno in range(1, next_round):
                    dfp = read_csv_safe(round_file(rno))
                    players = apply_results(players, dfp, bye_points=1.0)

                df_pairs = swiss_pair_round(players, next_round, forced_bye_id=None)
                outp = round_file(next_round)
                df_pairs.astype(str).to_csv(outp, index=False, encoding="utf-8")
                if next_round == 1 and seed_used is not None:
                    # guardar semilla visiblemente aunque R1 aún no esté publicada
                    meta = load_meta(); meta.setdefault("rounds", {}).setdefault("1", {})["seed"] = seed_used; save_meta(meta)
                add_log("auto_save_pairings_on_generate", next_round, actor, f"Guardado inicial en {outp}")
                st.success(f"Ronda {next_round} generada y guardada en {outp}")
                st.rerun()

st.divider()

# ---------- Publicar / Despublicar ----------
st.markdown("### Publicar / Despublicar rondas")
existing_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
if existing_rounds:
    status_rows = [{"ronda": i, "publicada": bool(is_published(i))} for i in existing_rounds]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    to_publish = [i for i in existing_rounds if not is_published(i)]
    if to_publish:
        sel_pub = st.selectbox("Ronda a publicar", to_publish, index=len(to_publish) - 1, key="pub_sel")
        if st.button("Publicar ronda seleccionada"):
            set_published(sel_pub, True, seed=(r1_seed() if sel_pub == 1 else None))
            add_log("publish_round", sel_pub, actor, "Publicada desde sección Publicar")
            # Auto-recalc standings (BYE=1.0)
            players = read_players_from_csv(jug_path)
            pubs = sorted([i for i in range(1, n+1) if os.path.exists(round_file(i)) and is_published(i)])
            for rno in pubs:
                dfp = read_csv_safe(round_file(rno)); players = apply_results(players, dfp, bye_points=1.0)
            df_st = compute_standings(players); df_st.to_csv(os.path.join(DATA_DIR, "standings.csv"), index=False, encoding="utf-8")
            st.success("Ronda publicada y clasificación recalculada.")
            st.rerun()
    else:
        st.info("No hay rondas pendientes de publicar.")

    to_unpub = [i for i in existing_rounds if is_published(i)]
    if to_unpub:
        sel_unpub = st.selectbox("Ronda a despublicar", to_unpub, index=len(to_unpub) - 1, key="unpub_sel")
        if st.button("Despublicar ronda seleccionada"):
            set_published(sel_unpub, False)
            add_log("unpublish_round", sel_unpub, actor, "Despublicada")
            # Auto-recalc standings (BYE=1.0)
            players = read_players_from_csv(jug_path)
            pubs = sorted([i for i in range(1, n+1) if os.path.exists(round_file(i)) and is_published(i)])
            for rno in pubs:
                dfp = read_csv_safe(round_file(rno)); players = apply_results(players, dfp, bye_points=1.0)
            df_st = compute_standings(players); df_st.to_csv(os.path.join(DATA_DIR, "standings.csv"), index=False, encoding="utf-8")
            st.success("Ronda despublicada y clasificación recalculada.")
            st.rerun()
else:
    st.info("Aún no hay rondas generadas.")

st.divider()

# ---------- Resultados y clasificación (solo PUBLICADAS) ----------
st.markdown("### Resultados y clasificación (solo PUBLICADAS)")
pubs = sorted([i for i in range(1, n+1) if os.path.exists(round_file(i)) and is_published(i)])
if pubs:
    sel_r = st.selectbox("Ronda publicada a editar", pubs, index=len(pubs) - 1, key="res_round")
    dfp = read_csv_safe(round_file(sel_r))
    if dfp is not None:
        st.caption("Valores: 1-0, 0-1, 1/2-1/2, +/- , -/+, BYE1.0, BYE0.5, BYE")
        options_res = ["", "1-0", "0-1", "1/2-1/2", "+/-", "-/+", "BYE1.0", "BYE0.5", "BYE"]
        for col in ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]:
            if col not in dfp.columns: dfp[col] = ""
        edited_res = st.data_editor(
            dfp, use_container_width=True, hide_index=True,
            column_config={"resultado": st.column_config.SelectboxColumn("resultado", options=options_res, required=False)},
            num_rows="fixed", key=f"results_R{sel_r}"
        )
        if st.button("Guardar resultados de la ronda"):
            outp = round_file(sel_r)
            edited_res.astype(str).to_csv(outp, index=False, encoding="utf-8")
            add_log("save_results", sel_r, actor, "Resultados actualizados")
            # Auto-recalc standings (BYE=1.0)
            players = read_players_from_csv(jug_path)
            for rno in pubs:
                dfpr = read_csv_safe(round_file(rno)); players = apply_results(players, dfpr, bye_points=1.0)
            df_st = compute_standings(players); df_st.to_csv(os.path.join(DATA_DIR, "standings.csv"), index=False, encoding="utf-8")
            st.success("Resultados guardados y clasificación recalculada.")
            st.rerun()
else:
    st.info("No hay rondas publicadas todavía.")

st.divider()

# ---------- Eliminar ronda ----------
st.markdown("### Eliminar ronda")
del_rounds = [i for i in range(1, n + 1) if os.path.exists(round_file(i))]
if del_rounds:
    dsel = st.selectbox("Ronda a eliminar", del_rounds, index=len(del_rounds) - 1)
    warn = st.text_input(f'Escribe "ELIMINAR R{dsel}" para confirmar', "")
    if st.button("Eliminar definitivamente") and warn.strip().upper() == f"ELIMINAR R{dsel}":
        path = round_file(dsel)
        try:
            os.remove(path)
            meta = load_meta()
            if str(dsel) in meta.get("rounds", {}):
                meta["rounds"].pop(str(dsel), None); save_meta(meta)
            add_log("delete_round", dsel, actor, f"pairings_R{dsel}.csv eliminado")
            # Auto-recalc standings (BYE=1.0)
            players = read_players_from_csv(jug_path)
            pubs = sorted([i for i in range(1, n+1) if os.path.exists(round_file(i)) and is_published(i)])
            for rno in pubs:
                dfp = read_csv_safe(round_file(rno)); players = apply_results(players, dfp, bye_points=1.0)
            df_st = compute_standings(players); df_st.to_csv(os.path.join(DATA_DIR, "standings.csv"), index=False, encoding="utf-8")
            st.success("Ronda eliminada y clasificación recalculada.")
            st.rerun()
        except Exception as e:
            st.error(f"No se pudo eliminar: {e}")
else:
    st.info("No hay rondas para eliminar.")
