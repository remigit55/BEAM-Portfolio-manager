# data_fetcher.py

import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from scipy.stats import linregress

# Cache pour 1 heure (3600 secondes)
@st.cache_data(ttl=3600)
def fetch_fx_rates(target_currency="EUR"):
    """
    Récupère les taux de change actuels par rapport à une devise cible.
    Utilise EUR comme devise de base par défaut pour les taux de change populaires.
    """
    fx_rates = {}
    currencies_to_fetch = ["USD", "EUR", "GBP", "CAD", "JPY", "CHF"] 

    for currency in currencies_to_fetch:
        if currency == target_currency:
            fx_rates[currency] = 1.0
            continue

        ticker_symbol = f"{currency}{target_currency}=X" 
        try:
            data = yf.download(ticker_symbol, period="1d", interval="1h", progress=False)
            if not data.empty:
                fx_rates[currency] = data['Close'].iloc[-1]
            else:
                st.warning(f"Impossible de récupérer le taux pour {ticker_symbol}. Essaie l'inverse.")
                ticker_symbol_inverse = f"{target_currency}{currency}=X" 
                data_inverse = yf.download(ticker_symbol_inverse, period="1d", interval="1h", progress=False)
                if not data_inverse.empty:
                    fx_rates[currency] = 1 / data_inverse['Close'].iloc[-1]
                else:
                    st.error(f"Taux de change pour {currency}/{target_currency} non trouvé via YFinance.")
                    fx_rates[currency] = None 
        except Exception as e:
            st.error(f"Erreur lors de la récupération du taux {ticker_symbol}: {e}")
            fx_rates[currency] = None 
            
    fx_rates[target_currency] = 1.0 

    return fx_rates


@st.cache_data(ttl=600) # Cache pour 10 minutes
def fetch_yahoo_data(ticker_symbol):
    """
    Récupère le nom court, le prix actuel et le plus haut sur 52 semaines pour un ticker.
    Utilise yfinance.
    Retourne aussi un indicateur si le prix est en pence (GBp) et doit être divisé par 100.
    """
    data = {}
    is_gbp_pence = False # Nouvel indicateur

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        data['shortName'] = info.get('shortName') or info.get('longName') or ticker_symbol
        data['currentPrice'] = info.get('currentPrice')
        data['fiftyTwoWeekHigh'] = info.get('fiftyTwoWeekHigh')

        # --- Logique de détection GBp ---
        currency_yahoo = info.get('currency')
        if currency_yahoo == 'GBp': 
            is_gbp_pence = True
        elif currency_yahoo == 'GBP' and ticker_symbol.endswith((".L", "^L")): 
            is_gbp_pence = True

        if is_gbp_pence:
            if data['currentPrice'] is not None and not np.isnan(data['currentPrice']):
                data['currentPrice'] /= 100
            if data['fiftyTwoWeekHigh'] is not None and not np.isnan(data['fiftyTwoWeekHigh']):
                data['fiftyTwoWeekHigh'] /= 100

    except Exception as e:
        data['shortName'] = ticker_symbol 
        data['currentPrice'] = np.nan
        data['fiftyTwoTwoWeekHigh'] = np.nan
        is_gbp_pence = False 
        
    data['is_gbp_pence'] = is_gbp_pence 
    return data

@st.cache_data(ttl=3600) # Cache pour 1 heure
def fetch_momentum_data(ticker_symbol, months=12):
    """
    Calcule le momentum (taux de changement) et le Z-score pour un ticker sur X mois.
    Utilise yfinance pour récupérer les données historiques.
    Applique une correction pour les prix en pence si nécessaire.
    """
    try:
        end_date = datetime.now()
        # Utilisez 5 ans de données pour la moyenne mobile de 39 semaines (environ 9 mois)
        # et le rolling Z-score de 10 semaines (environ 2.5 mois)
        # Il faut suffisamment de données pour que les fenêtres de rolling se remplissent.
        # 5 ans est plus que suffisant pour 39 semaines.
        start_date = end_date - timedelta(days=5 * 365) # Utilisez 5 ans pour les calculs robustes

        data = yf.download(ticker_symbol, start=start_date, end=end_date, interval="1wk", progress=False) # Important: interval="1wk"

        if data.empty or 'Close' not in data.columns:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "Pas de données historiques disponibles."
            }

        is_gbp_pence_for_momentum = False
        try:
            ticker_info = yf.Ticker(ticker_symbol).info
            currency_yahoo = ticker_info.get('currency')
            if currency_yahoo == 'GBp' or (currency_yahoo == 'GBP' and ticker_symbol.endswith((".L", "^L"))):
                is_gbp_pence_for_momentum = True
        except Exception:
            pass 

        if is_gbp_pence_for_momentum:
            # Assurez-vous que les colonnes existent avant de diviser
            for col in ['Close', 'Open', 'High', 'Low']:
                if col in data.columns:
                    data[col] = data[col] / 100

        # Utilisez .copy() pour éviter SettingWithCopyWarning
        df = pd.DataFrame({'Close': data['Close']}).copy()
        
        # S'assurer qu'il y a suffisamment de données pour les rolling windows
        if len(df) < 39: # Minimum number of data points for MA_39
            return {
                "Last Price": df['Close'].iloc[-1] if not df['Close'].empty else np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Insuffisant",
                "Action": "Plus de données requises",
                "Justification": "Pas assez de données pour calculer le momentum (moins de 39 semaines)."
            }

        df['MA_39'] = df['Close'].rolling(window=39).mean()
        df['Momentum'] = (df['Close'] / df['MA_39']) - 1
        df['Z_Momentum'] = (df['Momentum'] - df['Momentum'].rolling(10).mean()) / df['Momentum'].rolling(10).std()

        # Récupérer la dernière ligne
        latest = df.iloc[-1]

        # S'assurer que les valeurs sont scalaires (même si elles sont NaN)
        z = latest['Z_Momentum'] if pd.notna(latest['Z_Momentum']) else np.nan
        m = (latest['Momentum'] * 100) if pd.notna(latest['Momentum']) else np.nan
        latest_price = latest['Close'] if pd.notna(latest['Close']) else np.nan

        signal = "Neutre"
        action = "Maintenir"
        justification = ""

        if pd.notna(z): # N'évaluer que si z n'est pas NaN
            if z > 2:
                signal = "🔥 Surchauffe"
                action = "Alléger / Prendre profits"
                justification = "Momentum extrême, risque de retournement"
            elif z > 1.5:
                signal = "↗ Fort"
                action = "Surveiller"
                justification = "Momentum soutenu, proche de surchauffe"
            elif z > 0.5:
                signal = "↗ Haussier"
                action = "Conserver / Renforcer"
                justification = "Momentum sain"
            elif z > -0.5:
                signal = "➖ Neutre"
                action = "Ne rien faire"
                justification = "Pas de signal exploitable"
            elif z > -1.5:
                signal = "↘ Faible"
                action = "Surveiller / Réduire si confirmé"
                justification = "Dynamique en affaiblissement"
            else: # z <= -1.5
                signal = "🧊 Survendu"
                action = "Acheter / Renforcer (si signal technique)"
                justification = "Purge excessive, possible bas de cycle"
        else:
            justification = "Z-Score non calculable."

        if pd.notna(m):
            justification += f" Momentum: {m:.2f}%."
        
        if pd.notna(z):
            justification += f" Z-Score: {z:.2f}."


        return {
            "Last Price": latest_price,
            "Momentum (%)": m, # m est déjà en pourcentage et gère le NaN
            "Z-Score": z,       # z gère déjà le NaN
            "Signal": signal,
            "Action": action,
            "Justification": justification
        }

    except Exception as e:
        # st.error(f"Erreur lors du calcul du momentum pour {ticker_symbol}: {e}")
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "Erreur",
            "Action": "N/A",
            "Justification": f"Erreur de calcul: {e}"
        }
