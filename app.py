"""Legacy Streamlit entry point.

The optimizer moved to a static site: https://jlattanzi4.github.io/nfl-survivor-optimizer/
This stub keeps the old Streamlit Cloud URL working as a redirect.
"""
import streamlit as st

NEW_URL = "https://jlattanzi4.github.io/nfl-survivor-optimizer/"

st.set_page_config(page_title="NFL Survivor Pool Optimizer has moved")
st.markdown(f'<meta http-equiv="refresh" content="2; url={NEW_URL}">', unsafe_allow_html=True)
st.title("This app has moved")
st.markdown(f"The NFL Survivor Pool Optimizer now lives at **[{NEW_URL}]({NEW_URL})**. Redirecting…")
st.link_button("Open the new optimizer", NEW_URL, type="primary")
