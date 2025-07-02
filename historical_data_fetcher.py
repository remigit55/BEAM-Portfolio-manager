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
def fetch_historical_fx_rates(source_currencies, target_currency, start_date, end_date, interval="1d"):
    """
    Récupère les taux de change historiques pour les paires de devises via Yahoo Finance.
    
    Args:
        source_currencies: List of source currencies (e.g., ['USD', 'GBP']).
        target_currency: Target currency (e.g., 'EUR').
        start_date: Start date for historical data.
        end_date: End date for historical data.
        interval: Data interval ('1d' for daily, '1wk' for weekly).
    
    Returns:
        dict: {date: {currency_pair: rate}}
    """
    fx_rates = {}
    business_days = pd.bdate_range(start=start_date, end=end_date)
    
    for source_currency in source_currencies:
        if source_currency == target_currency:
            continue
        pair = f"{source_currency}{target_currency}=X"
        try:
            ticker = yf.Ticker(pair)
            hist = ticker.history(start=start_date, end=end_date + timedelta(days=1), interval=interval, progress=False)
            if not hist.empty:
                hist = hist[['Close']].reset_index()
                hist['Date'] = pd.to_datetime(hist['Date']).dt.date
                hist = hist.rename(columns={'Close': 'Rate'})
                # Interpolate to daily rates if using weekly data
                if interval == "1wk":
                    hist = hist.set_index('Date').reindex(business_days).interpolate(method='linear').reset_index()
                    hist['Date'] = hist['index']
                    hist = hist.drop(columns=['index'])
                for _, row in hist.iterrows():
                    date = row['Date']
                    if date not in fx_rates:
                        fx_rates[date] = {}
                    fx_rates[date][f"{source_currency}{target_currency}"] = row['Rate']
            else:
                st.warning(f"Aucune donnée de taux de change pour {pair} entre {start_date} et {end_date}.")
        except Exception as e:
            st.error(f"Erreur lors de la récupération des taux pour {pair} : {builtins.str(type(e).__name__)} - {builtins.str(e)}")
    
    # Ensure all business days have rates (fill missing with 1.0)
    for date in business_days:
        date = date.date()
        if date not in fx_rates:
            fx_rates[date] = {f"{c}{target_currency}": 1.0 for c in source_currencies if c != target_currency}
    
    return fx_rates

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

    interval = "1wk" if (end_date - start_date).days > 365 else "1d"
    historical_fx = fetch_historical_fx_rates(currencies, target_currency, start_date, end_date, interval=interval)
            
    return historical_prices, historical_fx
