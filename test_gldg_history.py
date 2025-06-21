# test_gldg_history.py
from datetime import datetime, timedelta
import pandas as pd
from historical_data_fetcher import fetch_stock_history

def test_gldg_data_fetch():
    print("--- Test de récupération de l'historique pour GLDG ---")

    ticker = "GLDG"
    end_date = datetime.now().date()
    # Récupérer l'historique sur les 30 derniers jours
    start_date = end_date - timedelta(days=30)

    print(f"Tentative de récupération des données pour {ticker} du {start_date} au {end_date}...")
    historical_prices = fetch_stock_history(ticker, start_date, end_date)

    if not historical_prices.empty:
        print(f"Données récupérées pour {ticker}:")
        print(historical_prices.head())
        print(f"\n... (dernières 5 entrées)")
        print(historical_prices.tail())
        print(f"\nNombre de jours: {len(historical_prices)}")
        print(f"Type de données: {type(historical_prices)}")
        print(f"Index est un DatetimeIndex: {isinstance(historical_prices.index, pd.DatetimeIndex)}")
    else:
        print(f"Aucune donnée récupérée pour {ticker} sur la période spécifiée.")
        print("Vérifiez le ticker ou la période.")

if __name__ == "__main__":
    test_gldg_data_fetch()
