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

    # Conversion des colonnes numériques
    if "Quantité" in df.columns:
        df["Quantité"] = pd.to_numeric(df["Quantité"], errors="coerce")
    if "Acquisition" in df.columns:
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")

    # Calcul de la valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Format français : 1 234,56
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")

    # Colonnes formatées pour affichage
    if "Quantité" in df.columns:
        df["Quantité affichée"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    if "Acquisition" in df.columns:
        df["Acquisition affichée"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    if "Valeur" in df.columns:
        df["Valeur affichée"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Ordre des colonnes à afficher (les colonnes brutes peuvent rester masquées si besoin)
    colonnes_affichage = []
    for col in df.columns:
        if col in ["Quantité", "Acquisition", "Valeur"]:
            continue
        colonnes_affichage.append(col)
    for col in ["Quantité affichée", "Acquisition affichée", "Valeur affichée"]:
        if col in df.columns:
            colonnes_affichage.append(col)

    # Renommer proprement
    df_affichage = df[colonnes_affichage].rename(columns={
        "Quantité affichée": "Quantité",
        "Acquisition affichée": "Acquisition",
        "Valeur affichée": "Valeur"
    })

    # CSS pour aligner à droite
    st.markdown("""
        <style>
            .stDataFrame td {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Affichage
    st.dataframe(df_affichage, use_container_width=True)
