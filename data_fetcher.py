import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt

# Cache pour 1 minute (60 secondes)
@st.cache_data(ttl=60)
def fetch_fx_rates(target_currency="EUR", all_currencies=None):
    """
    Récupère les taux de change actuels par rapport à une devise cible.
    Utilise EUR comme devise de base par défaut pour les taux de change populaires.
    """
    st.info(f"Tentative de récupération des taux de change avec yfinance. Devise cible: {target_currency}")
    fx_rates = {}
    
    # Si all_currencies n'est pas fourni, utilisez la liste par défaut.
    # Ceci est important car portfolio_display passe maintenant toutes les devises uniques.
    if all_currencies is None:
        currencies_to_fetch = ["USD", "EUR", "GBP", "CAD", "JPY", "CHF"]
    else:
        # Assurez-vous que la devise cible est toujours incluse
        currencies_to_fetch = list(set(all_currencies + [target_currency]))

    for currency in currencies_to_fetch:
        currency = currency.strip().upper() # Nettoyer et mettre en majuscules

        if currency == target_currency:
            fx_rates[currency] = 1.0
            fx_rates[f"{currency}/{target_currency}"] = 1.0 # Ajout explicite pour la paire
            st.info(f"Taux pour {currency}/{target_currency} défini à 1.0 (devise cible).")
            continue

        # Construire le ticker pour yfinance
        # On essaiera d'abord SOURCECIBLE=X puis CIBLESOURCE=X (inverse)
        ticker_symbol_direct = f"{currency}{target_currency}=X"
        ticker_symbol_inverse = f"{target_currency}{currency}=X"
        
        current_rate = np.nan # Initialiser comme NaN
        rate_found = False
        
        # Tenter de récupérer le taux direct
        try:
            st.info(f"Recherche du taux direct : {ticker_symbol_direct}")
            data_direct = yf.download(ticker_symbol_direct, period="1d", interval="1h", progress=False, timeout=10)
            if not data_direct.empty and 'Close' in data_direct.columns and not data_direct['Close'].empty:
                temp_val = data_direct['Close'].iloc[-1]
                if isinstance(temp_val, pd.Series) and len(temp_val) == 1:
                    temp_val = temp_val.item()
                if pd.notna(temp_val):
                    current_rate = temp_val
                    fx_rates[f"{currency}/{target_currency}"] = current_rate
                    st.success(f"✔️ Taux {ticker_symbol_direct} ({currency}/{target_currency}) récupéré : {current_rate}")
                    rate_found = True
            else:
                st.warning(f"Aucune donnée pour {ticker_symbol_direct} ou colonne 'Close' vide.")

        except Exception as e:
            st.error(f"❌ Erreur lors de la récupération du taux direct {ticker_symbol_direct}: {e}")

        # Si le taux direct n'est pas trouvé, tenter le taux inverse
        if not rate_found:
            try:
                st.info(f"Recherche du taux inverse : {ticker_symbol_inverse}")
                data_inverse = yf.download(ticker_symbol_inverse, period="1d", interval="1h", progress=False, timeout=10)
                if not data_inverse.empty and 'Close' in data_inverse.columns and not data_inverse['Close'].empty:
                    temp_val = data_inverse['Close'].iloc[-1]
                    if isinstance(temp_val, pd.Series) and len(temp_val) == 1:
                        temp_val = temp_val.item()
                    if pd.notna(temp_val) and temp_val != 0:
                        current_rate = 1 / temp_val # Inverser le taux
                        fx_rates[f"{currency}/{target_currency}"] = current_rate
                        st.success(f"✔️ Taux {ticker_symbol_inverse} récupéré et inversé ({currency}/{target_currency}) : {current_rate}")
                        rate_found = True
                else:
                    st.warning(f"Aucune donnée pour {ticker_symbol_inverse} ou colonne 'Close' vide.")

            except Exception as e:
                st.error(f"❌ Erreur lors de la récupération du taux inverse {ticker_symbol_inverse}: {e}")

        if not rate_found:
            st.error(f"❌ Impossible de récupérer le taux de change pour {currency}/{target_currency} via yfinance.")
            fx_rates[f"{currency}/{target_currency}"] = np.nan # Assurez-vous que N/A est bien un NaN numérique

    # Ajouter la devise cible elle-même si elle n'est pas dans les paires.
    # Utile si elle n'est pas listée dans les devises_a_fetch mais pourrait être nécessaire.
    if target_currency not in fx_rates:
         fx_rates[target_currency] = 1.0 # Cas où target_currency est 'EUR' et il n'y a pas de pair EUR/EUR=X
    if f"{target_currency}/{target_currency}" not in fx_rates:
        fx_rates[f"{target_currency}/{target_currency}"] = 1.0


    st.info("Fin de la récupération des taux de change.")
    return fx_rates


# --- Fonctions existantes pour Yahoo Data et Momentum (non modifiées ici) ---

@st.cache_data(ttl=3600)
def fetch_yahoo_data(ticker):
    """
    Récupère le nom court et le prix actuel pour un ticker donné.
    """
    if not ticker:
        return {}
    try:
        # Spécifiez les informations que vous voulez charger pour optimiser
        info = yf.Ticker(ticker).info
        return {
            "shortName": info.get("shortName", ticker),
            "currentPrice": info.get("currentPrice"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        }
    except Exception as e:
        # st.warning(f"Impossible de récupérer les données Yahoo pour {ticker}: {e}")
        return {"shortName": ticker, "currentPrice": np.nan, "fiftyTwoWeekHigh": np.nan}


@st.cache_data(ttl=3600)
def fetch_momentum_data(ticker, period="1y", interval="1wk"):
    """
    Calcule le momentum à 39 semaines, le Z-Score, le signal et la justification pour un ticker.
    """
    if not ticker:
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "",
            "Action": "",
            "Justification": "",
        }

    try:
        # Récupérer les données hebdomadaires
        data = yf.download(ticker, period=period, interval=interval, progress=False)

        if data.empty or 'Close' not in data.columns:
            # st.warning(f"Pas de données de clôture pour le calcul du momentum pour {ticker}.")
            return {
                "Last Price": np.nan,
                "Momentum (%)": np.nan,
                "Z-Score": np.nan,
                "Signal": "N/A",
                "Action": "N/A",
                "Justification": "Données de clôture manquantes ou vides.",
            }

        df = pd.DataFrame(data['Close']).rename(columns={'Close': 'Prix'})

        # Calculer la moyenne mobile sur 39 semaines
        df['MA_39_Semaines'] = df['Prix'].rolling(window=39).mean()

        # Calculer le momentum
        # Le momentum est le rapport du prix actuel sur la MA 39 semaines
        df['Momentum'] = (df['Prix'] / df['MA_39_Semaines']) - 1

        # Calculer la moyenne mobile du momentum sur 10 semaines pour le Z-Score
        df['MA_Momentum_10'] = df['Momentum'].rolling(window=10).mean()

        # Calculer l'écart-type du momentum sur 10 semaines
        df['Std_Momentum_10'] = df['Momentum'].rolling(window=10).std()

        # Calculer le Z-Score du momentum
        # Éviter la division par zéro si l'écart-type est nul
        df['Z_Momentum'] = np.where(df['Std_Momentum_10'] != 0, 
                                    (df['Momentum'] - df['MA_Momentum_10']) / df['Std_Momentum_10'], 
                                    np.nan)

        # Récupérer la dernière ligne pour les valeurs actuelles
        last_row = df.iloc[-1]
        last_price = last_row['Prix']
        momentum_percent = last_row['Momentum'] * 100
        z_score = last_row['Z_Momentum']

        # Déterminer le signal et l'action
        signal = "Neutre"
        action = "Maintenir"
        justification = ""

        if z_score >= 2:
            signal = "Surachat Fort"
            action = "Vente (Réduire)"
            justification = f"Le Z-Score ({z_score:.2f}) est > 2, indiquant un surachat important."
        elif z_score >= 1.5:
            signal = "Surachat Modéré"
            action = "Maintenir (Surveiller)"
            justification = f"Le Z-Score ({z_score:.2f}) est > 1.5, indiquant un surachat modéré."
        elif z_score <= -2:
            signal = "Survente Forte"
            action = "Achat (Renforcer)"
            justification = f"Le Z-Score ({z_score:.2f}) est < -2, indiquant une survente importante."
        elif z_score <= -1.5:
            signal = "Survente Modérée"
            action = "Maintenir (Surveiller)"
            justification = f"Le Z-Score ({z_score:.2f}) est < -1.5, indiquant une survente modérée."
        elif momentum_percent > 0:
            signal = "Momentum Positif"
            action = "Maintenir"
            justification = f"Le Momentum ({momentum_percent:.2f}%) est positif."
        else:
            signal = "Momentum Négatif"
            action = "Maintenir"
            justification = f"Le Momentum ({momentum_percent:.2f}%) est négatif."

        return {
            "Last Price": last_price,
            "Momentum (%)": momentum_percent,
            "Z-Score": z_score,
            "Signal": signal,
            "Action": action,
            "Justification": justification,
        }

    except Exception as e:
        # st.error(f"Erreur lors du calcul du momentum pour {ticker}: {e}")
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "Erreur",
            "Action": "Vérifier",
            "Justification": f"Erreur de calcul: {e}",
        }

def plot_momentum_chart(ticker, data_df):
    """
    Génère un graphique interactif avec Plotly pour le prix, la MA et le momentum/Z-score.
    """
    if data_df.empty or 'Prix' not in data_df.columns:
        st.warning(f"Pas de données suffisantes pour tracer le graphique de momentum pour {ticker}.")
        return

    # Création des sous-graphiques
    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1) # Partage l'axe X avec le premier graphique

    # Graphique des prix
    ax1.plot(data_df.index, data_df['Prix'], label='Prix', color='blue')
    ax1.plot(data_df.index, data_df['MA_39_Semaines'], label='MA 39 semaines', color='red', linestyle='--')
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

    plt.tight_layout()
    st.pyplot(fig) # Utilisez st.pyplot pour afficher le graphique Matplotlib
