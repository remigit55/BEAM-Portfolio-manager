# taux_change.py
import streamlit as st
import pandas as pd
import yfinance as yf
import time
import datetime

def afficher_taux_change():
    st.header("Taux de change (actualisation automatique toutes les 30 secondes)")

    devise_cible = st.session_state.get("devise_cible", "EUR")
    devises_sources = ["USD", "CAD", "JPY"]

    # Mapping vers les tickers Yahoo correspondants
    tickers_map = {
        ("USD", "EUR"): "EURUSD=X",
        ("CAD", "EUR"): "EURCAD=X",
        ("JPY", "EUR"): "EURJPY=X",
        ("EUR", "USD"): "USDEUR=X",
        ("CAD", "USD"): "USDCAD=X",
        ("JPY", "USD"): "USDJPY=X",
        # Ajoute plus de combinaisons ici si besoin
    }

    fx_rates = {}
    for src in devises_sources:
        if src == devise_cible:
            fx_rates[src] = 1.0
        else:
            key = (devise_cible, src)
            inv = False
            if key in tickers_map:
                ticker = tickers_map[key]
            else:
                key = (src, devise_cible)
                ticker = tickers_map.get(key)
                inv = True

            if ticker:
                try:
                    data = yf.download(ticker, period="1d", interval="1m")
                    last = data["Close"].dropna().iloc[-1]
                    fx_rates[src] = 1 / last if inv else last
                except Exception:
                    fx_rates[src] = None
            else:
                fx_rates[src] = None

    # Enregistrement dans la session
    st.session_state.fx_rates = fx_rates

    # Affichage
    fx_df = pd.DataFrame([
        {"De": dev, "Vers": devise_cible, "Taux": round(taux, 6) if taux else "Erreur"}
        for dev, taux in fx_rates.items()
    ])

    st.markdown(f"Taux au **{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")
    st.dataframe(fx_df, use_container_width=True)

    # Rafraîchissement automatique (30s)
    st.experimental_rerun() if st.button("⟳ Rafraîchir manuellement") else time.sleep(30)
    st.experimental_rerun()
