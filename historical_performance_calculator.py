# historical_performance_calculator.py

import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Import the necessary function from historical_data_fetcher.py
from historical_data_fetcher import get_all_historical_data

def calculate_daily_portfolio_value(snapshot_data, date, historical_prices, historical_fx, target_currency):
    """
    Calcule la valeur du portefeuille pour une date donnée en utilisant les cours et taux historiques.
    Inclut des vérifications de robustesse pour les types de données.
    """
    df_snapshot = snapshot_data['portfolio_data']
    current_date_str = date.strftime("%Y-%m-%d")

    daily_portfolio_value_acquisition = 0.0
    daily_portfolio_value_current = 0.0

    for index, row in df_snapshot.iterrows():
        # --- Vérifications défensives pour les types et les valeurs manquantes ---
        
        # Ticker
        ticker = row.get("Ticker")
        if not isinstance(ticker, str) or not ticker.strip(): # S'assurer que c'est une chaîne non vide
            # print(f"DEBUG: Skipping row {index} due to invalid Ticker: '{ticker}' (type: {type(ticker)})")
            continue # Ignorer cette ligne si le ticker est invalide

        # Quantité
        quantity = pd.to_numeric(row.get("Quantité"), errors='coerce')
        if pd.isna(quantity) or quantity <= 0: # Gérer les NaN et les quantités non positives
            # print(f"DEBUG: Skipping row {index} for Ticker '{ticker}' due to invalid Quantity: '{row.get('Quantité')}' (converted to {quantity})")
            continue

        # Prix d'Acquisition
        acquisition_price = pd.to_numeric(row.get("Acquisition"), errors='coerce')
        if pd.isna(acquisition_price):
            # print(f"DEBUG: Setting Acquisition Price to 0 for Ticker '{ticker}' due to invalid value: '{row.get('Acquisition')}'")
            acquisition_price = 0.0 # Défaut à 0.0 si le prix d'acquisition est invalide/manquant

        # Devise source
        source_currency = row.get("Devise", target_currency)
        if not isinstance(source_currency, str) or not source_currency.strip():
            # print(f"DEBUG: Defaulting Source Currency to '{target_currency}' for Ticker '{ticker}' due to invalid value: '{row.get('Devise')}'")
            source_currency = target_currency # Défaut à la devise cible si invalide
        source_currency = source_currency.upper() # Uniformiser la casse

        # --- Récupération des cours historiques ---
        current_price = np.nan
        if ticker in historical_prices:
            # Vérifier que l'objet dans historical_prices est bien une Series Pandas
            if isinstance(historical_prices[ticker], pd.Series):
                # Vérifier si la date est présente dans l'index de la série
                if current_date_str in historical_prices[ticker].index:
                    current_price = historical_prices[ticker].loc[current_date_str]
                # else:
                    # print(f"DEBUG: Date '{current_date_str}' not found in historical prices for '{ticker}'.")
            # else:
                # print(f"DEBUG: historical_prices['{ticker}'] is not a pandas Series (type: {type(historical_prices[ticker])}).")
        # else:
            # print(f"DEBUG: Ticker '{ticker}' not found in historical_prices.")
        
        if pd.isna(current_price): 
            current_price = acquisition_price # Retour au prix d'acquisition si le cours actuel n'est pas trouvé


        # --- Récupération des taux de change historiques ---
        fx_rate = 1.0
        if source_currency != target_currency:
            fx_key = (source_currency, target_currency)
            if fx_key in historical_fx:
                if isinstance(historical_fx[fx_key], pd.Series):
                    if current_date_str in historical_fx[fx_key].index:
                        fx_rate = historical_fx[fx_key].loc[current_date_str]
                    # else:
                        # print(f"DEBUG: Date '{current_date_str}' not found in FX rates for {fx_key}.")
                # else:
                    # print(f"DEBUG: historical_fx[{fx_key}] is not a pandas Series (type: {type(historical_fx[fx_key])}).")
            else:
                # Tente de trouver le taux inverse si le taux direct n'existe pas
                reverse_fx_key = (target_currency, source_currency)
                if reverse_fx_key in historical_fx and isinstance(historical_fx[reverse_fx_key], pd.Series):
                    if current_date_str in historical_fx[reverse_fx_key].index:
                        reverse_rate = historical_fx[reverse_fx_key].loc[current_date_str]
                        if reverse_rate != 0 and not pd.isna(reverse_rate):
                            fx_rate = 1.0 / reverse_rate
                        # else:
                            # print(f"DEBUG: Reverse FX rate for {reverse_fx_key} is 0 or NaN on {current_date_str}. Using default 1.0.")
                    # else:
                        # print(f"DEBUG: Date '{current_date_str}' not found in reverse FX rates for {reverse_fx_key}.")
                # else:
                    # print(f"DEBUG: FX pair {fx_key} or {reverse_fx_key} not found in historical_fx or not a Series.")
            
            if pd.isna(fx_rate): # Assurer que fx_rate est numérique après toutes les tentatives
                fx_rate = 1.0
                # print(f"DEBUG: Using default FX rate 1.0 for {source_currency} to {target_currency} on {current_date_str} due to missing data.")


        # --- Calcul des valeurs quotidiennes ---
        # S'assurer que toutes les valeurs sont numériques avant la multiplication
        daily_portfolio_value_acquisition += (quantity * acquisition_price) * fx_rate
        daily_portfolio_value_current += (quantity * current_price) * fx_rate
    
    return daily_portfolio_value_acquisition, daily_portfolio_value_current


def reconstruct_historical_performance(start_date, end_date, target_currency):
    """
    Reconstruit l'historique de la performance du portefeuille entre deux dates.
    """
    # Importation locale pour éviter les dépendances circulaires
    # (portfolio_journal.py pourrait importer historical_performance_calculator.py si on y sauvait des totaux)
    from portfolio_journal import load_portfolio_journal 
    
    portfolio_journal = load_portfolio_journal()

    # Filtrer les snapshots potentiellement invalides (par ex., si 'portfolio_data' n'est pas un DataFrame)
    # Cette logique de filtre doit être cohérente avec performance.py
    valid_snapshots = [
        s for s in portfolio_journal
        if 'portfolio_data' in s
        and isinstance(s['portfolio_data'], pd.DataFrame)
        and not s['portfolio_data'].empty
    ]
    portfolio_journal = valid_snapshots # Utiliser uniquement les snapshots valides

    if not portfolio_journal:
        return pd.DataFrame()

    # Trier les snapshots par date
    portfolio_journal.sort(key=lambda x: x['date'])

    # Récupérer les tickers et devises uniques de tous les snapshots pour la récupération des données
    all_tickers = set()
    all_currencies = set()
    for snapshot in portfolio_journal:
        # S'assurer que les colonnes 'Ticker' et 'Devise' existent et sont gérées
        if 'Ticker' in snapshot['portfolio_data'].columns:
            # Convertir en string et supprimer les espaces pour les tickers
            all_tickers.update(snapshot['portfolio_data']['Ticker'].dropna().astype(str).str.strip().unique())
        if 'Devise' in snapshot['portfolio_data'].columns:
            # Convertir en string et supprimer les espaces pour les devises
            all_currencies.update(snapshot['portfolio_data']['Devise'].dropna().astype(str).str.strip().unique())
    
    tickers = list(all_tickers)
    currencies = list(all_currencies)

    # Récupérer toutes les données historiques nécessaires
    # start_date et end_date sont déjà des objets datetime.datetime ici
    historical_prices, historical_fx = get_all_historical_data(tickers, currencies, start_date, end_date, target_currency)

    historical_data = []
    
    # Générer une plage de jours ouvrables pour la période d'analyse
    # S'assurer que start_date et end_date sont des dates pour pd.bdate_range
    business_days = pd.bdate_range(start_date.date(), end_date.date())

    current_snapshot_index = 0
    # Initialiser avec le premier snapshot valide
    if portfolio_journal:
        current_portfolio_state = portfolio_journal[current_snapshot_index]
    else:
        return pd.DataFrame() # Pas de snapshots, retourner un DataFrame vide


    for date_as_date in business_days:
        # Avancer l'état du portefeuille si un nouveau snapshot est disponible pour cette date ou avant
        while current_snapshot_index + 1 < len(portfolio_journal) and \
              portfolio_journal[current_snapshot_index + 1]['date'] <= date_as_date:
            current_snapshot_index += 1
            current_portfolio_state = portfolio_journal[current_snapshot_index]

        # Calculer les valeurs pour la date actuelle en utilisant le current_portfolio_state
        daily_acquisition, daily_current = calculate_daily_portfolio_value(
            current_portfolio_state, date_as_date, historical_prices, historical_fx, target_currency
        )
        
        # Ajouter aux résultats si nous avons des données valides (par ex., pas tous des NaNs)
        if not (np.isnan(daily_acquisition) or np.isnan(daily_current)):
            historical_data.append({
                "Date": date_as_date,
                "Valeur Acquisition": daily_acquisition,
                "Valeur Actuelle": daily_current,
                "Devise": target_currency # Stocker la devise cible utilisée pour ce jour
            })
    
    if not historical_data:
        return pd.DataFrame()

    df_reconstructed = pd.DataFrame(historical_data)
    df_reconstructed["Gain/Perte Absolu"] = df_reconstructed["Valeur Actuelle"] - df_reconstructed["Valeur Acquisition"]
    df_reconstructed["Gain/Perte (%)"] = df_reconstructed.apply(
        lambda row: (row["Gain/Perte Absolu"] / row["Valeur Acquisition"]) * 100 if row["Valeur Acquisition"] != 0 else 0,
        axis=1
    )
    
    # Formater la colonne Date en chaîne de caractères YYYY-MM-DD pour la cohérence de l'affichage si nécessaire
    df_reconstructed["Date"] = df_reconstructed["Date"].dt.strftime("%Y-%m-%d")

    return df_reconstructed
