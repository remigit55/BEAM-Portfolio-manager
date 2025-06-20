# historical_data_fetcher.py
import yfinance as yf # This is correct
import pandas as pd
from datetime import datetime, timedelta
import requests
import json
import streamlit as st

# Cache pour les données historiques (pour éviter des requêtes répétées à Yahoo Finance ou aux API de taux de change)
@st.cache_data(ttl=3600) # Cache for 1 hour
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné.
    """
    try:
        # This is the critical line where yf.download is called
        data = yf.download(Ticker, start=start_date, end=end_date, progress=False)
        if not data.empty:
            # Using 'Close' as discussed, which is correct
            return data['Close'].rename(Ticker)
    except Exception as e:
        # The error message comes from here, but the root cause is the `str` object not callable
        st.warning(f"Impossible de récupérer l'historique pour {Ticker}: {e}")
    return pd.Series(dtype='float64')

    if data.empty:
        st.error(f"Aucune donnée historique trouvée pour {ticker} entre {start_date.date()} et {end_date.date()}.")
    return


@st.cache_data(ttl=3600*24) # Cache for 24 hours (FX rates don't change as frequently intraday)
def fetch_historical_fx_rates(base_currency, target_currency, start_date, end_date):
    """
    Récupère l'historique des taux de change de EUR vers target_currency
    (ou base_currency vers target_currency si l'API le permet).
    Utilise l'API exchangerate.host qui est gratuite et simple.
    """
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")

    url = f"https://api.exchangerate.host/timeseries?start_date={start_str}&end_date={end_str}&base={base_currency}&symbols={target_currency}"
    
    try:
        response = requests.get(url)
        response.raise_for_status() # Lève une exception pour les codes d'état HTTP d'erreur
        data = response.json()
        
        rates_series = {}
        for date_str, rates in data.get('rates', {}).items():
            if target_currency in rates:
                rates_series[date_str] = rates[target_currency]
        
        if rates_series:
            return pd.Series(rates_series).rename(f"{base_currency}/{target_currency}")
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur lors de la récupération des taux de change historiques pour {base_currency}/{target_currency}: {e}")
    except json.JSONDecodeError as e:
        st.error(f"Erreur de décodage JSON pour les taux de change historiques: {e}")
    return pd.Series(dtype='float64')

def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère toutes les données historiques nécessaires (cours boursiers et taux de change).
    Retourne un dictionnaire de DataFrames/Series.
    """
    historical_prices = {}
    for ticker in tickers:
        prices = fetch_stock_history(ticker, start_date, end_date) # Calling fetch_stock_history
        if not prices.empty:
            historical_prices[ticker] = prices.reindex(pd.bdate_range(start_date, end_date)).ffill().bfill() # Fill missing dates

    historical_fx = {}
    unique_currencies = set(currencies)
    unique_currencies.add(target_currency)
    
    for currency in unique_currencies:
        if currency != target_currency:
            rate_series = fetch_historical_fx_rates(currency, target_currency, start_date, end_date) # Calling fetch_historical_fx_rates
            if not rate_series.empty:
                historical_fx[f"{currency}/{target_currency}"] = rate_series.reindex(pd.bdate_range(start_date, end_date)).ffill().bfill()

    return historical_prices, historical_fx
