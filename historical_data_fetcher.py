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

@st.cache_data(ttl=3600) # Cache les taux de change historiques pour 1 heure
def fetch_historical_fx_rates(target_currency, start_date, end_date):
    """Récupère les taux de change historiques via yfinance."""
    base_currencies = ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"] # Added EUR to base currencies
    all_dates = pd.date_range(start=start_date - timedelta(days=10), end=end_date)
    
    # Initialize DataFrame with default rates (1.0) for all pairs
    # Columns will be named as "SOURCETARGET" (e.g., "USDEUR")
    columns_to_create = [f"{c}{target_currency}" for c in base_currencies if c != target_currency]
    df_fx = pd.DataFrame(1.0, index=all_dates, columns=columns_to_create)
    
    for base in base_currencies:
        if base == target_currency:
            continue # No conversion needed for same currency

        # Try direct pair
        pair_direct_yf = f"{base}{target_currency}=X"
        try:
            fx_data_direct = yf.download(pair_direct_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
            if not fx_data_direct.empty and 'Close' in fx_data_direct.columns:
                df_fx[f"{base}{target_currency}"] = fx_data_direct["Close"].reindex(all_dates, method="ffill").fillna(1.0)
                continue 
        except Exception:
            pass 

        # Try inverse pair
        pair_inverse_yf = f"{target_currency}{base}=X"
        try:
            fx_data_inverse = yf.download(pair_inverse_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
            if not fx_data_inverse.empty and 'Close' in fx_data_inverse.columns:
                df_fx[f"{base}{target_currency}"] = (1 / fx_data_inverse["Close"]).reindex(all_dates, method="ffill").fillna(1.0)
                continue 
        except Exception:
            pass 

        # If direct and inverse failed, try via USD (only if both base and target are not USD)
        if base != "USD" and target_currency != "USD":
            usd_to_base_pair_yf = f"{base}USD=X"
            usd_to_target_pair_yf = f"{target_currency}USD=X" 
            
            try:
                fx_data_base_usd = yf.download(usd_to_base_pair_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
                fx_data_target_usd = yf.download(usd_to_target_pair_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)

                if not fx_data_base_usd.empty and 'Close' in fx_data_base_usd.columns and \
                   not fx_data_target_usd.empty and 'Close' in fx_data_target_usd.columns:
                    
                    base_usd_rates = fx_data_base_usd["Close"].reindex(all_dates, method="ffill").fillna(1.0)
                    target_usd_rates = fx_data_target_usd["Close"].reindex(all_dates, method="ffill").fillna(1.0)
                    
                    df_fx[f"{base}{target_currency}"] = base_usd_rates * (1 / target_usd_rates)
            except Exception:
                pass 
    
    df_fx = df_fx.interpolate(method="linear").ffill().bfill()
    return df_fx


@st.cache_data(ttl=3600) # Cache les données historiques globales pour 1 heure
def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère l'ensemble des données historiques nécessaires :
    - Cours des actions via Yahoo Finance
    - Taux de change
    """
    historical_prices = {}
    business_days = pd.bdate_range(start_date, end_date)

    for ticker in tickers:
        prices = fetch_stock_history(ticker, start_date, end_date)
        if not prices.empty:
            prices = prices.reindex(business_days).ffill().bfill()
            historical_prices[ticker] = prices

    # Use the new, robust fetch_historical_fx_rates
    historical_fx_df = fetch_historical_fx_rates(target_currency, start_date, end_date)
    
    # Convert DataFrame to dictionary of Series for compatibility with existing logic
    historical_fx = {col: historical_fx_df[col] for col in historical_fx_df.columns}
            
    return historical_prices, historical_fx
