# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
import requests
import json
import streamlit as st
import builtins

# La fonction is_pence_denominated est supprimée.

@st.cache_data(ttl=3600)
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance.
    La conversion pence-vers-livre n'est plus gérée ici.
    """
    try:
        if not builtins.isinstance(Ticker, builtins.str):
            st.warning(f"Ticker mal formé : {Ticker} (type: {builtins.str(type(Ticker).__name__)})")
            return pd.Series(dtype='float64')
        
        if not builtins.callable(yf.download):
            st.error("Erreur critique : yf.download n'est pas appelable. Conflit possible dans les imports.")
            return pd.Series(dtype='float64')

        data = yf.download(Ticker, start=start_date, end=end_date, progress=False)
        
        if not data.empty:
            if builtins.isinstance(data.columns, pd.MultiIndex):
                close_data = data[('Close', Ticker)] if ('Close', Ticker) in data.columns else None
                if close_data is not None:
                    close_data = close_data.rename(Ticker)
                else:
                    st.warning(f"Colonne ('Close', '{Ticker}') absente. Colonnes disponibles : {builtins.str(data.columns.tolist())}")
                    return pd.Series(dtype='float64')
            else:
                if 'Close' in data.columns:
                    close_data = data['Close'].rename(Ticker)
                else:
                    st.warning(f"Colonne 'Close' absente pour {Ticker}. Colonnes disponibles : {builtins.str(data.columns.tolist())}")
                    return pd.Series(dtype='float64')
            
            # La logique de conversion pence-vers-livre est supprimée d'ici.
            
            return close_data

        else:
            st.warning(f"Aucune donnée valide pour {Ticker} : DataFrame vide.")
            return pd.Series(dtype='float64')

    except Exception as e:
        error_msg = f"Erreur lors de la récupération pour {Ticker} : {builtins.str(type(e).__name__)} - {builtins.str(e)}"
        st.error(error_msg)
        return pd.Series(dtype='float64')

@st.cache_data(ttl=3600)
def fetch_historical_fx_rates(target_currency, start_date, end_date):
    """Récupère les taux de change historiques via yfinance."""
    base_currencies = ["USD", "HKD", "CNY", "SGD", "CAD", "AUD", "GBP", "EUR"]
    all_business_days = pd.bdate_range(start=start_date - timedelta(days=10), end=end_date)
    columns_to_create = [f"{c}{target_currency}" for c in base_currencies if c != target_currency]
    df_fx = pd.DataFrame(1.0, index=all_business_days, columns=columns_to_create)
    
    for base in base_currencies:
        if base == target_currency:
            continue
        pair_direct_yf = f"{base}{target_currency}=X"
        try:
            fx_data_direct = yf.download(pair_direct_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
            if not fx_data_direct.empty and 'Close' in fx_data_direct.columns:
                df_fx[f"{base}{target_currency}"] = fx_data_direct["Close"].reindex(all_business_days, method="ffill").fillna(1.0)
                continue 
        except Exception:
            pass 
        pair_inverse_yf = f"{target_currency}{base}=X"
        try:
            fx_data_inverse = yf.download(pair_inverse_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
            if not fx_data_inverse.empty and 'Close' in fx_data_inverse.columns:
                df_fx[f"{base}{target_currency}"] = (1 / fx_data_inverse["Close"]).reindex(all_business_days, method="ffill").fillna(1.0)
                continue 
        except Exception:
            pass 
        if base != "USD" and target_currency != "USD":
            usd_to_base_pair_yf = f"{base}USD=X"
            usd_to_target_pair_yf = f"{target_currency}USD=X" 
            try:
                fx_data_base_usd = yf.download(usd_to_base_pair_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
                fx_data_target_usd = yf.download(usd_to_target_pair_yf, start=start_date - timedelta(days=10), end=end_date, interval="1d", progress=False)
                if not fx_data_base_usd.empty and 'Close' in fx_data_base_usd.columns and \
                   not fx_data_target_usd.empty and 'Close' in fx_data_target_usd.columns:
                    base_usd_rates = fx_data_base_usd["Close"].reindex(all_business_days, method="ffill").fillna(1.0)
                    target_usd_rates = fx_data_target_usd["Close"].reindex(all_business_days, method="ffill").fillna(1.0)
                    df_fx[f"{base}{target_currency}"] = base_usd_rates * (1 / target_usd_rates)
            except Exception:
                pass 
    
    df_fx = df_fx.interpolate(method="linear").ffill().bfill()
    return df_fx

@st.cache_data(ttl=3600)
def get_all_historical_data(tickers, currencies, start_date, end_date, target_currency):
    """
    Récupère l'ensemble des données historiques nécessaires :
    - Cours des actions via Yahoo Finance
    - Taux de change
    """
    historical_prices = {}
    business_days = pd.bdate_range(start_date, end_date)
    ticker_currency_map = dict(zip(tickers, currencies)) if len(tickers) == len(currencies) else {}
    
    for ticker in tickers:
        # fetch_stock_history n'a plus besoin du paramètre currency pour la conversion pence
        prices = fetch_stock_history(ticker, start_date, end_date)
        if not prices.empty:
            prices = prices.reindex(business_days).ffill().bfill()
            historical_prices[ticker] = prices

    historical_fx_df = fetch_historical_fx_rates(target_currency, start_date, end_date)
    historical_fx = {col: historical_fx_df[col] for col in historical_fx_df.columns}
            
    return historical_prices, historical_fx
