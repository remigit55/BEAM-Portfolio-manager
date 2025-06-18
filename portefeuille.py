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
                df[col].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul Valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage FR
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0) if pd.notnull(x) else "")
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4) if pd.notnull(x) else "")
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2) if pd.notnull(x) else "")

    # Colonnes à afficher
    colonnes = ["Tickers", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", "Devise"]
    df_affichage = df[colonnes].rename(columns={
        "Tickers": "Ticker",
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur"
    })

    # Génération du tableau HTML avec CSS
    style = """
    <style>
        .styled-table {
            border-collapse: collapse;
            width: 100%;
            font-size: 14px;
        }
        .styled-table th, .styled-table td {
            border: 1px solid #ccc;
            padding: 6px 10px;
        }
        .styled-table th {
            background-color: #f2f2f2;
            text-align: right;
        }
        .styled-table td {
            text-align: right;
        }
        .styled-table td:first-child, .styled-table th:first-child {
            text-align: left;
        }
    </style>
    """

    html_table = df_affichage.to_html(index=False, classes="styled-table")
    st.markdown(style + html_table, unsafe_allow_html=True)
