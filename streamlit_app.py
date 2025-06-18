import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import datetime
import requests

st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Définir les couleurs de thème
PRIMARY_COLOR = "#363636"
SECONDARY_COLOR = "#E8E8E8"
ACCENT_COLOR = "#A49B6D"

st.markdown(f"""
    <style>
        body {{
            background-color: {SECONDARY_COLOR};
            color: {PRIMARY_COLOR};
        }}
        .stApp {{
            font-family: 'Arial', sans-serif;
        }}
        .css-1d391kg, .css-ffhzg2 {{
            background-color: {SECONDARY_COLOR} !important;
            color: {PRIMARY_COLOR} !important;
        }}
        .stDataFrame thead tr th {{
            background-color: {ACCENT_COLOR};
            color: white;
        }}
        .stDataFrame tbody tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .stDataFrame td {{
            text-align: right !important;
        }}
    </style>
""", unsafe_allow_html=True)

st.title("BEAM Portfolio Manager")

if "df" not in st.session_state:
    st.session_state.df = None
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"

# Onglets de navigation
tabs = st.tabs(["Portefeuille", "Performance", "OD Comptables", "Transactions M&A", "Taux de change", "Paramètres"])

# Onglet Portefeuille
with tabs[0]:
    if st.session_state.df is not None:
        st.subheader("Portefeuille consolidé")

        df = st.session_state.df.copy()
        cr = CurrencyRates()
        fx_rates_utilisés = {}
        devise_cible = st.session_state.devise_cible

        def get_fx_rate(devise_origine, devise_cible):
            if devise_origine == devise_cible:
                return 1.0
            try:
                rate = cr.get_rate(devise_origine, devise_cible)
                fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = rate
                return rate
            except:
                fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = "Erreur"
                return None

        if "Valeur" not in df.columns:
            df["Valeur"] = pd.to_numeric(df["Quantité"], errors="coerce") * pd.to_numeric(df["Acquisition"], errors="coerce")

        df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
        df["Taux FX Num"] = pd.to_numeric(df["Taux FX"], errors="coerce").fillna(0.0)
        df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce").fillna(0.0)
        df["Valeur (devise cible)"] = df["Valeur"].astype(float) * df["Taux FX Num"].astype(float)

        # Format des colonnes
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Acquisition"] = df["Acquisition"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Taux FX"] = df["Taux FX Num"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Valeur"] = df["Valeur"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
        df["Valeur (devise cible)"] = df["Valeur (devise cible)"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

        # Ajoute le nom de la participation (duplique la colonne Actions si elle existe)
        if "Actions" in df.columns:
            df.insert(1, "Nom", df["Actions"])

        # Supprimer la première colonne (index ou identifiant inutile)
        df = df.iloc[:, 1:]

        st.dataframe(df, use_container_width=True)

        st.session_state.fx_rates = fx_rates_utilisés

# Onglet Performance
with tabs[1]:
    if "performance" in st.session_state:
        perf = st.session_state.performance
        st.subheader("Performance historique")
        st.line_chart(perf.set_index(perf.columns[0]))

# Onglet OD Comptables
with tabs[2]:
    if "od" in st.session_state:
        st.subheader("OD Comptables")
        st.dataframe(st.session_state.od, use_container_width=True)

# Onglet Transactions M&A
with tabs[3]:
    if "ma" in st.session_state:
        st.subheader("Transactions minières")
        st.dataframe(st.session_state.ma, use_container_width=True)

# Onglet Taux de change
with tabs[4]:
    if st.session_state.fx_rates:
        st.subheader("Taux de change utilisés")
        st.markdown(f"Taux appliqués pour conversion en {st.session_state.devise_cible} au {datetime.date.today()}")
        st.dataframe(pd.DataFrame(list(st.session_state.fx_rates.items()), columns=["Conversion", "Taux"]))
    elif "fx" in st.session_state:
        st.subheader("Taux de change")
        st.dataframe(st.session_state.fx, use_container_width=True)

# Onglet Paramètres
with tabs[5]:
    st.subheader("Paramètres globaux")
    st.session_state.devise_cible = st.selectbox("Devise de référence pour consolidation", options=["USD", "EUR", "CAD", "CHF"], index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible))

    csv_url = st.text_input("Lien vers le CSV Google Sheets (onglet Portefeuille)")
    if csv_url:
        try:
            st.session_state.df = pd.read_csv(csv_url)
            st.success("Données importées depuis le lien CSV")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
