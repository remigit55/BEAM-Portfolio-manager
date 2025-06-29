# historical_data_fetcher.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta, date
import requests
import json
import streamlit as st
import builtins

try:
    import yfinance as yf
except ImportError as e:
    st.error(f"Erreur d'importation dans historical_data_fetcher.py : {e}")
    raise

def is_pence_denominated(currency):
    """
    Détermine si un actif est libellé en pence (GBp) en fonction de la devise.
    Retourne True si une conversion (division par 100) est nécessaire.
    """
    return str(currency).strip().lower() in ['gbp', 'gbp.', 'gbp ']

@st.cache_data(ttl=3600)
def fetch_stock_history(Ticker, start_date, end_date, currency=None):
    """
    Récupère l'historique des cours de clôture ajustés pour un ticker donné via Yahoo Finance.
    Applique une conversion pence-vers-livre si la devise est GBp.
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
            
            # Appliquer la conversion pence-vers-livre si la devise est GBp
            if currency and is_pence_denominated(currency):
                close_data = close_data / 100.0
                st.info(f"Conversion pence-vers-livre appliquée pour {Ticker} (devise: {currency}).")
            
            # Debug logging for HOC.L
            if Ticker == 'HOC.L':
                st.write(f"DEBUG (historical_data_fetcher): HOC.L données brutes")
                st.write(f"  Devise: {currency}")
                st.write(f"  Prix brut (dernier): {close_data[-1] if not close_data.empty else 'N/A'}")
                st.write(f"  Prix après conversion GBp: {close_data[-1] if currency and is_pence_denominated(currency) else 'N/A'}")
            
            return close_data

        else:
            st.warning(f"Aucune donnée valide pour {Ticker} : DataFrame vide.")
            return pd.Series(dtype='float64')

    except Exception as e:
        error_msg = f"Erreur lors de la récupération pour {Ticker} : {builtins.str(type(e).__name__)} - {builtins.str(e)}"
        st.error(error_msg)
        return pd.Series(dtype='float64')
