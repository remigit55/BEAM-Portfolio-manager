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
        df["Quantité"] = df["Quantité"].map(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
    if "Acquisition" in df.columns:
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: f"{x:,.4f}" if pd.notnull(x) else "")
    if "Valeur" in df.columns:
        df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce")
        df["Valeur_fmt"] = df["Valeur"].map(lambda x: f"{x:,.2f}" if pd.notnull(x) else "")

    # Construction du tableau à afficher
    colonnes_affichage = []
    for col in df.columns:
        if col == "Acquisition_fmt":
            colonnes_affichage.append("Acquisition_fmt")
        elif col == "Valeur_fmt":
            colonnes_affichage.append("Valeur_fmt")
        elif col in ["Acquisition", "Valeur"]:
            continue
        else:
            colonnes_affichage.append(col)

    df_affichage = df[colonnes_affichage].rename(columns={
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Alignement à droite (via CSS personnalisé)
    st.markdown("""
        <style>
            .stDataFrame td {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.dataframe(df_affichage, use_container_width=True)

