import streamlit as st

st.set_page_config(
    page_title="HELIX Project Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

dc7 = st.Page(
    "DC7/app.py",
    title="DC7",
    icon=":material/dashboard:",
    default=True,
)

dc7_tfo = st.Page(
    "DC7.TFO/app.py",
    title="DC7.TFO",
    icon=":material/electrical_services:",
)

page = st.navigation([dc7, dc7_tfo], position="top")
page.run()
