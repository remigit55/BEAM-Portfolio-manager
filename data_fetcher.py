# data_fetcher.py

import streamlit as st
import pandas as pd
import requests
import time
import yfinance as yf
import datetime # Nécessaire pour st.cache_data ttl

# --- Fonctions de récupération de données externes ---

@st.cache_data(ttl=3600) # Cache les taux de change pendant 1 heure (3600 secondes)
def fetch_fx_rates(base="EUR"):
    """
    Récupère les taux de change depuis exchangerate.host.
    """
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("rates", {})
    except Exception as e:
        st.error(f"Erreur lors de la récupération des taux de change pour {base}: {e}")
        return {}

# Utilisez st.cache_data car cette fonction renvoie un dictionnaire sérialisable
@st.cache_data(ttl=900) # Cache les données Yahoo pour 15 minutes (900 secondes)
def fetch_yahoo_data(t):
    """
    Récupère shortName, currentPrice et 52WeekHigh pour un ticker via Yahoo Finance API.
    Utilise un cache interne pour les appels récurrents et le cache Streamlit.
    """
    t = str(t).strip().upper()
    # Cache interne dans session_state pour éviter les appels redondants DANS LE MÊME RUN
    # (bien que st.cache_data gère déjà ça entre les runs)
    if t in st.session_state.get("ticker_names_cache", {}):
        cached = st.session_state.ticker_names_cache[t]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else: # Si le cache contient une entrée invalide, la supprimer
            del st.session_state.ticker_names_cache[t]
    
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=10) # Augmenter le timeout si nécessaire
        r.raise_for_status()
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        
        name = meta.get("shortName", f"https://finance.yahoo.com/quote/{t}")
        current_price = meta.get("regularMarketPrice", None)
        fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
        
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        
        # Mettre à jour le cache interne de session_state
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}
        st.session_state.ticker_names_cache[t] = result
        
        # Un petit délai pour éviter de surcharger l'API de Yahoo, si vous avez beaucoup de tickers
        # time.sleep(0.1) # Désactivé par défaut, car st.cache_data réduit les appels réels
        
        return result
    except Exception as e:
        print(f"Erreur lors de la récupération des données Yahoo pour {t}: {e}")
        # Mettre en cache les erreurs pour ne pas retenter constamment
        st.session_state.ticker_names_cache[t] = {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwo_week_high": None}
        return st.session_state.ticker_names_cache[t]

# Utilisez st.cache_data car cette fonction renvoie un dictionnaire sérialisable
@st.cache_data(ttl=3600) # Cache les données de momentum pendant 1 heure
def fetch_momentum_data(ticker, period="5y", interval="1wk"):
    """
    Effectue une analyse de momentum pour un ticker donné en utilisant yfinance.
    """
    try:
        data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False, show_errors=False)
        if data.empty or 'Close' not in data.columns:
            # print(f"Aucune donnée valide pour {ticker}")
            return {
                "Last Price": None, "Momentum (%)": None, "Z-Score": None,
                "Signal": "", "Action": "", "Justification": ""
            }

        # S'assurer que 'Close' est une Series simple si data est un MultiIndex (pour certains tickers)
        if isinstance(data.columns, pd.MultiIndex):
            if ('Close', ticker) in data.columns: # Pour les cas comme MSFT ou GOOG
                close = data['Close'][ticker]
            elif ('Close', '') in data.columns: # Pour les cas sans sub-ticker
                 close = data['Close']['']
            else:
                 close = data['Close'].iloc[:, 0] # Fallback si structure différente
        else:
            close = data['Close']
        
        df_m = pd.DataFrame({'Close': close}).dropna()

        if df_m.empty:
            return {
                "Last Price": None, "Momentum (%)": None, "Z-Score": None,
                "Signal": "", "Action": "", "Justification": ""
            }

        df_m['MA_39'] = df_m['Close'].rolling(window=39).mean()
        df_m['Momentum'] = (df_m['Close'] / df_m['MA_39']) - 1
        df_m['Z_Momentum'] = (df_m['Momentum'] - df_m['Momentum'].rolling(10).mean()) / df_m['Momentum'].rolling(10).std()

        latest = df_m.iloc[-1]
        z = latest.get('Z_Momentum')
        m = latest.get('Momentum') * 100 if pd.notna(latest.get('Momentum')) else None

        if pd.isna(z):
            return {
                "Last Price": round(latest['Close'], 2) if pd.notna(latest.get('Close')) else None,
                "Momentum (%)": None, "Z-Score": None, "Signal": "", "Action": "", "Justification": ""
            }

        if z > 2:
            signal = "🔥 Surchauffe"
            action = "Alléger / Prendre profits"
            reason = "Momentum extrême, risque de retournement"
        elif z > 1.5:
            signal = "↗ Fort"
            action = "Surveiller"
            reason = "Momentum soutenu, proche de surchauffe"
        elif z > 0.5:
            signal = "↗ Haussier"
            action = "Conserver / Renforcer"
            reason = "Momentum sain"
        elif z > -0.5:
            signal = "➖ Neutre"
            action = "Ne rien faire"
            reason = "Pas de signal exploitable"
        elif z > -1.5:
            signal = "↘ Faible"
            action = "Surveiller / Réduire si confirmé"
            reason = "Dynamique en affaiblissement"
        else:
            signal = "🧊 Survendu"
            action = "Acheter / Renforcer (si signal technique)"
            reason = "Purge excessive, possible bas de cycle"

        return {
            "Last Price": round(latest['Close'], 2) if pd.notna(latest.get('Close')) else None,
            "Momentum (%)": round(m, 2) if pd.notna(m) else None,
            "Z-Score": round(z, 2) if pd.notna(z) else None,
            "Signal": signal,
            "Action": action,
            "Justification": reason
        }
    except Exception as e:
        # print(f"Erreur lors de l'analyse du momentum pour {ticker}: {e}")
        return {
            "Last Price": None, "Momentum (%)": None, "Z-Score": None,
            "Signal": "", "Action": "", "Justification": ""
        }
