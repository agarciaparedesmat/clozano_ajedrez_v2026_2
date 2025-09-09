# lib/ui.py
# -*- coding: utf-8 -*-
import streamlit as st

_HEADER_CSS = """
<style>
.app-header {
  padding: 1.0rem 1.25rem;
  border-radius: 12px;
  background: linear-gradient(90deg, rgba(30,64,175,0.08) 0%, rgba(30,64,175,0.02) 100%);
  border: 1px solid rgba(30,64,175,0.12);
  margin-bottom: 0.75rem;
}
.app-header h1 {
  font-size: 1.35rem;
  margin: 0;
  line-height: 1.3;
}
.app-header p {
  margin: 0.25rem 0 0 0;
  color: rgba(15,23,42,0.80);
  font-size: 0.95rem;
}
</style>
"""

def page_header(title: str, subtitle: str = ""):
    st.markdown(_HEADER_CSS, unsafe_allow_html=True)
    html = f"<div class='app-header'><h1>{title}</h1>"
    if subtitle:
        html += f"<p>{subtitle}</p>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
