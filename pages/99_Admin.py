
import streamlit as st
import os
import pandas as pd
import random
import hashlib

from lib.tournament import (
    load_config, save_config, load_meta, save_meta, read_csv_safe, write_csv, last_modified,
    read_players_from_csv, apply_results, swiss_pair_round, formatted_name_from_parts,
    list_round_files, is_published, set_published, r1_seed, add_log, parse_bye_points,
    compute_standings, DATA_DIR
)

st.header("Panel de Administración")

pwd = st.text_input("Contraseña", type="password")
if not pwd or pwd != st.secrets.get("ADMIN_PASS", ""):
    st.stop()
st.success("Acceso concedido ✅")

actor = st.text_input("Tu nombre (registro de cambios)", value=st.session_state.get("actor_name", "Admin"))
st.session_state["actor_name"] = actor

cfg = load_config()
n = int(cfg.get("rondas", 5))
jug_path = os.path.join(DATA_DIR, "jugadores.csv")

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

seed_input = ""
if next_round == 1:
    seed_input = st.text_input("Semilla de aleatoriedad (opcional)", value="")

if is_published(next_round):
    st.warning(f"La Ronda {next_round} está **PUBLICADA**. Elimínala abajo para rehacerla.")
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

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button(f"Guardar pairings_R{next_round}.csv"):
                    edited.astype(str).to_csv(outp, index=False, encoding="utf-8")
                    add_log("save_pairings", next_round, actor, "Guardado manual")
                    st.success(f"Guardado en {outp}")
            with c2:
                csv_bytes = edited.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar CSV (previo)", csv_bytes, file_name=f"pairings_R{next_round}.csv", mime="text/csv")
            with c3:
                if os.path.exists(outp):
                    if st.button(f"Publicar Ronda {next_round}"):
                        set_published(next_round, published=True, seed=(r1_seed() if next_round == 1 else None))
                        add_log("publish_round", next_round, actor, "Ronda publicada")
                        st.success("Ronda publicada. Ahora puedes introducir resultados.")

st.divider()
st.markdown("### Resultados y clasificación")

rounds_available = [i for i in range(1, n + 1) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv"))]
published_rounds = [i for i in rounds_available if is_published(i)] if rounds_available else []

if published_rounds:
    sel_r = st.selectbox("Ronda publicada a editar", published_rounds, index=len(published_rounds) - 1, key="res_round")
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
            st.success(f"Resultados guardados en {outp}")
else:
    st.info("No hay rondas publicadas todavía.")

st.markdown("#### Calcular clasificación")
bye_pts = st.number_input("Puntos por BYE (por defecto si 'BYE')", min_value=0.0, max_value=1.0, value=1.0, step=0.5)
max_round = max([i for i in range(1, n + 1) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv"))] + [0])

# --- Slider seguro (evita rango [1,1]) ---
if max_round < 1:
    st.info("Aún no hay ninguna ronda generada/publicada. Genera y publica una ronda antes de calcular la clasificación.")
    upto = 1
elif max_round == 1:
    st.caption("Hay una sola ronda disponible. Se calculará la clasificación hasta la **Ronda 1**.")
    upto = 1
else:
    upto = st.slider("Calcular hasta la ronda", min_value=1, max_value=int(max_round), value=int(max_round), key="upto_slider")

if st.button("Calcular clasificación y guardar"):
    players = read_players_from_csv(jug_path)
    if not players:
        st.error("No se pudo leer jugadores.csv")
    else:
        for rno in range(1, upto + 1):
            dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
            players = apply_results(players, dfp, bye_points=float(bye_pts))
        df_st = compute_standings(players)
        outp = os.path.join(DATA_DIR, "standings.csv")
        df_st.to_csv(outp, index=False, encoding="utf-8")
        st.success(f"Clasificación guardada en {outp}")
        st.dataframe(df_st, use_container_width=True, hide_index=True)

st.divider()
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
            st.success(f"Ronda R{dsel} eliminada.")
        except Exception as e:
            st.error(f"No se pudo eliminar: {e}")
else:
    st.info("No hay rondas para eliminar.")

st.divider()
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
