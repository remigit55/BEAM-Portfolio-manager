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

    # Mise en forme des colonnes numériques si présentes
    if "Quantité" in df.columns:
        df["Quantité"] = pd.to_numeric(df["Quantité"], errors="coerce")
    if "Acquisition" in df.columns:
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Acquisition"] = df["Acquisition"].map(lambda x: f"{x:,.4f}" if pd.notnull(x) else "")
    if "Valeur" in df.columns:
        df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce")
        df["Valeur"] = df["Valeur"].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")

    # Alignement à droite (via CSS personnalisé)
    st.markdown("""
        <style>
            .stDataFrame td:nth-child(n+1):not(:first-child) {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.dataframe(df, use_container_width=True)
