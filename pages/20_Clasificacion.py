
import streamlit as st, os, pandas as pd
from lib.tournament import read_csv_safe, last_modified, DATA_DIR

st.header("Clasificación")
st_path = os.path.join(DATA_DIR, "standings.csv")
df = read_csv_safe(st_path)
if df is None or df.empty:
    st.warning("Aún no hay `standings.csv`.")
else:
    for c in ["puntos","buchholz_c1","buchholz","sonneborn_berger","progresivo","id"]:
        if c in df.columns:
            try: df[c] = pd.to_numeric(df[c])
            except: pass
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(f"Última actualización: {last_modified(st_path)}")
