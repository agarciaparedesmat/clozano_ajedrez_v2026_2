
import streamlit as st, os, pandas as pd, random, hashlib
from lib.tournament import (
    load_config, save_config, load_meta, save_meta, read_csv_safe, write_csv, last_modified,
    read_players_from_csv, apply_results, swiss_pair_round, formatted_name_from_parts,
    list_round_files, is_published, set_published, r1_seed, add_log, parse_bye_points,
    compute_standings, export_pdf_players, DATA_DIR
)

st.header("Panel de Administración")
pwd = st.text_input("Contraseña", type="password")
if not pwd or pwd != st.secrets.get("ADMIN_PASS", ""):
    st.stop()
st.success("Acceso concedido ✅")

actor = st.text_input("Tu nombre (registro de cambios)", value=st.session_state.get("actor_name", "Admin"))
st.session_state["actor_name"] = actor

cfg = load_config()
jug_path = os.path.join(DATA_DIR, "jugadores.csv")

st.markdown("### Emparejar (sistema suizo)")
jug_up = st.file_uploader("Subir/actualizar jugadores.csv", type=["csv"], key="jug_csv")
if jug_up is not None:
    with open(jug_path, "wb") as f: f.write(jug_up.read())
    st.success("jugadores.csv actualizado.")

n = int(cfg.get("rondas", 5))
completed = 0
for i in range(1, n+1):
    p = os.path.join(DATA_DIR, f"pairings_R{i}.csv")
    dfp = read_csv_safe(p)
    if dfp is None: break
    if "resultado" in dfp.columns and all(str(x).strip() != "" for x in dfp["resultado"].fillna("")):
        completed = i
    else: break
next_round = completed + 1
st.write(f"Rondas cerradas: **{completed}** / {n}")
st.write(f"Siguiente ronda: **Ronda {next_round}**")
st.caption(f"Semilla usada en R1: `{r1_seed() or '—'}`")

forced_bye_id = None
jug_df = read_csv_safe(jug_path)
options = ["— Ninguno —"]; idmap = {}
players_preview = []
if jug_df is not None and not jug_df.empty:
    players_preview = read_players_from_csv(jug_path)
    for rno in range(1, next_round):
        dfp_prev = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
        players_preview = apply_results(players_preview, dfp_prev, bye_points=1.0)
    for p in players_preview:
        if str(p.get("estado","activo")).lower()=="retirado": continue
        tag = " (ya BYE)" if p.get("_had_bye", False) else ""
        label = f"{p['id']} — {formatted_name_from_parts(p['nombre'],p['apellido1'],p['apellido2'])}{tag}"
        options.append(label); idmap[label] = p['id']
sel = st.selectbox("Forzar BYE (opcional)", options, index=0)
if sel in idmap: forced_bye_id = int(idmap[sel])

seed_input = ""
if next_round == 1:
    seed_input = st.text_input("Semilla de aleatoriedad (opcional)", value="")

if is_published(next_round):
    st.warning(f"La Ronda {next_round} está **PUBLICADA**. Elimínala abajo para rehacerla.")
else:
    if st.button(f"Generar Ronda {next_round}"):
        if next_round == 1:
            seed_used = seed_input.strip() or "seed-" + str(random.randint(100000,999999))
            random.seed(seed_used)
        else:
            seed_used = None
        players = read_players_from_csv(jug_path)
        if not players: st.error("No se pudo leer `data/jugadores.csv`.")
        else:
            for rno in range(1, next_round):
                dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
                players = apply_results(players, dfp, bye_points=1.0)
            df_pairs = swiss_pair_round(players, next_round, forced_bye_id=forced_bye_id)
            edited = st.data_editor(df_pairs, use_container_width=True, hide_index=True, key=f"preview_R{next_round}", num_rows="dynamic")
            c1,c2,c3 = st.columns(3)
            with c1:
                if st.button(f"Guardar pairings_R{next_round}.csv"):
                    outp = os.path.join(DATA_DIR, f"pairings_R{next_round}.csv")
                    edited.astype(str).to_csv(outp, index=False, encoding="utf-8")
                    if next_round == 1 and seed_used is not None:
                        set_published(1, published=False, seed=seed_used)
                    add_log("save_pairings", next_round, actor, "Guardado manual")
                    st.success(f"Guardado en {outp}")
            with c2:
                csv_bytes = edited.to_csv(index=False).encode("utf-8")
                st.download_button("Descargar CSV (previo)", csv_bytes, file_name=f"pairings_R{next_round}.csv", mime="text/csv")
            with c3:
                outp = os.path.join(DATA_DIR, f"pairings_R{next_round}.csv")
                if os.path.exists(outp):
                    if st.button(f"Publicar Ronda {next_round}"):
                        set_published(next_round, published=True, seed=(r1_seed() if next_round==1 else None))
                        add_log("publish_round", next_round, actor, "Ronda publicada")
                        st.success("Ronda publicada. Ahora puedes introducir resultados.")

st.divider()
st.markdown("#### Calcular clasificación")
bye_pts = st.number_input("Puntos por BYE (por defecto si 'BYE')", min_value=0.0, max_value=1.0, value=1.0, step=0.5)
max_round = max([i for i in range(1, n+1) if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv"))] + [0])
if max_round < 1:
    st.info("Aún no hay ninguna ronda generada/publicada. Genera y publica una ronda antes de calcular la clasificación.")
    upto = 1
else:
    upto = st.slider("Calcular hasta la ronda", min_value=1, max_value=max_round, value=max_round, key="upto_slider")
if st.button("Calcular y guardar clasificación"):
    players = read_players_from_csv(jug_path)
    if not players: st.error("No se pudo leer jugadores.csv")
    else:
        for rno in range(1, upto+1):
            dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
            players = apply_results(players, dfp, bye_points=float(bye_pts))
        from lib.tournament import compute_standings
        df_st = compute_standings(players)
        outp = os.path.join(DATA_DIR, "standings.csv")
        df_st.to_csv(outp, index=False, encoding="utf-8")
        st.success(f"Clasificación guardada en {outp}")
        st.dataframe(df_st, use_container_width=True, hide_index=True)

st.divider()
st.markdown("### Listado de jugadores (PDF)")
from lib.tournament import export_pdf_players, load_config, read_csv_safe
cfg = load_config()
jug_df = read_csv_safe(os.path.join(DATA_DIR,"jugadores.csv"))
if jug_df is None or jug_df.empty:
    st.info("Sube `jugadores.csv` primero.")
else:
    if st.button("Exportar listado (PDF)"):
        buff = export_pdf_players(jug_df, cfg)
        st.download_button("Descargar listado", buff, file_name="listado_jugadores.pdf", mime="application/pdf")
