# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
import requests
import json
import streamlit as st
import builtins # Importe le module builtins pour accéder à la fonction str() originale

@st.cache_data(ttl=3600) # Cache les données historiques des actions pour 1 heure
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance (yfinance library).
    Utilise builtins.str pour contourner l'écrasement potentiel de str().
    """
    try:
        # Utilise builtins.str pour s'assurer que Ticker est bien une chaîne
        if not builtins.isinstance(Ticker, builtins.str):
            st.warning(f"Ticker mal formé : {Ticker} (type: {builtins.str(type(Ticker).__name__)})")
            return pd.Series(dtype='float64')
        
        # Vérifie si yf.download est appelable en utilisant builtins.callable
        if not builtins.callable(yf.download):
            st.error("Erreur critique : yf.download n'est pas appelable. Conflit possible dans les imports.")
            return pd.Series(dtype='float64')

        # Appel à yf.download
        data = yf.download(Ticker, start=start_date, end=end_date, progress=False)
        
        # Vérification et extraction de la colonne 'Close'
        if not data.empty:
            if builtins.isinstance(data.columns, pd.MultiIndex):
                close_data = data[('Close', Ticker)] if ('Close', Ticker) in data.columns else None
                if close_data is not None:
                    close_data = close_data.rename(Ticker)
                    return close_data
                else:
                    st.warning(f"Colonne ('Close', '{Ticker}') absente. Colonnes disponibles : {builtins.str(data.columns.tolist())}")
                    return pd.Series(dtype='float64')
            else:
                if 'Close' in data.columns:
                    close_data = data['Close'].rename(Ticker)
                    return close_data
                else:
                    st.warning(f"Colonne 'Close' absente pour {Ticker}. Colonnes disponibles : {builtins.str(data.columns.tolist())}")
                    return pd.Series(dtype='float64')
        else:
            st.warning(f"Aucune donnée valide pour {Ticker} : DataFrame vide.")
            return pd.Series(dtype='float64')

    except Exception as e:
        error_msg = f"Erreur lors de la récupération pour {Ticker} : {builtins.str(type(e).__name__)} - {builtins.str(e)}"
        st.error(error_msg)
        return pd.Series(dtype='float64')

# Désactivé pour le moment, retourne une série de 1.0 pour ignorer la conversion de devise.
# Vous pouvez le réintégrer plus tard si vous avez besoin de la parité des changes.
def fetch_historical_fx_rates(base_currency, target_currency, start_date, end_date):
    """
    Récupère l'historique des taux de change via exchangerate.host pour une période donnée.
    Pour le moment, retourne une série de 1.0 pour désactiver la conversion de devise.
    """
    business_days = pd.bdate_range(start_date, end_date)
    return pd.Series(1.0, index=business_days, name=f"{base_currency}/{target_currency}")


@st.cache_data(ttl=3600) # Cache les données historiques globales pour 1 heure
def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère l'ensemble des données historiques nécessaires :
    - Cours des actions via Yahoo Finance
    - Taux de change (désactivé pour le moment, retourne 1.0)
    """
    historical_prices = {}
    business_days = pd.bdate_range(start_date, end_date)

    for ticker in tickers:
        prices = fetch_stock_history(ticker, start_date, end_date)
        if not prices.empty:
            # Re-indexer et remplir les jours manquants
            prices = prices.reindex(business_days).ffill().bfill()
            historical_prices[ticker] = prices

    # Les taux de change sont simplifiés pour le moment
    historical_fx = {}
    unique_currencies = set(currencies)
    unique_currencies.add(target_currency)

    for currency in unique_currencies:
        # Même si la fonction fetch_historical_fx_rates est simplifiée, on l'appelle pour avoir une structure cohérente
        fx_series = fetch_historical_fx_rates(currency, target_currency, start_date, end_date)
        if fx_series is not None and not fx_series.empty:
            fx_series = fx_series.reindex(business_days).ffill().bfill()
            historical_fx[f"{currency}/{target_currency}"] = fx_series
            
    return historical_prices, historical_fx
