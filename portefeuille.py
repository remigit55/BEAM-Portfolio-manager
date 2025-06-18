import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Conversion des colonnes numériques
    df["Quantité"] = pd.to_numeric(df.get("Quantité", 0), errors="coerce")
    df["Acquisition"] = pd.to_numeric(df.get("Acquisition", 0), errors="coerce")
    df["Valeur"] = df["Quantité"] * df["Acquisition"]

    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Sélection et renommage des colonnes pour affichage
    df_affichage = df[["Tickers", "Devise", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt"]].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Affichage HTML avec alignement à droite
    st.markdown("""
    <style>
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 8px 12px;
            text-align: right;
            border-bottom: 1px solid #ddd;
        }
        th:first-child, td:first-child {
            text-align: left;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(df_affichage.to_html(index=False, escape=False), unsafe_allow_html=True)
