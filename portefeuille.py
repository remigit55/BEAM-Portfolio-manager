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

    # Ordre et noms d’affichage
    colonnes = ["Ticker", "shortName", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", "Devise"]
    noms = ["Ticker", "Nom", "Quantité", "Prix d'Acquisition", "Valeur", "Devise"]

    # Calcul du total
    total_valeur = df["Valeur"].sum()
    total_valeur_fmt = format_fr(total_valeur, 2)

    # Générer HTML manuellement
    html = """
    <style>
    .portfolio-table-container {
        overflow-y: auto;
        max-height: 600px;
        border-style : none;
    }
    .portfolio-table {
        border-collapse: collapse;
        width: 100%;
        min-width: 700px;
        overflow: hidden;
        border-style : none;
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
        z-index: 10;
        border-style : none;
    }
    .portfolio-table td {
        padding: 6px;
        text-align: right;
        color: black;
        font-family: "Aptos narrow", Helvetica;
        font-size: 11px;
        border-style : none;
    }
    .portfolio-table td:first-child {
        text-align: left;
    }
</style>

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

    # Ligne total uniquement sur la colonne "Valeur"
        html += f"""
        <tr style="background-color:#A49B6D; font-weight: bold;">
            <td colspan="4" style="text-align:right;">TOTAL</td>
            <td style="text-align:right;">{total_valeur_fmt}</td>
            <td></td>
        </tr>
        </tbody>
    </table>
    </div>
    """

    st.markdown(html, unsafe_allow_html=True)


    html += "</tbody></table>"

    st.markdown(html, unsafe_allow_html=True)
