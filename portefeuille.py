# portefeuille.py

import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import requests

def afficher_portefeuille():

    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Affichage brut des colonnes du CSV importé, sans transformation
    st.dataframe(df, use_container_width=True)
