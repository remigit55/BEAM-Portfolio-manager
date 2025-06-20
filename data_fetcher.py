import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import io

# Cache pour stocker les résultats de yfinance.Ticker(ticker).info
@st.cache_data(ttl=3600) # Cache pendant 1 heure
def fetch_yahoo_data(ticker):
    try:
        # Débogage spécifique pour LJP3.L
        if ticker == "LJP3.L":
            st.write(f"🔍 Débogage Yahoo Data pour {ticker}...")
            
        info = yf.Ticker(ticker).info
        
        if ticker == "LJP3.L":
            st.write(f"Info complète pour {ticker}: {info}")
            st.write(f"Current Price pour {ticker}: {info.get('currentPrice')}")
            st.write(f"Fifty Two Week High pour {ticker}: {info.get('fiftyTwoWeekHigh')}")

        return {
            "shortName": info.get("shortName", ticker),
            "currentPrice": info.get("currentPrice"),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        }
    except Exception as e:
        st.error(f"⚠️ Erreur lors de la récupération des données Yahoo pour {ticker}: {e}")
        return {
            "shortName": ticker,
            "currentPrice": np.nan,
            "fiftyTwoWeekHigh": np.nan,
        }

# Cache pour stocker les résultats du calcul de momentum
@st.cache_data(ttl=3600) # Cache pendant 1 heure
def fetch_momentum_data(ticker):
    try:
        # Débogage spécifique pour LJP3.L
        if ticker == "LJP3.L":
            st.write(f"🔍 Débogage Momentum pour {ticker}...")
            st.write(f"Tentative de téléchargement des données pour {ticker}, period='5y', interval='1wk'")

        # Télécharger les données historiques
        data = yf.download(ticker, period="5y", interval="1wk", auto_adjust=True, progress=False)

        if ticker == "LJP3.L":
            st.write(f"Données brutes téléchargées pour {ticker} (head):\n", data.head())
            st.write(f"Colonnes de données pour {ticker}: {data.columns.tolist()}")

        if data.empty:
            if ticker == "LJP3.L": st.warning(f"Aucune donnée historique trouvée pour {ticker} pour la période spécifiée.")
            return {"Signal": "Pas de données", "Justification": "Aucune donnée historique yfinance trouvée pour cette période/intervalle."}

        # Assurez-vous que la colonne 'Close' est présente et est une série simple
        close_price_series = None
        if isinstance(data.columns, pd.MultiIndex):
            # Cas où yfinance retourne un MultiIndex (e.g. pour des indices ou si plusieurs tickers sont passés en même temps, peu probable ici)
            if ('Close', ticker) in data.columns:
                close_price_series = data['Close'][ticker]
            elif 'Close' in data.columns:
                # Si 'Close' est un top-level mais reste un DataFrame ou série à multiples niveaux
                close_price_series = data['Close']
            else:
                if ticker == "LJP3.L": st.error(f"La colonne 'Close' pour le ticker {ticker} n'a pas été trouvée dans le MultiIndex des données téléchargées.")
                return {"Signal": "Erreur données", "Justification": "Colonne 'Close' manquante ou format inattendu (MultiIndex)."}
        else:
            # Cas normal avec un Index simple
            if 'Close' in data.columns:
                close_price_series = data['Close']
            else:
                if ticker == "LJP3.L": st.error(f"La colonne 'Close' n'a pas été trouvée dans les données de {ticker}.")
                return {"Signal": "Erreur données", "Justification": "Colonne 'Close' manquante."}

        if close_price_series is None or close_price_series.empty:
            if ticker == "LJP3.L": st.warning(f"La série de prix 'Close' est vide ou non trouvée pour {ticker}.")
            return {"Signal": "Données vides", "Justification": "Série 'Close' vide ou non trouvée."}
        
        # S'assurer que close_price_series est une pd.Series simple
        if isinstance(close_price_series, pd.DataFrame):
            if len(close_price_series.columns) == 1:
                close_price_series = close_price_series.iloc[:, 0]
            else:
                if ticker == "LJP3.L": st.error(f"La série 'Close' est un DataFrame avec plusieurs colonnes pour {ticker}.")
                return {"Signal": "Erreur données", "Justification": "Série 'Close' n'est pas une série simple."}
        
        df_momentum = pd.DataFrame({'Close': close_price_series})

        if ticker == "LJP3.L": st.write(f"DataFrame momentum initial pour {ticker}:\n", df_momentum.head())

        # Vérifier si suffisamment de données pour le calcul
        if len(df_momentum) < 39:
            if ticker == "LJP3.L": st.warning(f"Pas assez de données pour {ticker} pour calculer le momentum (moins de 39 semaines). Nombre de points: {len(df_momentum)}")
            return {"Signal": "Données insuffisantes", "Justification": f"Moins de 39 semaines de données nécessaires pour MA_39 ({len(df_momentum)} trouvées)."}

        # Calcul de la MA 39 semaines
        df_momentum['MA_39'] = df_momentum['Close'].rolling(window=39, min_periods=1).mean()
        # Calcul du Momentum (Price / MA_39 - 1)
        df_momentum['Momentum'] = (df_momentum['Close'] / df_momentum['MA_39']) - 1

        # Calcul du Z-Score sur 10 semaines
        momentum_std_10 = df_momentum['Momentum'].rolling(10, min_periods=1).std()
        momentum_mean_10 = df_momentum['Momentum'].rolling(10, min_periods=1).mean()

        # Éviter la division par zéro pour le Z-Score
        df_momentum['Z_Momentum'] = (df_momentum['Momentum'] - momentum_mean_10) / momentum_std_10
        df_momentum['Z_Momentum'] = df_momentum['Z_Momentum'].replace([np.inf, -np.inf], np.nan)
        
        if ticker == "LJP3.L": st.write(f"DataFrame momentum intermédiaire pour {ticker}:\n", df_momentum.tail())

        if df_momentum.empty or df_momentum['Z_Momentum'].isnull().all():
            if ticker == "LJP3.L": st.warning(f"Momentum ou Z-Score non calculable pour {ticker} (données insuffisantes après calcul ou toutes NaN).")
            return {"Signal": "Non calculable", "Justification": "Momentum/Z-Score non calculable ou NaN après calcul."}

        latest = df_momentum.iloc[-1]
        z = latest['Z_Momentum']
        m = latest['Momentum'] * 100

        if ticker == "LJP3.L": st.write(f"Derniers calculs pour {ticker}: Z={z}, M={m}%")

        signal = "Neutre"
        action = "Conserver"
        reason = ""

        if pd.notna(z):
            if z > 2:
                signal = "Très Haussier"
                action = "Renforcer Achat"
                reason = "Z-Score très élevé, forte dynamique positive."
            elif z > 1.5:
                signal = "Haussier"
                action = "Achat"
                reason = "Z-Score élevé, bonne dynamique positive."
            elif z < -2:
                signal = "Très Baissier"
                action = "Renforcer Vente"
                reason = "Z-Score très bas, forte dynamique négative."
            elif z < -1.5:
                signal = "Baissier"
                action = "Vente"
                reason = "Z-Score bas, dynamique négative."
            
            # Ajustements pour la direction du momentum même dans le neutre
            if signal == "Neutre":
                if pd.notna(m):
                    if m > 0.05: # Petit momentum positif
                        reason = "Momentum positif léger, Z-Score neutre."
                    elif m < -0.05: # Petit momentum négatif
                        reason = "Momentum négatif léger, Z-Score neutre."
                    else:
                        reason = "Momentum et Z-Score neutres."
                else:
                    reason = "Z-Score neutre."
        else:
            signal = "Indéfini"
            action = "N/A"
            reason = "Z-Score non disponible."


        return {
            "Last Price": round(latest['Close'], 2) if pd.notna(latest['Close']) else np.nan,
            "Momentum (%)": round(m, 2) if pd.notna(m) else np.nan,
            "Z-Score": round(z, 2) if pd.notna(z) else np.nan,
            "Signal": signal,
            "Action": action,
            "Justification": reason
        }

    except Exception as e:
        if ticker == "LJP3.L": st.error(f"💥 Erreur inattendue dans fetch_momentum_data pour {ticker}: {e}")
        return {
            "Last Price": np.nan,
            "Momentum (%)": np.nan,
            "Z-Score": np.nan,
            "Signal": "Erreur",
            "Action": "N/A",
            "Justification": f"Erreur de calcul: {e}."
        }

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
