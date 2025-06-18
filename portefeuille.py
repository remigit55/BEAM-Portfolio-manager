import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Normaliser les colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul de la valeur
    if "Quantité" in df.columns and "Acquisition" in df.columns:
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage français
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", " ").replace(".", ",")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Ordre des colonnes
    colonnes = ["Ticker", "shortName", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", "Devise"]
    noms = ["Ticker", "Nom", "Quantité", "Prix d'Acquisition", "Valeur", "Devise"]

    total_valeur_fmt = format_fr(df["Valeur"].sum(), 2)

    # HTML avec style et tableau scrollable
    html = """
    <style>
        .table-container {
            max-height: 400px;
            overflow-y: auto;
        }
        .portfolio-table {
            border-collapse: collapse;
            width: 100%;
            border-left: 1px solid transparent;
            border-right: 1px solid transparent;
        }
        .portfolio-table th {
            background-color: #363636;
            padding: 6px;
            text-align: center;
            color: white;
            font-family: "Aptos narrow", Helvetica;
            font-size: 12px;
            position: sticky;
            top: 0;
            z-index: 1;
            border-bottom: 1px solid transparent;
            border-left: 1px solid transparent;
            border-right: 1px solid transparent;
        }
        .portfolio-table td {
            padding: 6px;
            text-align: right;
            border-bottom: 1px solid transparent;
            border-left: 1px solid transparent;
            border-right: 1px solid transparent;
            color: black;
            font-family: "Aptos narrow", Helvetica;
            font-size: 11px;
        }
        .portfolio-table td:first-child {
            text-align: left;
        }
        .total-row {
            background-color: #A49B6D;
            font-weight: bold;
            color: white;
            border-top: 1px solid transparent;
            border-bottom: 1px solid transparent;
            border-left: 1px solid transparent;
            border-right: 1px solid transparent;
        }
    </style>
    <div class="table-container">
    <table class="portfolio-table">
        <thead>
            <tr>""" + "".join(f"<th>{name}</th>" for name in noms) + """</tr>
        </thead>
        <tbody>
    """

    for _, row in df.iterrows():
        html += "<tr>"
        for col in colonnes:
            val = row.get(col, "")
            html += f"<td>{val}</td>"
        html += "</tr>"

    html += f"""
        <tr class="total-row">
            <td colspan="4" style="text-align:right;">TOTAL</td>
            <td>{total_valeur_fmt}</td>
            <td></td>
        </tr>
        </tbody>
    </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)
