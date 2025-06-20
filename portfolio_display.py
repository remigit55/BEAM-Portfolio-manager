import streamlit as st
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np # Assurez-vous d'importer numpy si ce n'est pas déjà fait

# Votre fonction portfolio_display existante (exemple)
def portfolio_display():
    st.title("Mon Portefeuille d'Investissement")

    # --- Votre code existant pour le tableau du portefeuille ---
    # Exemple de données de portefeuille (à remplacer par vos vraies données si ce n'est pas déjà fait)
    # Assurez-vous que cette partie existe déjà et génère `df_portefeuille`
    portfolio_data = {
        'Ticker': ['MSFT', 'AAPL', 'GOOGL', 'AMZN'],
        'Quantité': [10, 15, 5, 8],
        'Prix Achat': [300, 150, 120, 100],
        'Prix Actuel': [320, 160, 130, 110]
    }
    df_portefeuille = pd.DataFrame(portfolio_data)
    # Calculer la valeur actuelle et les plus/moins values
    df_portefeuille['Valeur Actuelle'] = df_portefeuille['Quantité'] * df_portefeuille['Prix Actuel']
    df_portefeuille['Plus/Moins Value'] = (df_portefeuille['Prix Actuel'] - df_portefeuille['Prix Achat']) * df_portefeuille['Quantité']

    st.header("Résumé du Portefeuille")
    st.dataframe(df_portefeuille) # C'est votre tableau principal

    # --- DÉBUT DE L'INTÉGRATION DU CODE D'ANALYSE DE MOMENTUM ---

    st.header("Analyse de Momentum des Actifs du Portefeuille")

    # Utilisons la liste de tickers que vous avez fournie pour ce test
    tickers_to_analyze = [
        "GLDG", "COP", "TTE", "CVX", "LJP3.L", "APGO.V", "FVL.V", "RVG.V", "SSV.V", "MUX",
        "SLVR.V", "LNG", "CCJ", "PBR", "HCC", "BTU", "CBR.V", "NIO", "EL", "UEC", "NFGC",
        "WNS", "FUTU", "AUMB.V", "YUMC", "TLK", "HSTR.V", "HDB", "RDY", "F34.SI", "PSLV",
        "AGX.V", "BEKE", "TCOM", "IBN", "PDD", "BABA", "JD", "LTOD.IL", "1157.HK", "BIDU",
        "INFY", "BCM.V", "Y92.SI"
    ]

    results = {}
    period = "5y"
    interval = "1wk"

    # Utilisez st.spinner pour montrer que le calcul est en cours
    with st.spinner("Calcul du momentum en cours... Cela peut prendre un certain temps pour de nombreux tickers."):
        for ticker in tickers_to_analyze:
            # Utilisez st.expander pour chaque ticker pour organiser les graphiques
            with st.expander(f"Détails du Momentum pour **{ticker}**"):
                try:
                    data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
                    
                    if data.empty:
                        st.warning(f"**Aucune donnée historique trouvée** pour {ticker} pour la période/intervalle spécifié(e).")
                        continue

                    # Gestion du MultiIndex comme dans votre exemple original
                    if isinstance(data.columns, pd.MultiIndex):
                        # Assurez-vous que la colonne spécifique au ticker existe
                        if ('Close', ticker) in data.columns:
                            close = data['Close'][ticker]
                        else:
                            st.error(f"**Erreur :** La colonne 'Close' pour le ticker {ticker} n'a pas été trouvée dans le MultiIndex des données téléchargées.")
                            continue
                    else:
                        if 'Close' in data.columns:
                            close = data['Close']
                        else:
                            st.error(f"**Erreur :** La colonne 'Close' n'a pas été trouvée dans les données de {ticker}.")
                            continue

                    # Vérification si la série 'close' est vide après extraction
                    if close.empty:
                        st.warning(f"La série de prix 'Close' est **vide** pour {ticker}.")
                        continue

                    # Assurez-vous que 'close' est une Series et non un DataFrame d'une seule colonne (cas rares)
                    if isinstance(close, pd.DataFrame) and len(close.columns) == 1:
                        close = close.iloc[:, 0] # Convertir en Series

                    df_momentum = pd.DataFrame({'Close': close})

                    # Vérification si suffisamment de données sont disponibles après le nettoyage
                    # Minimum 39 pour MA_39, mais le Z-Score a besoin de 10 points de momentum,
                    # donc la taille totale doit être au moins 39 + 10 - 1 = 48 semaines pour un Z-score stable.
                    # Pour un calcul minimal, on garde 39.
                    if len(df_momentum) < 39: 
                        st.warning(f"**Données insuffisantes** pour {ticker} pour calculer le momentum (moins de 39 semaines).")
                        continue
                    
                    df_momentum['MA_39'] = df_momentum['Close'].rolling(window=39, min_periods=1).mean() # min_periods pour permettre calcul début
                    df_momentum['Momentum'] = (df_momentum['Close'] / df_momentum['MA_39']) - 1
                    
                    # Gestion des cas où std est zéro pour éviter division par zéro ou NaN
                    momentum_std_10 = df_momentum['Momentum'].rolling(10, min_periods=1).std()
                    momentum_mean_10 = df_momentum['Momentum'].rolling(10, min_periods=1).mean()

                    df_momentum['Z_Momentum'] = (df_momentum['Momentum'] - momentum_mean_10) / momentum_std_10
                    df_momentum['Z_Momentum'] = df_momentum['Z_Momentum'].replace([np.inf, -np.inf], np.nan) # Gérer infinis si std est 0

                    # Vérification pour s'assurer qu'il y a des données après les calculs
                    if df_momentum.empty or df_momentum['Z_Momentum'].isnull().all():
                        st.warning(f"Momentum ou Z-Score non calculable pour {ticker} (données insuffisantes ou erreurs de calcul après MA/Momentum).")
                        continue

                    latest = df_momentum.iloc[-1]
                    z = latest['Z_Momentum']
                    m = latest['Momentum'] * 100

                    signal = "Neutre"
                    action = "Maintenir"
                    reason = "Pas de signal exploitable." # Valeur par défaut

                    if pd.notna(z): # Vérifier que Z-score n'est pas NaN
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
                        else: # z <= -1.5
                            signal = "🧊 Survendu"
                            action = "Acheter / Renforcer (si signal technique)"
                            reason = "Purge excessive, possible bas de cycle"
                    else:
                        reason = "Z-Score non calculable (données insuffisantes ou volatilité nulle)."


                    results[ticker] = {
                        "Last Price": round(latest['Close'], 2) if pd.notna(latest['Close']) else np.nan,
                        "Momentum (%)": round(m, 2) if pd.notna(m) else np.nan,
                        "Z-Score": round(z, 2) if pd.notna(z) else np.nan,
                        "Signal": signal,
                        "Action": action,
                        "Justification": reason
                    }

                    # Graphique Streamlit
                    fig, ax = plt.subplots(figsize=(12, 4)) # Crée une figure et un axe
                    ax.plot(df_momentum.index, df_momentum['Z_Momentum'], label=f'{ticker} - Z Momentum')
                    ax.axhline(0, color='gray', linestyle='--')
                    ax.axhline(2, color='red', linestyle='--', label='Surchauffe (+2σ)')
                    ax.axhline(-2, color='green', linestyle='--', label='Survendu (-2σ)')
                    ax.set_title(f'Oscillateur de Momentum - {ticker}')
                    ax.legend()
                    ax.grid(True)
                    st.pyplot(fig) # Affiche la figure Matplotlib dans Streamlit
                    plt.close(fig) # Ferme la figure pour libérer la mémoire

                except Exception as e:
                    st.error(f"**Erreur inattendue** lors du calcul du momentum pour {ticker}: {e}")
                    results[ticker] = {
                        "Last Price": np.nan,
                        "Momentum (%)": np.nan,
                        "Z-Score": np.nan,
                        "Signal": "Erreur",
                        "Action": "N/A",
                        "Justification": f"Erreur de calcul: {e}."
                    }
    
    # Résumé global des résultats de momentum
    if results: # N'afficher que si des résultats ont été collectés
        results_df = pd.DataFrame(results).T
        results_df = results_df.sort_values(by="Z-Score", ascending=False)
        st.subheader("Synthèse de l'Analyse de Momentum")
        st.dataframe(results_df)
    else:
        st.info("Aucun résultat de momentum disponible pour les tickers spécifiés après traitement.")

# --- FIN DE L'INTÉGRATION DU CODE D'ANALYSE DE MOMENTUM ---

# Appel de la fonction pour exécuter le code dans votre application Streamlit
# Si portfolio_display est déjà appelée dans votre script principal (par ex. app.py),
# assurez-vous qu'elle est appelée ici ou là-bas.
# portfolio_display() # Décommentez si vous exécutez ce fichier directement et que cette fonction n'est pas appelée ailleurs.
