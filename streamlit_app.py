import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import datetime
import requests

st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

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
            text-align: right !important;
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
if "ticker_data_cache" not in st.session_state:
    st.session_state.ticker_data_cache = {}

# Onglets
tabs = st.tabs(["Portefeuille", "Performance", "OD Comptables", "Transactions", "Taux de change", "Paramètres"])

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

        df["Valeur"] = pd.to_numeric(df["Quantité"], errors="coerce") * pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
        df["Taux FX Num"] = pd.to_numeric(df["Taux FX"], errors="coerce").fillna(0.0)
        df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce").fillna(0.0)
        df["Valeur (devise cible)"] = df["Valeur"].astype(float) * df["Taux FX Num"].astype(float)

        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Acquisition"] = df["Acquisition"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Taux FX"] = df["Taux FX Num"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Valeur"] = df["Valeur"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
        df["Valeur (devise cible)"] = df["Valeur (devise cible)"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

        # Récupération des infos Yahoo Finance enrichies
        def get_yahoo_data(ticker):
            if ticker in st.session_state.ticker_data_cache:
                return st.session_state.ticker_data_cache[ticker]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers)
                if r.ok:
                    data = r.json()
                    meta = data["chart"]["result"][0]["meta"]
                    result = {
                        "Nom": meta.get("symbol", "Non trouvé"),
                        "Cours": meta.get("regularMarketPrice", ""),
                        "Devise Confirmée": meta.get("currency", ""),
                        "Plus Haut 52s": meta.get("fiftyTwoWeekHigh", "")
                    }
                else:
                    result = {"Nom": "Erreur", "Cours": "", "Devise Confirmée": "", "Plus Haut 52s": ""}
            except:
                result = {"Nom": "Erreur", "Cours": "", "Devise Confirmée": "", "Plus Haut 52s": ""}
            st.session_state.ticker_data_cache[ticker] = result
            return result

        if "Tickers" in df.columns:
            info = df["Tickers"].apply(get_yahoo_data).apply(pd.Series)
            idx = df.columns.get_loc("Tickers") + 1
            for col in ["Nom", "Cours", "Devise Confirmée", "Plus Haut 52s"]:
                df.insert(idx, col, info[col])
                idx += 1

        st.dataframe(df, use_container_width=True)
        st.session_state.fx_rates = fx_rates_utilisés

with tabs[1]:
    if "performance" in st.session_state:
        st.subheader("Performance historique")
        perf = st.session_state.performance
        st.line_chart(perf.set_index(perf.columns[0]))

with tabs[2]:
    if "od" in st.session_state:
        st.subheader("OD Comptables")
        st.dataframe(st.session_state.od, use_container_width=True)

with tabs[3]:
    if "ma" in st.session_state:
        st.subheader("Transactions minières")
        st.dataframe(st.session_state.ma, use_container_width=True)

with tabs[4]:
    if st.session_state.fx_rates:
        st.subheader("Taux de change utilisés")
        st.markdown(f"Taux appliqués pour conversion en {st.session_state.devise_cible} au {datetime.date.today()}")
        st.dataframe(pd.DataFrame(list(st.session_state.fx_rates.items()), columns=["Conversion", "Taux"]))
    elif "fx" in st.session_state:
        st.subheader("Taux de change")
        st.dataframe(st.session_state.fx, use_container_width=True)

with tabs[5]:
    st.subheader("Paramètres globaux")
    st.session_state.devise_cible = st.selectbox("Devise de référence pour consolidation", ["USD", "EUR", "CAD", "CHF"], index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible))
    csv_url = st.text_input("Lien vers le CSV Google Sheets (onglet Portefeuille)")
    if csv_url:
        try:
            st.session_state.df = pd.read_csv(csv_url)
            st.success("Données importées depuis le lien CSV")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
