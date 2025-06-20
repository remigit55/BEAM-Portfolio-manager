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
                    # Plus précis: si GBP n'est pas trouvé et EUR est cible, utiliser une source externe ou valeur par défaut
                    # Pour l'instant, garder None
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
        # Méthode 1: Vérifier la devise reportée par Yahoo Finance (si disponible et fiable)
        currency_yahoo = info.get('currency')
        if currency_yahoo == 'GBp': # Yahoo Finance peut parfois retourner 'GBp'
            is_gbp_pence = True
        elif currency_yahoo == 'GBP' and ticker_symbol.endswith((".L", "^L")): # Les tickers britanniques avec .L ou ^L sont souvent en pence
            is_gbp_pence = True
        # Méthode 2: Basé sur des tickers connus ou suffixe (si la méthode 1 n'est pas suffisante)
        # Vous pouvez ajouter ici une liste de tickers spécifiques ou des règles plus fines
        # Exemple: if ticker_symbol in ["VOD.L", "BP.L"]: is_gbp_pence = True

        # Appliquer la correction si c'est en pence
        if is_gbp_pence:
            if data['currentPrice'] is not None and not np.isnan(data['currentPrice']):
                data['currentPrice'] /= 100
            if data['fiftyTwoWeekHigh'] is not None and not np.isnan(data['fiftyTwoWeekHigh']):
                data['fiftyTwoWeekHigh'] /= 100
            # Note: Le 'Last Price' pour le momentum sera géré par fetch_momentum_data
            # qui doit aussi avoir une logique similaire si elle est cotée en GBp.
            # Pour l'instant, on se concentre sur currentPrice et fiftyTwoWeekHigh.

    except Exception as e:
        # st.warning(f"Impossible de récupérer les données pour {ticker_symbol} via yfinance: {e}")
        data['shortName'] = ticker_symbol 
        data['currentPrice'] = np.nan
        data['fiftyTwoWeekHigh'] = np.nan
        is_gbp_pence = False # Par défaut, pas en pence si erreur
        
    data['is_gbp_pence'] = is_gbp_pence # Retourner l'indicateur
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
        start_date = end_date - timedelta(days=months * 30) 

        data = yf.download(ticker_symbol, start=start_date, end=end_date, progress=False)

        if data.empty:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "Pas de données historiques disponibles."
            }

        # --- Logique de détection GBp pour les données historiques ---
        # C'est plus délicat ici car yfinance ne donne pas la devise pour chaque point de données
        # On doit se baser sur la devise principale récupérée via ticker.info ou le suffixe.
        # Idéalement, cette information devrait être passée depuis fetch_yahoo_data
        # Pour simplifier, on peut réutiliser une logique similaire ou faire un appel minimal.
        
        # Pour une approche plus robuste, on pourrait appeler fetch_yahoo_data pour obtenir 'is_gbp_pence'
        # ou, encore mieux, passer cette information si elle est déjà calculée.
        
        # Pour l'exemple, on refait une détection simple basée sur le ticker (moins performant si déjà fait)
        is_gbp_pence_for_momentum = False
        try:
            ticker_info = yf.Ticker(ticker_symbol).info
            currency_yahoo = ticker_info.get('currency')
            if currency_yahoo == 'GBp' or (currency_yahoo == 'GBP' and ticker_symbol.endswith((".L", "^L"))):
                is_gbp_pence_for_momentum = True
        except Exception:
            pass # Si on ne peut pas récupérer l'info, on ne corrige pas par défaut

        if is_gbp_pence_for_momentum:
            data['Close'] /= 100
            data['Open'] /= 100
            data['High'] /= 100
            data['Low'] /= 100
            # Ajuster aussi le volume si applicable, mais pour momentum, Close suffit

        latest_price = data['Close'].iloc[-1]
        oldest_price = data['Close'].iloc[0]
        
        if oldest_price == 0: 
            momentum_percent = np.nan
        else:
            momentum_percent = ((latest_price - oldest_price) / oldest_price) * 100

        returns = data['Close'].pct_change().dropna()
        if len(returns) > 1:
            mean_return = returns.mean()
            std_return = returns.std()
            if std_return == 0:
                z_score = 0 
            else:
                z_score = (returns.iloc[-1] - mean_return) / std_return
        else:
            z_score = np.nan
        
        signal = "Neutre"
        action = "Maintenir"
        justification = ""

        if pd.notna(momentum_percent):
            if momentum_percent > 10: 
                signal = "Fort positif"
                justification = f"Momentum > 10% ({momentum_percent:.2f}%)."
                if pd.notna(z_score) and z_score > 1.5: 
                    action = "Acheter"
                    justification += " Fortes performances récentes (Z-score élevé)."
                else:
                    action = "Conserver"
                    justification += " Performances stables."
            elif momentum_percent < -10: 
                signal = "Fort négatif"
                justification = f"Momentum < -10% ({momentum_percent:.2f}%)."
                if pd.notna(z_score) and z_score < -1.5: 
                    action = "Vendre"
                    justification += " Fortes baisses récentes (Z-score faible)."
                else:
                    action = "Observer"
                    justification += " Performances déclinantes."
            else:
                signal = "Neutre"
                action = "Maintenir"
                justification = f"Momentum modéré ({momentum_percent:.2f}%)."
        else:
            justification = "Momentum non calculable."

        if pd.notna(z_score):
             justification += f" Z-Score: {z_score:.2f}."


        return {
            "Last Price": latest_price,
            "Momentum (%)": momentum_percent,
            "Z-Score": z_score,
            "Signal": signal,
            "Action": action,
            "Justification": justification
        }

    except Exception as e:
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "Erreur",
            "Action": "N/A",
            "Justification": f"Erreur de calcul: {e}"
        }
