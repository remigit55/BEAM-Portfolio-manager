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

    # Calcul de la colonne "Valeur"
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage français : 1 234,56
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    if "Quantité" in df.columns:
        df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    if "Acquisition" in df.columns:
        df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    if "Valeur" in df.columns:
        df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Sélection des colonnes dans l'ordre souhaité
    colonnes_base = {
        "Ticker": "Ticker",
        "Quantité_fmt": "Quantité",
        "Acquisition_fmt": "Acquisition",
        "Valeur_fmt": "Valeur",
        "Devise": "Devise"
    }
    colonnes_existantes = [col for col in colonnes_base if col in df.columns]

    df_affichage = df[colonnes_existantes].rename(columns={k: colonnes_base[k] for k in colonnes_existantes})

    # CSS personnalisé
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
            text-align: right;
        }
        .styled-table td:first-child, .styled-table th:first-child {
            text-align: left;
        }
    </style>
    """

    html_table = df_affichage.to_html(index=False, classes="styled-table")
    st.markdown(style + html_table, unsafe_allow_html=True)
