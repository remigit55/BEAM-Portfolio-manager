import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Conversion brute
    df["Quantité"] = pd.to_numeric(df.get("Quantité", 0), errors="coerce")
    df["Acquisition"] = pd.to_numeric(df.get("Acquisition", 0), errors="coerce")
    df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage en style français
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    df["Quantité"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Sélection des colonnes à afficher
    colonnes = [col for col in ["Tickers", "Devise", "Quantité", "Acquisition", "Valeur"] if col in df.columns]

    # Affichage
    st.dataframe(df[colonnes], use_container_width=True)

    # Hack CSS pour forcer alignement à droite
    st.markdown("""
        <style>
        .st-emotion-cache-1xarl3l td {
            text-align: right !important;
        }
        .st-emotion-cache-1xarl3l th {
            text-align: right !important;
        }
        </style>
    """, unsafe_allow_html=True)
