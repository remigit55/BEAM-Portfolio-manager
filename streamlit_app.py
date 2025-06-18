import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
            df["Valeur"] = df["Quantité"] * df["Acquisition"]

        df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
        df["Valeur (devise cible)"] = df["Valeur"] * df["Taux FX"]

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

    google_sheet_url = st.text_input("Lien vers le Google Sheets du portefeuille")
    if google_sheet_url:
        try:
            scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
            client = gspread.authorize(creds)
            spreadsheet_id = google_sheet_url.split("/d/")[1].split("/")[0]
            spreadsheet = client.open_by_key(spreadsheet_id)

            st.session_state.df = pd.DataFrame(spreadsheet.worksheet("Portefeuille").get_all_records())
            st.session_state.performance = pd.DataFrame(spreadsheet.worksheet("Performance").get_all_records())
            st.session_state.od = pd.DataFrame(spreadsheet.worksheet("OD_Comptables").get_all_records())
            st.session_state.ma = pd.DataFrame(spreadsheet.worksheet("Transactions_M&A").get_all_records())
            st.session_state.fx = pd.DataFrame(spreadsheet.worksheet("Taux_FX").get_all_records())

            st.success("Données importées depuis Google Sheets")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
