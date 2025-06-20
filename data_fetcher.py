import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

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
            
            current_rate = np.nan # Initialiser comme NaN

            # Traiter les données du ticker original
            if not data.empty and 'Close' in data.columns and not data['Close'].empty:
                temp_val = data['Close'].iloc[-1]
                # S'assurer que temp_val est un scalaire. Si c'est une Series de longueur 1, la convertir.
                if isinstance(temp_val, pd.Series) and len(temp_val) == 1:
                    temp_val = temp_val.item() # Forcer la conversion en scalaire
                
                if pd.notna(temp_val):
                    current_rate = temp_val
            
            # Si le taux original est toujours NaN, essayer le ticker inverse
            if pd.isna(current_rate): # Cette vérification est maintenant sûre car current_rate est toujours scalaire ou NaN
                st.warning(f"Impossible d'obtenir un taux valide pour {ticker_symbol}. Essai de l'inverse.")
                ticker_symbol_inverse = f"{target_currency}{currency}=X" 
                data_inverse = yf.download(ticker_symbol_inverse, period="1d", interval="1h", progress=False)

                if not data_inverse.empty and 'Close' in data_inverse.columns and not data_inverse['Close'].empty:
                    temp_val_inverse = data_inverse['Close'].iloc[-1]
                    # S'assurer que temp_val_inverse est un scalaire
                    if isinstance(temp_val_inverse, pd.Series) and len(temp_val_inverse) == 1:
                        temp_val_inverse = temp_val_inverse.item() # Forcer la conversion en scalaire

                    if pd.notna(temp_val_inverse) and temp_val_inverse != 0:
                        current_rate = 1 / temp_val_inverse
                    else:
                        st.error(f"Taux de change pour {currency}/{target_currency} non trouvé via YFinance (inverse vide, NaN ou zéro).")
                else:
                    st.error(f"Taux de change pour {currency}/{target_currency} non trouvé via YFinance (données inverses vides).")
            
            # Assigner le taux final
            if pd.notna(current_rate):
                fx_rates[currency] = current_rate
            else:
                fx_rates[currency] = None # Définir explicitement à None si le taux n'a pas pu être obtenu

        except Exception as e:
            st.error(f"Erreur lors de la récupération du taux {ticker_symbol}: {e}")
            fx_rates[currency] = None 
            
    # S'assurer que la devise cible elle-même est 1.0
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
    is_gbp_pence = False 

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info
        
        data['shortName'] = info.get('shortName') or info.get('longName') or ticker_symbol
        data['currentPrice'] = info.get('currentPrice')
        data['fiftyTwoWeekHigh'] = info.get('fiftyTwoWeekHigh')

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
        data['fiftyTwoWeekHigh'] = np.nan
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
        start_date = end_date - timedelta(days=5 * 365) # 5 ans pour calculs robustes

        data = yf.download(ticker_symbol, start=start_date, end=end_date, interval="1wk", progress=False)

        # Vérifier si les données sont vides ou si la colonne 'Close' est manquante
        if data.empty or 'Close' not in data.columns:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "Pas de données historiques disponibles."
            }
        
        # Vérification explicite : si la colonne 'Close' existe mais est vide
        if data['Close'].empty:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "La colonne 'Close' ne contient pas de données pour la période demandée."
            }


        # Détection GBp et correction des prix si nécessaire
        is_gbp_pence_for_momentum = False
        try:
            ticker_info = yf.Ticker(ticker_symbol).info
            currency_yahoo = ticker_info.get('currency')
            if currency_yahoo == 'GBp' or (currency_yahoo == 'GBP' and ticker_symbol.endswith((".L", "^L"))):
                is_gbp_pence_for_momentum = True
        except Exception:
            pass 

        if is_gbp_pence_for_momentum:
            for col in ['Close', 'Open', 'High', 'Low']:
                if col in data.columns:
                    data[col] = data[col] / 100.0

        # Créer un DataFrame pour les calculs de momentum avec une colonne 'Close' valide
        df = pd.DataFrame({'Close': data['Close']}).copy()
        
        # Vérifier si suffisamment de données sont disponibles après le nettoyage
        if len(df) < 39: 
            last_price = df['Close'].iloc[-1] if not df['Close'].empty else np.nan
            return {
                "Last Price": last_price,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Insuffisant",
                "Action": "Plus de données requises",
                "Justification": "Pas assez de données pour calculer le momentum (moins de 39 semaines)."
            }

        # Calcul des indicateurs de momentum
        df['MA_39'] = df['Close'].rolling(window=39, min_periods=1).mean()
        df['Momentum'] = (df['Close'] / df['MA_39']) - 1
        
        df['Momentum_Mean_10'] = df['Momentum'].rolling(window=10, min_periods=1).mean()
        df['Momentum_Std_10'] = df['Momentum'].rolling(window=10, min_periods=1).std()

        df['Z_Momentum'] = (df['Momentum'] - df['Momentum_Mean_10']) / df['Momentum_Std_10']
        df['Z_Momentum'] = df['Z_Momentum'].replace([np.inf, -np.inf], np.nan)

        # Récupérer la dernière ligne pour les valeurs finales
        if df.empty:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Erreur",
                "Action": "Vérifier Ticker",
                "Justification": "DataFrame vide après calculs."
            }

        latest = df.iloc[-1]

        # Extraire les valeurs finales, en s'assurant qu'elles sont scalaires et non NaN
        latest_price = latest['Close'] if pd.notna(latest['Close']) else np.nan
        m = (latest['Momentum'] * 100.0) if pd.notna(latest['Momentum']) else np.nan
        z = latest['Z_Momentum'] if pd.notna(latest['Z_Momentum']) else np.nan

        signal = "Neutre"
        action = "Maintenir"
        justification = ""

        if pd.notna(z):
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
            "Momentum (%)": m,
            "Z-Score": z,
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
            "Justification": f"Erreur de calcul: {e}."
        }
