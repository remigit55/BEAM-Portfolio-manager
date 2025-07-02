# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import builtins

@st.cache_data(ttl=3600)
def fetch_stock_history(Ticker, start_date, end_date):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance.
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
    # [Unchanged code, as it does not involve GBP-specific logic]
    # ... (same as original)

@st.cache_data(ttl=3600)
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

    historical_fx_df = fetch_historical_fx_rates(target_currency, start_date, end_date)
    historical_fx = {col: historical_fx_df[col] for col in historical_fx_df.columns}
            
    return historical_prices, historical_fx
