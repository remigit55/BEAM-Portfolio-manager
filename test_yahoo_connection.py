# test_yahoo_connection.py
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import builtins # Just in case, but shouldn't be needed here

def test_fetch_single_stock_data(ticker="MSFT", days_ago=30):
    """
    Tente de récupérer les données historiques d'un seul ticker
    pour une courte période et affiche le résultat.
    """
    print(f"Tentative de récupération des données pour {ticker}...")
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_ago)

        # Utiliser builtins.str au cas où, bien que dans un script minimaliste, ce ne soit pas censé être un problème.
        # Le but est de s'assurer que yf.download lui-même fonctionne.
        data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), 
                            end=end_date.strftime('%Y-%m-%d'), progress=False)

        if not data.empty:
            print(f"✅ Données récupérées avec succès pour {ticker} du {start_date.strftime('%Y-%m-%d')} au {end_date.strftime('%Y-%m-%d')}!")
            print("\nAperçu des 5 premières lignes :")
            print(data.head())
            print("\nAperçu des 5 dernières lignes :")
            print(data.tail())
            print(f"\nNombre total d'entrées : {len(data)}")
            print(f"Type de l'objet retourné : {builtins.str(type(data))}")
            print(f"L'index est un DatetimeIndex : {builtins.isinstance(data.index, pd.DatetimeIndex)}")
            return True
        else:
            print(f"❌ Aucune donnée récupérée pour {ticker} sur la période spécifiée.")
            print("Vérifiez le ticker ou la période, et votre connexion internet.")
            return False

    except Exception as e:
        print(f"❌ Erreur lors de la récupération des données pour {ticker} : {builtins.str(e)}")
        # C'est ici que l'erreur 'str' object is not callable apparaîtrait si elle persistait
        # mais dans ce script isolé, cela serait très surprenant.
        return False

if __name__ == "__main__":
    print("--- Test de connectivité Yahoo Finance ---")
    
    # Test avec un ticker courant (Microsoft)
    success = test_fetch_single_stock_data(ticker="MSFT", days_ago=30)
    
    if not success:
        print("\n--- Tentative avec un autre ticker (Apple) si le premier a échoué ---")
        test_fetch_single_stock_data(ticker="AAPL", days_ago=30)
    
    print("\n--- Fin du test de connectivité ---")
