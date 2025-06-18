rimport streamlit as st
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
    colonnes = ["Ticker", "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", "Devise"]
    noms = ["Ticker", "Quantité", "Acquisition", "Valeur", "Devise"]

    # Générer HTML manuellement
    html = """
    <style>
        .portfolio-table {
            border-collapse: collapse;
            width: 100%;
            font-family: sans-serif;
            font-size: 14px;
        }
        .portfolio-table th {
            background-color: #f4f4f4;
            padding: 8px;
            text-align: center;
            border-bottom: 2px solid #ccc;
        }
        .portfolio-table td {
            padding: 6px 10px;
            border-bottom: 1px solid #ddd;
            text-align: right;
        }
        .portfolio-table td:first-child,
        .portfolio-table th:first-child {
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

    html += "</tbody></table>"

    st.markdown(html, unsafe_allow_html=True)
