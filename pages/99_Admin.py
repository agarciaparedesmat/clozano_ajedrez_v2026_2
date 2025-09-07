
import streamlit as st
import os
import pandas as pd
import random

from lib.tournament import (
    load_config, load_meta, save_meta, read_csv_safe, write_csv, last_modified,
    read_players_from_csv, apply_results, swiss_pair_round, formatted_name_from_parts,
    list_round_files, is_published, set_published, r1_seed, add_log,
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
def published_rounds(n):
    return sorted([i for i in range(1, n+1)
                   if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv")) and is_published(i)])

def recalc_and_save_standings(bye_points=1.0):
    players = read_players_from_csv(jug_path)
    if not players:
        return False, "No se pudo leer jugadores.csv"
    pubs = published_rounds(n)
    for rno in pubs:
        dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
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

# ---------- Siguiente ronda ----------
completed = 0
for i in range(1, n + 1):
    p = os.path.join(DATA_DIR, f"pairings_R{i}.csv")
    dfp = read_csv_safe(p)
    if dfp is None:
        break
    if "resultado" in dfp.columns and all(str(x).strip() != "" for x in dfp["resultado"].fillna("")):
        completed = i
    else:
        break

next_round = completed + 1
st.write(f"Rondas cerradas: **{completed}** / {n}")
st.write(f"Siguiente ronda: **Ronda {next_round}**")
st.caption(f"Semilla usada en R1: `{r1_seed() or '—'}`")

# ---------- Forzar BYE ----------
forced_bye_id = None
jug_df = read_csv_safe(jug_path)
options = ["— Ninguno —"]
idmap = {}
players_preview = []

if jug_df is not None and not jug_df.empty:
    players_preview = read_players_from_csv(jug_path)
    for rno in range(1, next_round):
        dfp_prev = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
        players_preview = apply_results(players_preview, dfp_prev, bye_points=1.0)
    for p in players_preview:
        if str(p.get("estado", "activo")).lower() == "retirado":
            continue
        tag = " (ya BYE)" if p.get("_had_bye", False) else ""
        label = f"{p['id']} — {formatted_name_from_parts(p['nombre'], p['apellido1'], p['apellido2'])}{tag}"
        options.append(label)
        idmap[label] = p['id']

sel = st.selectbox("Forzar BYE (opcional)", options, index=0)
if sel in idmap:
    forced_bye_id = int(idmap[sel])

# ---------- Semilla R1 ----------
seed_input = ""
if next_round == 1:
    seed_input = st.text_input("Semilla de aleatoriedad (opcional)", value="")

# ---------- Generar ronda ----------
if is_published(next_round):
    st.warning(f"La Ronda {next_round} está **PUBLICADA**. Elimínala abajo para rehacerla, o despublícala en la sección inferior.")
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
                dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
                players = apply_results(players, dfp, bye_points=1.0)

            df_pairs = swiss_pair_round(players, next_round, forced_bye_id=forced_bye_id)

            outp = os.path.join(DATA_DIR, f"pairings_R{next_round}.csv")
            df_pairs.astype(str).to_csv(outp, index=False, encoding="utf-8")
            if next_round == 1 and seed_used is not None:
                set_published(1, published=False, seed=seed_used)
            add_log("auto_save_pairings_on_generate", next_round, actor, f"Guardado inicial en {outp}")

            st.success(f"Ronda {next_round} generada y guardada en {outp}")
            st.caption(f"Archivo actual: {outp}")
            st.caption("Puedes editar la tabla y volver a guardar si lo deseas.")

            edited = st.data_editor(
                df_pairs,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "resultado": st.column_config.SelectboxColumn(
                        "resultado",
                        options=["", "BYE1.0", "BYE0.5"],
                        required=False
                    )
                },
                num_rows="dynamic",
                key=f"preview_R{next_round}"
            )

            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"Guardar pairings_R{next_round}.csv"):
                    edited.astype(str).to_csv(outp, index=False, encoding="utf-8")
                    add_log("save_pairings", next_round, actor, "Guardado manual")
                    st.success(f"Guardado en {outp}")
            with c2:
                csv_bytes = edited.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar CSV (previo)", csv_bytes, file_name=f"pairings_R{next_round}.csv", mime="text/csv")

# ---------- Publicar / Despublicar ----------
st.divider()
st.markdown("### Publicar / Despublicar rondas")
existing_rounds = [i for i in range(1, n + 1) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv"))]
if existing_rounds:
    status_rows = [{"ronda": i, "publicada": bool(is_published(i))} for i in existing_rounds]
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    to_publish = [i for i in existing_rounds if not is_published(i)]
    if to_publish:
        sel_pub = st.selectbox("Ronda a publicar", to_publish, index=len(to_publish) - 1, key="pub_sel")
        if st.button("Publicar ronda seleccionada"):
            set_published(sel_pub, True, seed=(r1_seed() if sel_pub == 1 else None))
            add_log("publish_round", sel_pub, actor, "Publicada desde sección Publicar")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Ronda {sel_pub} publicada. Clasificación recalculada y guardada en {path}")
            else:
                st.warning("Ronda publicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
    else:
        st.info("No hay rondas pendientes de publicar.")

    to_unpub = [i for i in existing_rounds if is_published(i)]
    if to_unpub:
        sel_unpub = st.selectbox("Ronda a despublicar", to_unpub, index=len(to_unpub) - 1, key="unpub_sel")
        if st.button("Despublicar ronda seleccionada"):
            set_published(sel_unpub, False)
            add_log("unpublish_round", sel_unpub, actor, "Despublicada")
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Ronda {sel_unpub} despublicada. Clasificación recalculada y guardada en {path}")
            else:
                st.warning("Ronda despublicada, pero no se pudo recalcular la clasificación.")
            st.rerun()
else:
    st.info("Aún no hay rondas generadas.")

st.divider()

# ---------- Resultados y clasificación ----------
st.markdown("### Resultados y clasificación (solo PUBLICADAS)")
pubs = published_rounds(n)
if pubs:
    sel_r = st.selectbox("Ronda publicada a editar", pubs, index=len(pubs) - 1, key="res_round")
    dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{sel_r}.csv"))
    if dfp is not None:
        st.caption("Valores: 1-0, 0-1, 1/2-1/2, +/- , -/+, BYE1.0, BYE0.5, BYE")
        options_res = ["", "1-0", "0-1", "1/2-1/2", "+/-", "-/+", "BYE1.0", "BYE0.5", "BYE"]
        for col in ["mesa", "blancas_id", "blancas_nombre", "negras_id", "negras_nombre", "resultado"]:
            if col not in dfp.columns:
                dfp[col] = ""
        edited_res = st.data_editor(
            dfp,
            use_container_width=True,
            hide_index=True,
            column_config={
                "resultado": st.column_config.SelectboxColumn("resultado", options=options_res, required=False)
            },
            num_rows="fixed",
            key=f"results_R{sel_r}"
        )
        if st.button("Guardar resultados de la ronda"):
            outp = os.path.join(DATA_DIR, f"pairings_R{sel_r}.csv")
            edited_res.astype(str).to_csv(outp, index=False, encoding="utf-8")
            add_log("save_results", sel_r, actor, "Resultados actualizados")
            # Auto-recalc standings when saving results of a PUBLISHED round
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Resultados guardados. Clasificación recalculada y guardada en {path}")
            else:
                st.warning("Resultados guardados, pero no se pudo recalcular la clasificación.")
            st.rerun()
else:
    st.info("No hay rondas publicadas todavía.")

st.divider()

# ---------- Eliminar ronda ----------
st.markdown("### Eliminar ronda")
del_rounds = [i for i in range(1, n + 1) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv"))]
if del_rounds:
    dsel = st.selectbox("Ronda a eliminar", del_rounds, index=len(del_rounds) - 1)
    warn = st.text_input(f'Escribe "ELIMINAR R{dsel}" para confirmar', "")
    if st.button("Eliminar definitivamente") and warn.strip().upper() == f"ELIMINAR R{dsel}":
        path = os.path.join(DATA_DIR, f"pairings_R{dsel}.csv")
        try:
            os.remove(path)
            meta = load_meta()
            if str(dsel) in meta.get("rounds", {}):
                meta["rounds"].pop(str(dsel), None)
                save_meta(meta)
            add_log("delete_round", dsel, actor, f"pairings_R{dsel}.csv eliminado")
            # After deleting a round, recalc standings (BYE=1.0) based on remaining published rounds
            ok, path = recalc_and_save_standings(bye_points=1.0)
            if ok:
                st.success(f"Ronda R{dsel} eliminada. Clasificación recalculada y guardada en {path}")
            else:
                st.info("Ronda eliminada. No hay jugadores o no se pudo recalcular la clasificación.")
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
