# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime
import requests
import json
import streamlit as st
import builtins  # Pour garantir l’accès à str natif même s’il a été écrasé ailleurs

# Cache pour les données historiques des actions (valable 1h)
@st.cache_data(ttl=3600)
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance.
    """
    try:
        if not isinstance(Ticker, builtins.str):
            st.warning(f"Ticker mal formé : {Ticker} (type: {type(Ticker)})")
            return pd.Series(dtype='float64')
        
        if not callable(yf.download):
            st.error("Erreur critique : yf.download n'est pas appelable. Conflit possible dans les imports.")
            return pd.Series(dtype='float64')

        data = yf.download(Ticker, start=start_date, end=end_date, progress=False)
        if not data.empty:
            return data['Close'].rename(Ticker)

    except Exception as e:
        if isinstance(e, TypeError) and "'str' object is not callable" in builtins.str(e):
            st.error("⚠️ Erreur critique : la fonction native `str()` a été écrasée. Vérifiez votre code (évitez `str = ...`).")
        else:
            st.warning(f"Impossible de récupérer l'historique pour {Ticker}: {builtins.str(e)}")

    return pd.Series(dtype='float64')


# Cache pour les taux de change historiques (valable 24h)
@st.cache_data(ttl=86400)
def fetch_historical_fx_rates(base_currency, target_currency, start_date, end_date):
    """
    Récupère l'historique des taux de change via exchangerate.host (base -> target).
    """
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    url = f"https://api.exchangerate.host/timeseries?start_date={start_str}&end_date={end_str}&base={base_currency}&symbols={target_currency}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        rates_series = {}
        for date_str, rates in data.get('rates', {}).items():
            if target_currency in rates:
                rates_series[date_str] = rates[target_currency]

        if rates_series:
            return pd.Series(rates_series).rename(f"{base_currency}/{target_currency}")
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur HTTP pour les taux de change {base_currency}/{target_currency} : {builtins.str(e)}")
    except json.JSONDecodeError as e:
        st.error(f"Erreur JSON pour les taux de change {base_currency}/{target_currency} : {builtins.str(e)}")
    
    return pd.Series(dtype='float64')


def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère l'ensemble des données historiques nécessaires :
    - Cours des actions via Yahoo Finance
    - Taux de change via exchangerate.host
    Retourne deux dictionnaires : historical_prices et historical_fx.
    """
    historical_prices = {}
    business_days = pd.bdate_range(start_date, end_date)

    # Récupération des prix
    for ticker in tickers:
        prices = fetch_stock_history(ticker, start_date, end_date)
        if not prices.empty:
            prices = prices.reindex(business_days).ffill().bfill()
            historical_prices[ticker] = prices

    # Récupération des taux de change
    historical_fx = {}
    unique_currencies = set(currencies)
    unique_currencies.add(target_currency)

    for currency in unique_currencies:
        if currency != target_currency:
            fx_series = fetch_historical_fx_rates(currency, target_currency, start_date, end_date)
            if fx_series is not None and not fx_series.empty:
                fx_series = fx_series.reindex(business_days).ffill().bfill()
                historical_fx[f"{currency}/{target_currency}"] = fx_series

    return historical_prices, historical_fx
