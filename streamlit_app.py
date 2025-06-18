# streamlit_app.py
import streamlit as st
import pandas as pd
import datetime
import requests
from forex_python.converter import CurrencyRates

# Configuration de la page (à mettre en tout début)
st.set_page_config(page_title="BEAM Portfolio Manager", layout="wide")

# Thème personnalisé
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
        .stDataFrame td, .stDataFrame th {{
            text-align: right !important;
        }}
        .st-emotion-cache-18ni7ap {{
            background-color: {ACCENT_COLOR};
            padding: 10px;
            border-radius: 0 0 10px 10px;
            margin-bottom: 25px;
        }}
        .st-emotion-cache-1v0mbdj, .st-emotion-cache-1avcm0n {{
            display: none;
        }}
    </style>
""", unsafe_allow_html=True)

# Titre principal
st.title("BEAM Portfolio Manager")

# Initialisation des variables session
if "df" not in st.session_state:
    st.session_state.df = None
if "fx_rates" not in st.session_state:
    st.session_state.fx_rates = {}
if "devise_cible" not in st.session_state:
    st.session_state.devise_cible = "EUR"
if "ticker_names_cache" not in st.session_state:
    st.session_state.ticker_names_cache = {}

# Onglets horizontaux
onglets = st.tabs([
    "Portefeuille", 
    "Performance", 
    "OD Comptables", 
    "Transactions", 
    "Taux de change", 
    "Paramètres"
])

# Onglet : Portefeuille
with onglets[0]:
    st.subheader("📊 Portefeuille")

    if st.session_state.df is not None:
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

        # Calculs
        df["Valeur"] = pd.to_numeric(df["Quantité"], errors="coerce") * pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
        df["Taux FX Num"] = pd.to_numeric(df["Taux FX"], errors="coerce").fillna(0.0)
        df["Valeur"] = pd.to_numeric(df["Valeur"], errors="coerce").fillna(0.0)
        df["Valeur (devise cible)"] = df["Valeur"].astype(float) * df["Taux FX Num"].astype(float)

        # Formatage
        df["Acquisition"] = pd.to_numeric(df["Acquisition"], errors="coerce")
        df["Acquisition"] = df["Acquisition"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Taux FX"] = df["Taux FX Num"].map(lambda x: f"{x:.4f}" if pd.notnull(x) else "")
        df["Valeur"] = df["Valeur"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")
        df["Valeur (devise cible)"] = df["Valeur (devise cible)"].map(lambda x: f"{x:.2f}" if pd.notnull(x) else "")

        # Ajout du nom des sociétés depuis Yahoo Finance
        def get_name_cached(ticker):
            if ticker in st.session_state.ticker_names_cache:
                return st.session_state.ticker_names_cache[ticker]
            try:
                response = requests.get(f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}")
                if response.ok:
                    name = response.json()['quoteResponse']['result'][0].get('shortName', 'Non trouvé')
                else:
                    name = "Erreur requête"
            except:
                name = "Erreur nom"
            st.session_state.ticker_names_cache[ticker] = name
            return name

        if "Tickers" in df.columns:
            noms = df["Tickers"].apply(get_name_cached)
            index_ticker = df.columns.get_loc("Tickers")
            df.insert(index_ticker + 1, "Nom", noms)

        st.dataframe(df, use_container_width=True)
        st.session_state.fx_rates = fx_rates_utilisés
    else:
        st.info("Aucun portefeuille chargé. Veuillez importer les données dans l’onglet Paramètres.")

# Onglet : Performance
with onglets[1]:
    st.subheader("📈 Performance")
    if "performance" in st.session_state:
        perf = st.session_state.performance
        st.line_chart(perf.set_index(perf.columns[0]))
    else:
        st.info("Aucune donnée de performance disponible.")

# Onglet : OD Comptables
with onglets[2]:
    st.subheader("📋 OD Comptables")
    if "od" in st.session_state:
        st.dataframe(st.session_state.od, use_container_width=True)
    else:
        st.info("Aucune OD comptable enregistrée.")

# Onglet : Transactions
with onglets[3]:
    st.subheader("🤝 Transactions M&A")
    if "ma" in st.session_state:
        st.dataframe(st.session_state.ma, use_container_width=True)
    else:
        st.info("Aucune transaction enregistrée.")

# Onglet : Taux de change
with onglets[4]:
    st.subheader("💱 Taux de change")
    if st.session_state.fx_rates:
        st.markdown(f"Taux appliqués pour conversion en {st.session_state.devise_cible} au {datetime.date.today()}")
        st.dataframe(pd.DataFrame(list(st.session_state.fx_rates.items()), columns=["Conversion", "Taux"]))
    else:
        st.info("Aucun taux de change utilisé pour l’instant.")

# Onglet : Paramètres
with onglets[5]:
    st.subheader("⚙️ Paramètres")

    st.session_state.devise_cible = st.selectbox(
        "Devise de référence pour consolidation",
        options=["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    csv_url = st.text_input("Lien vers le fichier CSV (Google Sheets)")
    if csv_url:
        try:
            st.session_state.df = pd.read_csv(csv_url)
            st.success("Données importées depuis le lien CSV.")
        except Exception as e:
            st.error(f"Erreur d'import : {e}")
