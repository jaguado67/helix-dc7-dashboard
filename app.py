import streamlit as st

st.set_page_config(
    page_title="HELIX Dashboards",
    page_icon="📊",
    layout="wide",
)

st.title("HELIX Dashboards")
st.info(
    "This repository contains two independent Streamlit applications. "
    "Deploy DC7 from DC7/app.py and DC7.TFO from DC7.TFO/app.py."
)

c1, c2 = st.columns(2)
with c1:
    st.subheader("DC7")
    st.code("DC7/app.py")
with c2:
    st.subheader("DC7.TFO")
    st.code("DC7.TFO/app.py")
