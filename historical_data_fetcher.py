# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, time # Import time as well
import requests
import json
import streamlit as st
import builtins # Explicitly import builtins to refer to original str()

# Cache pour les données historiques des actions (valable 1h)
@st.cache_data(ttl=3600)
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance (yfinance library).
    """
    try:
        if not isinstance(Ticker, builtins.str): # Use builtins.str
            st.warning(f"Ticker mal formé : {Ticker} (type: {builtins.str(type(Ticker))})")
            return pd.Series(dtype='float64')
        
        # This check for callable(yf.download) is good for debugging, keep it.
        if not builtins.callable(yf.download): # Use builtins.callable
            st.error("Erreur critique : yf.download n'est pas appelable. Conflit possible dans les imports.")
            return pd.Series(dtype='float64')

        data = yf.download(Ticker, start=start_date, end=end_date, progress=False)
        if not data.empty:
            return data['Close'].rename(Ticker)

    except Exception as e:
        # We already have builtins imported above.
        if isinstance(e, builtins.TypeError) and "'str' object is not callable" in builtins.str(e):
            st.error("⚠️ Erreur critique : la fonction native `str()` a été écrasée. Vérifiez votre code (évitez `str = ...`).")
        else:
            st.warning(f"Impossible de récupérer l'historique pour {Ticker}: {builtins.str(e)}")

    return pd.Series(dtype='float64')


@st.cache_data(ttl=3600)
def fetch_stock_history_direct_api(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné
    en appelant directement l'API de Yahoo Finance.
    """
    if not isinstance(Ticker, builtins.str): # Use builtins.str
        st.warning(f"Ticker mal formé pour l'API directe : {Ticker} (type: {builtins.str(type(Ticker))})")
        return pd.Series(dtype='float64')

    base_url = "https://query1.finance.yahoo.com/v8/finance/chart/"
    
    # Convert date objects to datetime objects for timestamp() method
    # It's good practice to ensure they are datetime objects, as .timestamp() is a datetime method.
    if isinstance(start_date, datetime.date) and not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, time.min) # Use time.min for start of day
    if isinstance(end_date, datetime.date) and not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, time.max) # Use time.max for end of day

    # Yahoo Finance API expects Unix timestamps (seconds since epoch)
    start_timestamp = int(start_date.timestamp())
    # Add one day to end_date to ensure the last day's data is included,
    # as Yahoo API's 'end' parameter is exclusive for daily data.
    end_timestamp = int((end_date + timedelta(days=1)).timestamp())

    # 'interval' can be '1d', '1wk', '1mo', etc. 'range' for the period.
    # We'll use '1d' for daily data.
    params = {
        "interval": "1d",
        "period1": start_timestamp,
        "period2": end_timestamp
    }

    url = f"{base_url}{Ticker}"

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        data = response.json()

        # Navigate the JSON structure to get relevant data
        chart_data = data.get("chart", {}).get("result")
        if not chart_data:
            st.warning(f"Aucune donnée 'chart' ou 'result' trouvée pour {Ticker} via l'API directe.")
            return pd.Series(dtype='float64')

        # Assuming 'result' is a list and we take the first element
        main_data = chart_data[0]
        timestamps = main_data.get("timestamp", [])
        closes = main_data.get("indicators", {}).get("adjclose", [])[0].get("adjclose", []) # Adjusted close

        if not timestamps or not closes:
            st.warning(f"Aucune donnée de timestamp ou de clôture ajustée trouvée pour {Ticker} via l'API directe.")
            return pd.Series(dtype='float64')

        # Create a Pandas Series
        dates = [datetime.fromtimestamp(ts).strftime("%Y-%m-%d") for ts in timestamps]
        prices = pd.Series(closes, index=pd.to_datetime(dates), name=Ticker)
        
        # Filter dates to be strictly within the requested start_date and end_date
        # The Yahoo API might return data slightly outside the range, so we refine it.
        prices = prices[(prices.index.date >= start_date.date()) & (prices.index.date <= end_date.date())]


        if prices.empty:
            st.warning(f"Aucune donnée valide récupérée pour {Ticker} sur la période spécifiée via l'API directe après filtrage.")
            return pd.Series(dtype='float64')

        return prices.sort_index() # Ensure dates are sorted

    except requests.exceptions.RequestException as e:
        st.warning(f"Erreur réseau ou HTTP lors de la récupération pour {Ticker} via l'API directe : {builtins.str(e)}")
    except json.JSONDecodeError as e:
        st.warning(f"Erreur de décodage JSON pour {Ticker} via l'API directe : {builtins.str(e)}")
    except Exception as e:
        # Use builtins.str here too, just in case other errors occur
        st.error(f"Une erreur inattendue s'est produite lors de la récupération pour {Ticker} via l'API directe : {builtins.str(e)}")

    return pd.Series(dtype='float64')


def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère l'ensemble des données historiques nécessaires :
    - Cours des actions via Yahoo Finance (using direct API for stocks)
    - Taux de change via exchangerate.host
    Retourne deux dictionnaires : historical_prices et historical_fx.
    """
    historical_prices = {}
    business_days = pd.bdate_range(start_date, end_date)

    # Récupération des prix
    for ticker in tickers:
        # !!! IMPORTANT: We are now using the direct API function for stocks
        prices = fetch_stock_history_direct_api(ticker, start_date, end_date)
        # If you wanted to switch back to yfinance, uncomment the line below and comment the one above:
        # prices = fetch_stock_history(ticker, start_date, end_date)

        if not prices.empty:
            # Reindexing to ensure all business days are present, forward-filling, then backward-filling
            prices = prices.reindex(business_days).ffill().bfill()
            historical_prices[ticker] = prices
        else:
            st.warning(f"Aucune donnée valide récupérée pour {ticker} après re-indexation et remplissage. Il est possible que le ticker n'existe pas ou qu'il n'y ait pas de données pour cette période.")


    # Récupération des taux de change (this part remains unchanged)
    historical_fx = {}
    unique_currencies = set(currencies)
    unique_currencies.add(target_currency)

    for currency in unique_currencies:
        if currency != target_currency:
            fx_series = fetch_historical_fx_rates(currency, target_currency, start_date, end_date)
            if fx_series is not None and not fx_series.empty:
                fx_series = fx_series.reindex(business_days).ffill().bfill()
                historical_fx[f"{currency}/{target_currency}"] = fx_series
            else:
                st.warning(f"Impossible de récupérer les taux de change historiques pour {currency}/{target_currency}.")
    
    return historical_prices, historical_fx


@st.cache_data(ttl=3600)
def fetch_historical_fx_rates(base_currency, target_currency, start_date, end_date):
    """
    Récupère l'historique des taux de change pour une paire de devises via exchangerate.host.
    """
    if base_currency == target_currency:
        return pd.Series(1.0, index=pd.bdate_range(start_date, end_date), name=f"{base_currency}/{target_currency}")

    api_url = f"https://api.exchangerate.host/timeseries"
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
        st.error(f"Une erreur inattendue s'est produite pour les taux de change {base_currency}/{target_currency} : {builtins.str(e)}")
    
    return pd.Series(dtype='float64')
