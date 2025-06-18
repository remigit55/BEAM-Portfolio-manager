# taux_change.py
import streamlit as st
import pandas as pd
import datetime

def afficher_taux_change():
    if "fx_rates" in st.session_state and st.session_state.fx_rates:
        devise_cible = st.session_state.get("devise_cible", "EUR")
        st.markdown(f"Taux appliqués pour conversion en **{devise_cible}** au **{datetime.date.today()}**")
        fx_df = pd.DataFrame(
            list(st.session_state.fx_rates.items()),
            columns=["Conversion", "Taux"]
        )
        st.dataframe(fx_df, use_container_width=True)
    else:
        st.info("Aucun taux de change disponible. Veuillez d'abord importer un portefeuille.")
