
import streamlit as st, os
from lib.tournament import load_config, read_csv_safe, list_round_files, last_modified, is_published, export_pdf_pairings, export_pdf_results

st.header("Rondas")
cfg = load_config()
n = int(cfg.get("rondas", 5))

for i, path in list_round_files(n):
    with st.expander(f"Ronda {i}", expanded=(i==1)):
        df = read_csv_safe(path)
        if df is None or df.empty:
            st.info("Aún no disponible.")
        else:
            pub = is_published(i)
            st.markdown(f"**Estado:** {'🟢 Publicada' if pub else '🟡 No publicada'}")
            st.dataframe(df, use_container_width=True, hide_index=True)
            st.caption(f"Archivo: pairings_R{i}.csv — Última actualización: {last_modified(path)}")
            c1, c2 = st.columns(2)
            with c1:
                if st.button(f"PDF emparejamientos R{i}", key=f"pairpdf_{i}"):
                    buff = export_pdf_pairings(i, df, cfg)
                    st.download_button("Descargar", buff, file_name=f"emparejamientos_R{i}.pdf", mime="application/pdf")
            with c2:
                if st.button(f"PDF resultados R{i}", key=f"respdf_{i}"):
                    buff = export_pdf_results(i, df, cfg)
                    st.download_button("Descargar", buff, file_name=f"resultados_R{i}.pdf", mime="application/pdf")
