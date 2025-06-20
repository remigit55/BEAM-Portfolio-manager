# historical_performance_calculator.py

import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# from historical_data_fetcher import get_all_historical_data # Will be called from here

def calculate_daily_portfolio_value(snapshot_data, date, historical_prices, historical_fx, target_currency):
    """
    Calcule la valeur du portefeuille pour une date donnée en utilisant les cours et taux historiques.
    """
    df_snapshot = snapshot_data['portfolio_data']
    current_date_str = date.strftime("%Y-%m-%d")

    daily_portfolio_value_acquisition = 0.0
    daily_portfolio_value_current = 0.0

    # ### NOUVEAU LOG POUR DÉBUG
    print(f"DEBUG calculate_daily_portfolio_value pour la date: {date}")
    print(f"DEBUG Ticker du snapshot: {df_snapshot['Ticker'].tolist()}")
    # ### FIN LOG

    for _, row in df_snapshot.iterrows():
        ticker = row.get("Ticker")
        quantity = row.get("Quantité", 0)
        acquisition_price = row.get("Acquisition", 0)
        source_currency = row.get("Devise", target_currency).upper() # Default to target_currency if not specified

        if pd.isna(quantity) or quantity == 0:
            continue

        # Get historical current price for the ticker
        current_price = np.nan
        if ticker and ticker in historical_prices and current_date_str in historical_prices[ticker].index:
            current_price = historical_prices[ticker].loc[current_date_str]
        
        # ### MODIFICATION : Si le prix courant n'est pas disponible, utilisez le prix d'acquisition.
        if pd.isna(current_price) or current_price == 0: # Ajout de current_price == 0 pour éviter division par zéro ou valeur nulle
             print(f"DEBUG Pas de prix historique pour {ticker} à {current_date_str}. Utilisation du prix d'acquisition {acquisition_price} comme prix actuel.")
             current_price = acquisition_price
             
        # Get historical FX rate for conversion to target_currency (for current value)
        fx_rate_to_target = 1.0 # ### MODIFICATION : Valeur par défaut
        if source_currency != target_currency:
            # Check for direct rate in historical_fx
            if source_currency in historical_fx and current_date_str in historical_fx[source_currency].index:
                temp_rate = historical_fx[source_currency].loc[current_date_str]
                if pd.notna(temp_rate) and temp_rate != 0: # ### MODIFICATION : Vérifier que le taux n'est pas NaN ou 0
                    fx_rate_to_target = temp_rate
                    print(f"DEBUG Taux {source_currency}/{target_currency} trouvé pour {current_date_str}: {fx_rate_to_target}") # LOG
                else:
                    print(f"DEBUG Taux {source_currency}/{target_currency} est NaN/zéro pour {current_date_str}. Défaut à 1.0 (valeur actuelle).") # LOG
            else:
                print(f"DEBUG Taux {source_currency}/{target_currency} non trouvé dans historical_fx pour {current_date_str}. Défaut à 1.0 (valeur actuelle).") # LOG

        # Calculate historical acquisition value and current value in their original currency
        asset_acquisition_value_original_currency = quantity * acquisition_price
        asset_current_value_original_currency = quantity * current_price

        # Convert acquisition value to target currency - Need acquisition currency to target currency FX rate
        acquisition_currency = source_currency 

        fx_rate_from_acquisition_currency = 1.0 # ### MODIFICATION : Valeur par défaut
        if acquisition_currency != target_currency:
            if acquisition_currency in historical_fx and current_date_str in historical_fx[acquisition_currency].index:
                temp_rate = historical_fx[acquisition_currency].loc[current_date_str]
                if pd.notna(temp_rate) and temp_rate != 0: # ### MODIFICATION : Vérifier que le taux n'est pas NaN ou 0
                    fx_rate_from_acquisition_currency = temp_rate
                    print(f"DEBUG Taux {acquisition_currency}/{target_currency} trouvé pour {current_date_str}: {fx_rate_from_acquisition_currency}") # LOG
                else:
                    print(f"DEBUG Taux {acquisition_currency}/{target_currency} est NaN/zéro pour {current_date_str}. Défaut à 1.0 (valeur d'acquisition).") # LOG
            else:
                print(f"DEBUG Taux {acquisition_currency}/{target_currency} non trouvé dans historical_fx pour {current_date_str}. Défaut à 1.0 (valeur d'acquisition).") # LOG

        daily_portfolio_value_acquisition += asset_acquisition_value_original_currency * fx_rate_from_acquisition_currency
        daily_portfolio_value_current += asset_current_value_original_currency * fx_rate_to_target
        
        # ### NOUVELLE LIGNE DE DÉBUG POUR CHAQUE ACTIF
        print(f"DEBUG {ticker}: Quantité={quantity}, Prix Acq={acquisition_price}, Prix Actuel={current_price}, Devise Source={source_currency}")
        print(f"  -> Taux FX vers cible (actuel)={fx_rate_to_target}, Taux FX vers cible (acq)={fx_rate_from_acquisition_currency}")
        print(f"  -> Valeur Acq après FX={asset_acquisition_value_original_currency * fx_rate_from_acquisition_currency}, Valeur Actuelle après FX={asset_current_value_original_currency * fx_rate_to_target}")
        # ### FIN LOG
        
    # ### NOUVELLE LIGNE DE DÉBUG POUR LES TOTAUX JOURNALIERS
    print(f"DEBUG Total Acq pour {date}: {daily_portfolio_value_acquisition}, Total Actuel pour {date}: {daily_portfolio_value_current}")
    # ### FIN LOG

    return daily_portfolio_value_acquisition, daily_portfolio_value_current


def reconstruct_historical_performance(portfolio_journal, historical_prices, historical_fx, target_currency, start_date, end_date):
    # ... (le reste de cette fonction reste inchangé)
    # Assurez-vous que cette fonction reçoit bien historical_fx, même s'il est vide ou partiel
    # Le comportement de fallback est géré dans calculate_daily_portfolio_value
    
    historical_data = []
    
    # Ensure end_date includes today for performance display, but actual data might be until yesterday
    # If using date.today(), it will cause issues, better use max_journal_date for logical end
    today_date_obj = datetime.now().date()
    
    # Generate business days range
    # Ensure start_date and end_date for bdate_range are date objects
    dates_range = pd.bdate_range(start_date, end_date) # Should be date objects
    
    # ### NOUVEAU LOG POUR DÉBUG
    print(f"DEBUG Dates à reconstruire: {dates_range.tolist()}")
    # ### FIN LOG
    
    current_snapshot_index = 0
    # Initialize current_portfolio_state with the first snapshot or empty if journal is empty
    current_portfolio_state = portfolio_journal[0] if portfolio_journal else {'date': date.min, 'portfolio_data': pd.DataFrame(), 'target_currency': target_currency}
    
    for date_as_date in dates_range:
        # Update portfolio state if a new snapshot is available for this date or before
        while current_snapshot_index + 1 < len(portfolio_journal) and \
              portfolio_journal[current_snapshot_index + 1]['date'] <= date_as_date:
            current_snapshot_index += 1
            current_portfolio_state = portfolio_journal[current_snapshot_index]
            
        # ### NOUVEAU LOG POUR DÉBUG
        print(f"DEBUG État du portefeuille pour {date_as_date}: Snapshot du {current_portfolio_state['date']}")
        # ### FIN LOG

        # Calculate values for the current date using the current_portfolio_state
        daily_acquisition, daily_current = calculate_daily_portfolio_value(
            current_portfolio_state, date_as_date, historical_prices, historical_fx, target_currency
        )
        
        # Add to results if we have valid data
        if not (np.isnan(daily_acquisition) or np.isnan(daily_current)):
            historical_data.append({
                "Date": date_as_date,
                "Valeur Acquisition": daily_acquisition,
                "Valeur Actuelle": daily_current,
                "Devise": target_currency # Store the target currency used for this day
            })
        else:
            print(f"DEBUG Données NaN pour {date_as_date}, saut de l'ajout à l'historique.") # LOG
    
    if not historical_data:
        print("DEBUG historical_data est vide. Retourne DataFrame vide.") # LOG
        return pd.DataFrame()

    df_reconstructed = pd.DataFrame(historical_data)
    df_reconstructed["Gain/Perte Absolu"] = df_reconstructed["Valeur Actuelle"] - df_reconstructed["Valeur Acquisition"]
    df_reconstructed["Gain/Perte (%)"] = df_reconstructed.apply(
        lambda row: (row["Gain/Perte Absolu"] / row["Valeur Acquisition"]) * 100 if row["Valeur Acquisition"] != 0 else 0,
        axis=1
    )
    
    # ### NOUVEAU LOG POUR DÉBUG
    print(f"DEBUG df_reconstructed head:\n{df_reconstructed.head()}")
    print(f"DEBUG df_reconstructed tail:\n{df_reconstructed.tail()}")
    # ### FIN LOG

    return df_reconstructed
