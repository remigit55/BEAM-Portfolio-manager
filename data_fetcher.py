import streamlit as st
import yfinance as yf # Gardons l'import pour d'autres fonctions si elles l'utilisent encore
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import requests # Ajout de l'import pour les requêtes HTTP
import json     # Ajout de l'import pour traiter le JSON

# Cache pour 1 minute (60 secondes)
@st.cache_data(ttl=60)
def fetch_fx_rates(target_currency="EUR", all_currencies=None):
    """
    Récupère les taux de change actuels par rapport à une devise cible en utilisant exchangerate.host.
    Cette fonction est appelée par portfolio_display.py.
    """
    st.info(f"Tentative de récupération des taux de change pour le portefeuille avec exchangerate.host. Devise cible: {target_currency}")
    fx_rates = {}

    # Assurez-vous que la devise cible est en majuscules
    target_currency = target_currency.strip().upper()

    # Si all_currencies n'est pas fourni, utilisez la liste par default.
    # Ceci est important car portfolio_display passe maintenant toutes les devises uniques.
    if all_currencies is None:
        # Liste par défaut des devises si aucune n'est passée
        currencies_to_fetch = ["USD", "EUR", "GBP", "CAD", "JPY", "CHF"]
    else:
        # Nettoyer et mettre en majuscules toutes les devises, et s'assurer que la devise cible est incluse
        currencies_to_fetch = list(set([c.strip().upper() for c in all_currencies] + [target_currency]))

    # Taux pour la devise cible est toujours 1.0
    fx_rates[f"{target_currency}/{target_currency}"] = 1.0
    fx_rates[target_currency] = 1.0 # Pour le cas où la clé est juste la devise

    # Construire la liste des symboles pour l'API
    symbols_str = ",".join([c for c in currencies_to_fetch if c != target_currency])

    # Si aucune devise à convertir, retourner tôt
    if not symbols_str:
        st.info("Aucune autre devise à convertir que la devise cible pour le portefeuille. Retourne le taux par défaut.")
        return fx_rates

    # URL de l'API exchangerate.host pour les taux "latest"
    api_url = f"https://api.exchangerate.host/latest?base={target_currency}&symbols={symbols_str}"

    try:
        st.info(f"Requête API pour le portefeuille: {api_url}")
        response = requests.get(api_url, timeout=5)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)
        data = response.json()

        if data.get("success"):
            api_rates = data.get("rates", {})
            st.success(f"Réponse API reçue (succès) pour le portefeuille: {api_rates}")

            for currency in currencies_to_fetch:
                currency = currency.strip().upper()
                if currency == target_currency:
                    continue

                # Le taux de l'API est BASE/SYMBOL, soit TARGET/SOURCE.
                # Nous voulons SOURCE/TARGET. Donc il faut 1 / (TARGET/SOURCE).
                # Exemple : base=EUR, symbol=USD. api_rates['USD'] = 1.08 (1 EUR = 1.08 USD)
                # On veut USD/EUR, ce qui signifie 1 USD = ? EUR.
                # Donc 1 USD = 1/1.08 EUR = 0.9259 EUR.

                if currency in api_rates and pd.notna(api_rates[currency]) and api_rates[currency] != 0:
                    fx_rates[f"{currency}/{target_currency}"] = 1 / api_rates[currency] 
                    st.success(f"✔️ Taux {currency}/{target_currency} (via {target_currency}/{currency} inversé) pour le portefeuille : {fx_rates[f'{currency}/{target_currency}']:.4f}")
                else:
                    st.warning(f"Taux de {currency} par rapport à {target_currency} non trouvé ou invalide dans la réponse API pour le portefeuille. Taux pour {currency}/{target_currency} sera N/A.")
                    fx_rates[f"{currency}/{target_currency}"] = np.nan # Si non trouvé, NaN

        else:
            st.error(f"❌ La réponse de l'API exchangerate.host indique un échec pour le portefeuille: {data.get('error', 'Pas de message d\'erreur détaillé.')}")
            for currency in currencies_to_fetch:
                if currency != target_currency:
                    fx_rates[f"{currency}/{target_currency}"] = np.nan

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erreur de requête HTTP lors de la récupération des taux de change pour le portefeuille : {e}")
        for currency in currencies_to_fetch:
            if currency != target_currency:
                fx_rates[f"{currency}/{target_currency}"] = np.nan
    except json.JSONDecodeError as e:
        st.error(f"❌ Erreur de décodage JSON de la réponse API pour le portefeuille : {e}")
        for currency in currencies_to_fetch:
            if currency != target_currency:
                fx_rates[f"{currency}/{target_currency}"] = np.nan
    except Exception as e:
        st.error(f"❌ Une erreur inattendue est survenue lors de la récupération des taux de change pour le portefeuille : {e}")
        for currency in currencies_to_fetch:
            if currency != target_currency:
                fx_rates[f"{currency}/{target_currency}"] = np.nan

    st.info("Fin de la récupération des taux de change pour le portefeuille.")
    return fx_rates


# --- Fonctions existantes pour Yahoo Data et Momentum (non modifiées ici) ---
# Ces fonctions sont supposées être OK car elles sont dans data_fetcher.py
# et n'ont pas été la source principale des N/A pour les taux de change.

@st.cache_data(ttl=3600)
def fetch_yahoo_data(ticker):
    """
    Récupère le nom court et le prix actuel pour un ticker donné.
    """
    if not ticker:
        return {}
    try:
        info = yf.Ticker(ticker).info
        return {
            "shortName": info.get("shortName", ticker),
            "currentPrice": info.get("currentPrice"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        }
    except Exception as e:
        return {"shortName": ticker, "currentPrice": np.nan, "fiftyTwoWeekHigh": np.nan}


@st.cache_data(ttl=3600)
def fetch_momentum_data(ticker, period="1y", interval="1wk"):
    """
    Calcule le momentum à 39 semaines, le Z-Score, le signal et la justification pour un ticker.
    """
    if not ticker:
        return {
            "Last Price": np.nan, "Momentum (%)": np.nan, "Z-Score": np.nan,
            "Signal": "", "Action": "", "Justification": "",
        }

    try:
        data = yf.download(ticker, period=period, interval=interval, progress=False)

        if data.empty or 'Close' not in data.columns:
            return {
                "Last Price": np.nan, "Momentum (%)": np.nan, "Z-Score": np.nan,
                "Signal": "N/A", "Action": "N/A", "Justification": "Données de clôture manquantes ou vides.",
            }

        df = pd.DataFrame(data['Close']).rename(columns={'Close': 'Prix'})
        df['MA_39_Semaines'] = df['Prix'].rolling(window=39).mean()
        df['Momentum'] = (df['Prix'] / df['MA_39_Semaines']) - 1
        df['MA_Momentum_10'] = df['Momentum'].rolling(window=10).mean()
        df['Std_Momentum_10'] = df['Momentum'].rolling(window=10).std()
        df['Z_Momentum'] = np.where(df['Std_Momentum_10'] != 0, 
                                    (df['Momentum'] - df['MA_Momentum_10']) / df['Std_Momentum_10'], 
                                    np.nan)

        last_row = df.iloc[-1]
        last_price = last_row['Prix']
        momentum_percent = last_row['Momentum'] * 100
        z_score = last_row['Z_Momentum']

        signal = "Neutre"; action = "Maintenir"; justification = ""
        if z_score >= 2:
            signal = "Surachat Fort"; action = "Vente (Réduire)"; justification = f"Le Z-Score ({z_score:.2f}) est > 2, indiquant un surachat important."
        elif z_score >= 1.5:
            signal = "Surachat Modéré"; action = "Maintenir (Surveiller)"; justification = f"Le Z-Score ({z_score:.2f}) est > 1.5, indiquant un surachat modéré."
        elif z_score <= -2:
            signal = "Survente Forte"; action = "Achat (Renforcer)"; justification = f"Le Z-Score ({z_score:.2f}) est < -2, indiquant une survente importante."
        elif z_score <= -1.5:
            signal = "Survente Modérée"; action = "Maintenir (Surveiller)"; justification = f"Le Z-Score ({z_score:.2f}) est < -1.5, indiquant une survente modérée."
        elif momentum_percent > 0:
            signal = "Momentum Positif"; action = "Maintenir"; justification = f"Le Momentum ({momentum_percent:.2f}%) est positif."
        else:
            signal = "Momentum Négatif"; action = "Maintenir"; justification = f"Le Momentum ({momentum_percent:.2f}%) est négatif."

        return {
            "Last Price": last_price, "Momentum (%)": momentum_percent, "Z-Score": z_score,
            "Signal": signal, "Action": action, "Justification": justification,
        }

    except Exception as e:
        return {
            "Last Price": np.nan, "Momentum (%)": np.nan, "Z-Score": np.nan,
            "Signal": "Erreur", "Action": "Vérifier", "Justification": f"Erreur de calcul: {e}",
        }

def plot_momentum_chart(ticker, data_df):
    """
    Génère un graphique interactif avec Plotly pour le prix, la MA et le momentum/Z-score.
    """
    if data_df.empty or 'Prix' not in data_df.columns:
        st.warning(f"Pas de données suffisantes pour tracer le graphique de momentum pour {ticker}.")
        return

    fig = plt.figure(figsize=(12, 8))
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1])
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[1, 0], sharex=ax1)

    ax1.plot(data_df.index, data_df['Prix'], label='Prix', color='blue')
    ax1.plot(data_df.index, data_df['MA_39_Semaines'], label='MA 39 semaines', color='red', linestyle='--')
    ax1.set_title(f'Prix et Moyenne Mobile 39 semaines pour {ticker}')
    ax1.set_ylabel('Prix')
    ax1.legend(); ax1.grid(True)

    ax2.plot(data_df.index, data_df['Momentum'] * 100, label='Momentum (%)', color='green')
    ax2.axhline(0, color='gray', linestyle='--', linewidth=0.8)
    ax2.set_title(f'Momentum et Z-Score pour {ticker}')
    ax2.set_ylabel('Momentum (%)')
    ax2.legend(loc='upper left'); ax2.grid(True)

    ax3 = ax2.twinx()
    ax3.plot(data_df.index, data_df['Z_Momentum'], label='Z-Score Momentum', color='purple', linestyle=':')
    ax3.set_ylabel('Z-Score')
    ax3.legend(loc='upper right')

    ax3.axhline(2, color='orange', linestyle=':', linewidth=0.8, label='Z-Score > 2')
    ax3.axhline(1.5, color='orange', linestyle=':', linewidth=0.8, label='Z-Score > 1.5')
    ax3.axhline(-1.5, color='orange', linestyle=':', linewidth=0.8, label='Z-Score < -1.5')
    ax3.axhline(-2, color='orange', linestyle=':', linewidth=0.8, label='Z-Score < -2')

    plt.tight_layout()
    st.pyplot(fig)
