# historical_performance_calculator.py
import pandas as pd
from datetime import datetime, timedelta, date # Import date
import numpy as np
import streamlit as st # Nécessaire pour st.cache_data et les messages d'info/erreur
from historical_data_fetcher import get_all_historical_data # Import la fonction pour récupérer toutes les données historiques

def calculate_daily_portfolio_value(snapshot_data, date, historical_prices, historical_fx, target_currency):
    """
    Calcule la valeur du portefeuille pour une date donnée en utilisant les cours et taux historiques.
    """
    df_snapshot = snapshot_data['portfolio_data']
    current_date_str = date.strftime("%Y-%m-%d")

    daily_portfolio_value_acquisition = 0.0
    daily_portfolio_value_current = 0.0

    # Assurer que les colonnes nécessaires existent et sont du bon type, remplir les NaN si besoin
    # Ceci rend la fonction plus robuste face à des DF mal formés ou incomplets
    if 'Quantité' not in df_snapshot.columns:
        df_snapshot['Quantité'] = 0.0
    if 'Acquisition' not in df_snapshot.columns:
        df_snapshot['Acquisition'] = 0.0
    if 'Devise' not in df_snapshot.columns:
        df_snapshot['Devise'] = target_currency
    if 'Ticker' not in df_snapshot.columns:
        df_snapshot['Ticker'] = ''

    df_snapshot['Quantité'] = pd.to_numeric(df_snapshot['Quantité'], errors='coerce').fillna(0)
    df_snapshot['Acquisition'] = pd.to_numeric(df_snapshot['Acquisition'], errors='coerce').fillna(0)
    df_snapshot['Devise'] = df_snapshot['Devise'].fillna(target_currency).astype(str)
    df_snapshot['Ticker'] = df_snapshot['Ticker'].astype(str)


    for _, row in df_snapshot.iterrows():
        ticker = row.get("Ticker")
        quantity = row.get("Quantité", 0)
        acquisition_price = row.get("Acquisition", 0)
        source_currency = row.get("Devise", target_currency).upper() # Par défaut à la devise cible si non spécifié

        if pd.isna(quantity) or quantity == 0:
            continue

        # Récupérer le cours de clôture historique pour le ticker
        current_price = np.nan
        # Utiliser .get() pour éviter KeyError si le ticker n'est pas dans historical_prices
        if ticker and historical_prices.get(ticker) is not None and current_date_str in historical_prices[ticker].index:
            current_price = historical_prices[ticker].loc[current_date_str]
        
        # Si aucun prix spécifique n'est trouvé, utiliser le prix d'acquisition comme valeur actuelle (approche conservatrice)
        if pd.isna(current_price):
             current_price = acquisition_price 
             
        # Récupérer le taux de change historique
        fx_rate = 1.0 # Par défaut à 1.0 si la devise source est la devise cible ou si le taux n'est pas trouvé

        if source_currency != target_currency:
            fx_key = f"{source_currency}/{target_currency}"
            # Utiliser .get() pour éviter KeyError
            if historical_fx.get(fx_key) is not None and current_date_str in historical_fx[fx_key].index:
                fx_rate = historical_fx[fx_key].loc[current_date_str]
            
            # Si le taux de change est manquant, assumer 1.0. Cela peut être ajusté si une gestion d'erreur plus stricte est souhaitée.
            if pd.isna(fx_rate):
                fx_rate = 1.0 # Fallback : assumer pas de conversion si le taux est manquant

        # Calculer les valeurs dans la devise cible
        # La valeur d'acquisition et la valeur actuelle sont toutes deux converties avec le taux de change du jour.
        acquisition_value_in_target_currency = (quantity * acquisition_price) * fx_rate
        current_value_in_target_currency = (quantity * current_price) * fx_rate
        
        daily_portfolio_value_acquisition += acquisition_value_in_target_currency
        daily_portfolio_value_current += current_value_in_target_currency

    return daily_portfolio_value_acquisition, daily_portfolio_value_current

@st.cache_data(ttl=3600) # Met en cache le résultat de la reconstruction pour 1 heure
def reconstruct_historical_portfolio_value(df_current_portfolio, start_date_dt, end_date_dt, target_currency):
    """
    Reconstruit la valeur historique du portefeuille basée sur sa composition actuelle
    et les cours/taux de change historiques sur une période donnée.
    """
    if df_current_portfolio is None or df_current_portfolio.empty:
        st.warning("Le portefeuille actuel est vide. Impossible de calculer la performance historique.")
        return pd.DataFrame()

    # Extraire les tickers et devises uniques du portefeuille actuel pour la récupération des données
    tickers = df_current_portfolio['Ticker'].dropna().unique().tolist()
    currencies = df_current_portfolio['Devise'].dropna().unique().tolist()
    
    st.info(f"Début de la récupération des données historiques pour {len(tickers)} tickers et {len(currencies)} devises.")

    # Récupérer toutes les données historiques (cours et taux de change)
    # Cet appel est lui-même mis en cache dans historical_data_fetcher.py
    historical_prices, historical_fx = get_all_historical_data(
        tickers, currencies, start_date_dt, end_date_dt, target_currency
    )
    
    if not historical_prices and not historical_fx:
        st.error("Impossible de récupérer les données historiques des cours ou des taux de change. Vérifiez les tickers/devises ou votre connexion.")
        return pd.DataFrame()

    historical_data = []
    # Générer une série de jours ouvrables entre les dates de début et de fin
    business_days = pd.bdate_range(start_date_dt, end_date_dt)

    if business_days.empty:
        st.warning("Aucun jour ouvrable trouvé dans la période sélectionnée.")
        return pd.DataFrame()
        
    # Utiliser un seul état de portefeuille (le portefeuille actuel) pour tous les calculs historiques
    # Le 'date' dans snapshot_data est conceptuellement la date pour laquelle on calcule la valeur,
    # et non la date d'un "snapshot" de portefeuille qui changerait.
    fixed_portfolio_state = {'date': start_date_dt.date(), 'portfolio_data': df_current_portfolio.copy()}

    # Itérer sur chaque jour ouvrable et calculer la valeur du portefeuille
    for date_obj in business_days:
        date_as_date = date_obj.date() # Convertir Timestamp en objet date
        
        # Calculer la valeur d'acquisition et la valeur actuelle du portefeuille pour ce jour
        daily_acquisition, daily_current = calculate_daily_portfolio_value(
            fixed_portfolio_state, date_as_date, historical_prices, historical_fx, target_currency
        )
        
        # Ajouter les résultats si les données sont valides (pas NaN)
        if not (np.isnan(daily_acquisition) or np.isnan(daily_current)):
            historical_data.append({
                "Date": date_as_date,
                "Valeur Acquisition": daily_acquisition,
                "Valeur Actuelle": daily_current,
                "Devise": target_currency # Stocker la devise cible utilisée pour ce jour
            })
    
    if not historical_data:
        st.warning("Aucune donnée de valeur de portefeuille historique n'a pu être reconstruite.")
        return pd.DataFrame()

    # Créer le DataFrame final et calculer les gains/pertes
    df_reconstructed = pd.DataFrame(historical_data)
    df_reconstructed["Date"] = pd.to_datetime(df_reconstructed["Date"])
    df_reconstructed = df_reconstructed.set_index("Date").sort_index()

    df_reconstructed["Gain/Perte Absolu"] = df_reconstructed["Valeur Actuelle"] - df_reconstructed["Valeur Acquisition"]
    df_reconstructed["Gain/Perte (%)"] = df_reconstructed.apply(
        lambda row: (row["Gain/Perte Absolu"] / row["Valeur Acquisition"]) * 100 if row["Valeur Acquisition"] != 0 else 0,
        axis=1
    )
    
    return df_reconstructed
