# historical_performance_calculator.py

import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# from historical_data_fetcher import get_all_historical_data # Will be called from here

def calculate_daily_portfolio_value(snapshot_data, date, historical_prices, historical_fx, target_currency):
    """
    Calcule la valeur du portefeuille pour une date donnée en utilisant les cours et taux historiques.
    Inclut des vérifications de robustesse pour les types de données.
    """
    df_snapshot = snapshot_data['portfolio_data']
    # Assurez-vous que l'index de df_snapshot est un DatetimeIndex si nécessaire,
    # bien que .iterrows() ne dépende pas de l'index.
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
    # ... (le reste de la fonction reconstruct_historical_performance reste inchangé) ...
    # Assurez-vous que cette fonction appelle la version mise à jour de calculate_daily_portfolio_value
