import streamlit as st
import pandas as pd
import time
import datetime
import requests

DEVISES = ["USD", "CAD", "CHF", "JPY", "GBP", "AUD"]
DEVISE_CIBLE = st.session_state.get("devise_cible", "EUR")

@st.cache_data(ttl=30)
def get_fx_yahoo(base, quote):
    try:
        symbol = f"{base}{quote}=X"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        json_data = r.json()
        meta = json_data["chart"]["result"][0]["meta"]
        return meta.get("regularMarketPrice", None)
    except Exception:
        return None

def afficher_taux_change():
    st.markdown(f"Taux de change pour conversion en **{DEVISE_CIBLE}** (auto-refresh toutes les 30s) — *{datetime.datetime.now().strftime('%H:%M:%S')}*")

    fx_rates = []
    for dev in DEVISES:
        if dev == DEVISE_CIBLE:
            continue
        taux = get_fx_yahoo(dev, DEVISE_CIBLE)
        if taux:
            fx_rates.append((f"{dev}/{DEVISE_CIBLE}", taux))

    if fx_rates:
        st.session_state.fx_rates = {pair: rate for pair, rate in fx_rates}
        df = pd.DataFrame(fx_rates, columns=["Conversion", "Taux"])
        st.dataframe(df, use_container_width=True)
    else:
        st.error("Impossible de récupérer les taux. Vérifiez votre connexion ou réessayez plus tard.")
