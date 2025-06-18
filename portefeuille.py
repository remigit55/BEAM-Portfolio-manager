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

    # Formattage style français : 1 234,56
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")

    if "Quantité" in df.columns:
        df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    if "Acquisition" in df.columns:
        df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    if "Valeur" in df.columns:
        df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Préparer les colonnes d’affichage
    colonnes_affichage = []
    for col in df.columns:
        if col == "Acquisition_fmt":
            colonnes_affichage.append("Acquisition_fmt")
        elif col == "Valeur_fmt":
            colonnes_affichage.append("Valeur_fmt")
        elif col in ["Acquisition", "Valeur"]:
            continue
        elif col == "Quantité_fmt":
            colonnes_affichage.append("Quantité_fmt")
        elif col == "Quantité":
            continue
        else:
            colonnes_affichage.append(col)

    # Renommer colonnes formatées pour affichage
    df_affichage = df[colonnes_affichage].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Alignement CSS à droite
    st.markdown("""
        <style>
            .stDataFrame td {
                text-align: right !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # Affichage
    st.dataframe(df_affichage, use_container_width=True)
