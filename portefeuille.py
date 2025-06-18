import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Nettoyage des colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
                .astype(float)
            )

    # Calcul de la valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Format français
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Ordre des colonnes à afficher
    colonnes_affichage = []
    if "Tickers" in df.columns:
        df["Ticker"] = df["Tickers"]  # pour afficher avec un nom plus propre
        colonnes_affichage.append("Ticker")
    colonnes_affichage += ["Quantité_fmt", "Acquisition_fmt", "Valeur_fmt"]
    if "Devise" in df.columns:
        colonnes_affichage.append("Devise")

    # Construction du DataFrame final
    df_affichage = df[colonnes_affichage].rename(columns={
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # CSS alignement à droite
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

    st.dataframe(df_affichage, use_container_width=True)
