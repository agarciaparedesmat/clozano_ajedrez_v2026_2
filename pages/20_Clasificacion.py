
import streamlit as st
import os
import pandas as pd

from lib.tournament import (
    load_config, read_csv_safe, read_players_from_csv, apply_results, compute_standings,
    is_published, DATA_DIR
)

st.header("Clasificación")

cfg = load_config()
n = int(cfg.get("rondas", 5))
jug_path = os.path.join(DATA_DIR, "jugadores.csv")

# --- Auto-recalcular SIEMPRE con rondas PUBLICADAS (BYE=1.0) ---
players = read_players_from_csv(jug_path)
if not players:
    st.warning("Aún no hay `jugadores.csv`.")
else:
    published = [i for i in range(1, n+1)
                 if os.path.exists(os.path.join(DATA_DIR, f"pairings_R{i}.csv")) and is_published(i)]
    published = sorted(published)
    if not published:
        st.info("No hay rondas PUBLICADAS. La clasificación aparecerá cuando publiques al menos una ronda.")
    else:
        for rno in published:
            dfp = read_csv_safe(os.path.join(DATA_DIR, f"pairings_R{rno}.csv"))
            players = apply_results(players, dfp, bye_points=1.0)  # BYE por defecto = 1.0
        df_st = compute_standings(players)
        # Guardar para descarga o uso externo
        outp = os.path.join(DATA_DIR, "standings.csv")
        df_st.to_csv(outp, index=False, encoding="utf-8")

        # Mostrar
        # Convertir a tipos numéricos si procede
        for c in ["puntos","buchholz_c1","buchholz","sonneborn_berger","progresivo","id"]:
            if c in df_st.columns:
                try:
                    df_st[c] = pd.to_numeric(df_st[c])
                except Exception:
                    pass
        st.dataframe(df_st, use_container_width=True, hide_index=True)
        st.caption(f"Rondas publicadas consideradas: {', '.join(map(str, published))}")
        st.caption(f"Guardado en: data/standings.csv")
