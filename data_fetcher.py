import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

# Cache pour 1 minute (60 secondes)
@st.cache_data(ttl=60)
def fetch_fx_rates(target_currency="EUR"):
    """
    Récupère les taux de change actuels par rapport à une devise cible.
    Utilise EUR comme devise de base par défaut pour les taux de change populaires.
    """
    fx_rates = {}
    currencies_to_fetch = ["USD", "EUR", "GBP", "CAD", "JPY", "CHF", "HKD", "SGD", "THB", "VND", "PHP", "AUD", "CNY"]

    for currency in currencies_to_fetch:
        if currency == target_currency:
            fx_rates[f"{currency}/{target_currency}"] = 1.0
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
            if pd.isna(current_rate):
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
                fx_rates[currency] = None

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
    Si le prix actuel n'est pas disponible (None ou NaN), tente de récupérer la dernière clôture historique.
    """
    data = {}
    is_gbp_pence = False

    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info

        data['shortName'] = info.get('shortName') or info.get('longName') or ticker_symbol
        
        # Tentative 1: currentPrice (prix de marché actuel)
        current_price_found = info.get('currentPrice')
        
        # Tentative 2: regularMarketPrice si currentPrice est None
        if current_price_found is None:
            current_price_found = info.get('regularMarketPrice')

        # Si toujours pas de prix "live", tenter de récupérer la dernière clôture historique
        if current_price_found is None or pd.isna(current_price_found):
            # Tente de récupérer la dernière clôture disponible avec un intervalle court (1m)
            hist_data = yf.download(ticker_symbol, period="1d", interval="1m", progress=False) 
            
            # Si aucune donnée 1m, tente avec un intervalle plus long (1h)
            if hist_data.empty:
                hist_data = yf.download(ticker_symbol, period="5d", interval="1h", progress=False) 
            
            # Si des données historiques ont été trouvées et contiennent 'Close'
            if not hist_data.empty and 'Close' in hist_data.columns and not hist_data['Close'].empty:
                last_historical_close = hist_data['Close'].iloc[-1]
                if pd.notna(last_historical_close):
                    current_price_found = float(last_historical_close)
                    # st.warning(f"Utilisation du dernier prix de clôture historique pour {ticker_symbol}: {current_price_found}")

        data['currentPrice'] = current_price_found
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
        # En cas d'erreur générale, les valeurs restent NaN
        # st.error(f"Erreur lors de la récupération des données Yahoo pour {ticker_symbol}: {e}") 
        data['shortName'] = ticker_symbol
        data['currentPrice'] = np.nan
        data['fiftyTwoWeekHigh'] = np.nan
        is_gbp_pence = False
        
    data['is_gbp_pence'] = is_gbp_pence
    return data

@st.cache_data(ttl=60) # Cache pour 1 minute
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

        close_series = pd.Series([]) # Initialise une Series vide
        
        if data.empty:
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "Pas de données historiques disponibles."
            }

        # Gère les colonnes MultiIndex (par exemple, lors du téléchargement de données pour plusieurs tickers)
        if isinstance(data.columns, pd.MultiIndex):
            if ('Close', ticker_symbol) in data.columns: # Vérifie si 'Close' du ticker spécifique existe
                close_series = data['Close'][ticker_symbol]
            elif 'Close' in data.columns: # Fallback si 'Close' est un MultiIndex mais sans le nom du ticker
                 close_series = data['Close'].iloc[:, 0] if isinstance(data['Close'], pd.DataFrame) else data['Close']
            else:
                 return {
                    "Last Price": np.nan,
                    "Momentum (%)": np.nan,
                    "Z-Score": np.nan,
                    "Signal": "Erreur",
                    "Action": "Vérifier Ticker",
                    "Justification": "Colonne 'Close' spécifique au ticker non trouvée dans le MultiIndex."
                }
        elif 'Close' in data.columns: # Colonnes simples standards
            close_series = data['Close']
        else: # Colonne 'Close' pas trouvée du tout
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "Manquant",
                "Action": "Vérifier Ticker",
                "Justification": "Colonne 'Close' non trouvée dans les données historiques."
            }
            
        # Maintenant, vérifie si la close_series extraite est vide
        if close_series.empty:
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
            pass # Ignorer les erreurs si info n'est pas dispo ici

        if is_gbp_pence_for_momentum:
            # Applique la correction directement à la close_series
            close_series = close_series / 100.0

        # Créer un DataFrame pour les calculs de momentum avec la colonne 'Close' valide
        df = pd.DataFrame({'Close': close_series}).copy()
        
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
        # Retourne les valeurs NaN en cas d'erreur
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "Erreur",
            "Action": "N/A",
            "Justification": f"Erreur de calcul: {e}."
        }


# --- Fonction plot_momentum_chart (si vous l'utilisez ailleurs) ---
def plot_momentum_chart(ticker, data_df):
    """
    Génère un graphique de prix et de momentum pour un ticker donné.
    data_df doit contenir les colonnes 'Close', 'MA_39', 'Momentum', 'Z_Momentum'.
    """
    if data_df.empty:
        st.write(f"Pas de données disponibles pour tracer le graphique de {ticker}.")
        return None

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Graphique des prix et MA
    ax1.plot(data_df.index, data_df['Close'], label='Prix Clôture', color='blue')
    ax1.plot(data_df.index, data_df['MA_39'], label='MA 39 semaines', color='red', linestyle='--')
    ax1.set_title(f'Prix et Moyenne Mobile 39 semaines pour {ticker}')
    ax1.set_ylabel('Prix')
    ax1.legend()
    ax1.grid(True)

    # Graphique du Momentum
    ax2.plot(data_df.index, data_df['Momentum'] * 100, label='Momentum (%)', color='green')
    ax2.axhline(0, color='gray', linestyle='--', linewidth=0.8) # Ligne zéro pour le momentum
    ax2.set_title(f'Momentum et Z-Score pour {ticker}')
    ax2.set_ylabel('Momentum (%)')
    ax2.legend(loc='upper left')
    ax2.grid(True)

    # Ajouter le Z-Score sur l'axe secondaire
    ax3 = ax2.twinx()
    ax3.plot(data_df.index, data_df['Z_Momentum'], label='Z-Score Momentum', color='purple', linestyle=':')
    ax3.set_ylabel('Z-Score')
    ax3.legend(loc='upper right')
    
    # Lignes pour les seuils de Z-Score
    ax3.axhline(2, color='orange', linestyle=':', linewidth=0.8, label='Z-Score > 2')
    ax3.axhline(1.5, color='orange', linestyle=':', linewidth=0.8, label='Z-Score > 1.5')
    ax3.axhline(-1.5, color='orange', linestyle=':', linewidth=0.8, label='Z-Score < -1.5')
    ax3.axhline(-2, color='orange', linestyle=':', linewidth=0.8, label='Z-Score < -2')
    
    # Formatage de l'axe des dates
    fig.autofmt_xdate()

    plt.tight_layout()
    
    # Sauvegarder le graphique dans un buffer pour l'affichage Streamlit
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    plt.close(fig) # Fermer la figure pour libérer la mémoire
    buf.seek(0)
    return buf
