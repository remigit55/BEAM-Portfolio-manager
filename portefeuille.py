import streamlit as st
import pandas as pd

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Nettoyage et conversion
    df["Quantité"] = pd.to_numeric(df.get("Quantité", 0), errors="coerce")
    df["Acquisition"] = pd.to_numeric(df.get("Acquisition", 0), errors="coerce")
    df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Formatage français
    def format_fr(x, dec=2):
        if pd.isnull(x):
            return ""
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", " ")

    df["Quantité_fmt"] = df["Quantité"].map(lambda x: format_fr(x, 0))
    df["Acquisition_fmt"] = df["Acquisition"].map(lambda x: format_fr(x, 4))
    df["Valeur_fmt"] = df["Valeur"].map(lambda x: format_fr(x, 2))

    # Création du tableau HTML
    tableau = "<table><thead><tr>"
    colonnes = ["Tickers", "Devise", "Quantité", "Acquisition", "Valeur"]
    for col in colonnes:
        tableau += f"<th>{col}</th>"
    tableau += "</tr></thead><tbody>"

    for _, row in df.iterrows():
        tableau += "<tr>"
        tableau += f"<td style='text-align: left'>{row.get('Tickers', '')}</td>"
        tableau += f"<td style='text-align: right'>{row.get('Quantité_fmt', '')}</td>"
        tableau += f"<td style='text-align: right'>{row.get('Acquisition_fmt', '')}</td>"
        tableau += f"<td style='text-align: right'>{row.get('Valeur_fmt', '')}</td>"
        tableau += f"<td style='text-align: left'>{row.get('Devise', '')}</td>"
        tableau += "</tr>"

    tableau += "</tbody></table>"

    # CSS pour bordures et alignement
    st.markdown("""
        <style>
            table {
                width: 100%;
                border-collapse: collapse;
            }
            th, td {
                padding: 8px;
                border-bottom: 1px solid #ddd;
                font-family: monospace;
            }
            thead {
                background-color: #f0f0f0;
            }
        </style>
    """, unsafe_allow_html=True)

    # Affichage
    st.markdown(tableau, unsafe_allow_html=True)
