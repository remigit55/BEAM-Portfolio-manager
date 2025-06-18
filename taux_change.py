# taux_change.py
import streamlit as st
import pandas as pd
import datetime

st.subheader("Taux de change utilisés")

if "fx_rates" in st.session_state and st.session_state.fx_rates:
    st.markdown(f"Taux appliqués pour conversion en **{st.session_state.devise_cible}** au **{datetime.date.today()}**")
    st.dataframe(pd.DataFrame(list(st.session_state.fx_rates.items()), columns=["Conversion", "Taux"]))
elif "fx" in st.session_state:
    st.subheader("Taux de change (importés manuellement)")
    st.dataframe(st.session_state.fx, use_container_width=True)
else:
    st.info("Aucun taux de change disponible actuellement. Veuillez importer un portefeuille ou des taux manuellement.")
