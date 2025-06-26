# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date, time # Import date and time
import requests
import json
import streamlit as st
import builtins
if not callable(str):
    str = builtins.str

# Cache pour les données historiques des actions (valable 1h)
@st.cache_data(ttl=3600)
def fetch_stock_history(ticker, start_date, end_date, currency_source, currency_target):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance (yfinance library).
    """
    try:
        if not isinstance(ticker, builtins.str):  # <-- CORRIGÉ
            st.warning(f"Ticker mal formé : {ticker} (type: {builtins.str(type(ticker))})")
            return pd.Series(dtype='float64')

        if not builtins.callable(yf.download):
            st.error("Erreur critique : yf.download n'est pas appelable. Conflit possible dans les imports.")
            return pd.Series(dtype='float64')

        data = yf.download(ticker, start=start_date, end=end_date, progress=False)  # <-- CORRIGÉ
        if not data.empty:
            return data['Close'].rename(ticker)  # <-- CORRIGÉ

    except Exception as e:
        if isinstance(e, builtins.TypeError) and "'str' object is not callable" in builtins.str(e):
            st.error("⚠️ Erreur critique : la fonction native `str()` a été écrasée. Vérifiez votre code (évitez `str = ...`).")
        else:
            st.warning(f"Impossible de récupérer l'historique pour {ticker}: {builtins.str(e)}")

    return pd.Series(dtype='float64')


# The fetch_stock_history_direct_api function was causing the TypeError
# and is not called elsewhere in the provided code. It has been removed
# to resolve the issue and simplify the code. The main fetch_stock_history
# function is robust enough.

@st.cache_data(ttl=3600)
def fetch_historical_fx_rates(base_currency, target_currency, start_date, end_date):
    """
    Récupère l'historique des taux de change via exchangerate.host pour une période donnée.
    """
    if base_currency.upper() == target_currency.upper():
        # If source and target are the same, return a Series of 1.0 for the date range
        business_days = pd.bdate_range(start_date, end_date)
        return pd.Series(1.0, index=business_days, name=f"{base_currency}/{target_currency}")

    api_url = "https://api.exchangerate.host/timeseries"
    params = {
        "base": base_currency,
        "symbols": target_currency,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d")
    }

    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data and data.get('rates'):
            fx_rates = {
                date: rates.get(target_currency)
                for date, rates in data['rates'].items()
            }
            # Convert to Pandas Series, convert index to datetime, and sort
            fx_series = pd.Series(fx_rates, name=f"{base_currency}/{target_currency}").dropna()
            fx_series.index = pd.to_datetime(fx_series.index)
            return fx_series.sort_index()
        else:
            st.warning(f"Aucune donnée de taux de change trouvée pour {base_currency}/{target_currency} sur la période spécifiée.")
            return pd.Series(dtype='float64')

    except requests.exceptions.RequestException as e:
        st.warning(f"Erreur réseau ou HTTP pour les taux de change {base_currency}/{target_currency} : {builtins.str(e)}")
    except json.JSONDecodeError as e:
        st.warning(f"Erreur JSON pour les taux de change {base_currency}/{target_currency} : {builtins.str(e)}")
    except Exception as e:
        st.error(f"Une erreur inattendue est survenue pour les taux de change {base_currency}/{target_currency} : {e}")
    
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

def fetch_stock_history_converted(ticker, start_date, end_date, currency_source="USD", currency_target="EUR"):
    """
    Récupère les cours d’un ticker et les convertit en devise cible.
    """
    df = yf.download(ticker, start=start_date, end=end_date, interval="1d", progress=False)

    if df.empty or "Close" not in df.columns:
        return pd.DataFrame()

    df = df[["Close"]].copy()
    df.index.name = "Date"

    if currency_source != currency_target:
        fx_ticker = f"{currency_source}{currency_target}=X"
        fx_data = yf.download(fx_ticker, start=start_date, end=end_date, interval="1d", progress=False)

        if not fx_data.empty and "Close" in fx_data.columns:
            fx_data = fx_data[["Close"]].rename(columns={"Close": "FX"})
            df = df.join(fx_data, how="left")
            df.dropna(inplace=True)
            df["Close"] = df["Close"] * df["FX"]
            df.drop(columns=["FX"], inplace=True)

    return df

