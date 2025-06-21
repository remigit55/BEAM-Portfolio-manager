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

st.subheader("🛠️ Outil de Test Yahoo Finance (temporaire)")
    st.write("Utilisez cet outil pour vérifier la connectivité de l'application à Yahoo Finance.")

    test_ticker = st.text_input("Entrez un symbole boursier pour le test (ex: MSFT, AAPL, GLDG)", value="GLDG")
    test_days_ago = st.slider("Nombre de jours d'historique à récupérer", 1, 365, 30)

    if st.button("Lancer le test de connexion Yahoo Finance"):
        import datetime as dt_test
        from datetime import timedelta as td_test
        
        start_date = dt_test.datetime.now() - td_test(days=test_days_ago)
        end_date = dt_test.datetime.now()

        st.info(f"Tentative de récupération des données pour **{test_ticker}** du **{start_date.strftime('%Y-%m-%d')}** au **{end_date.strftime('%Y-%m-%d')}**...")
        
        import builtins 

        try:
            # L'appel à yf.download est maintenant valide car yf est importé au début du fichier
            data = yf.download(test_ticker, 
                               start=start_date.strftime('%Y-%m-%d'), 
                               end=end_date.strftime('%Y-%m-%d'), 
                               progress=False)

            if not data.empty:
                st.success(f"✅ Données récupérées avec succès pour {test_ticker}!")
                st.write("Aperçu des données :")
                st.dataframe(data.head())
                st.write("...")
                st.dataframe(data.tail())
                st.write(f"Nombre total d'entrées : **{len(data)}**")
                st.write(f"Type de l'objet retourné : `{builtins.str(type(data))}`")
                st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(data.index, pd.DatetimeIndex)}`")

                st.subheader("Graphique des cours de clôture")
                st.line_chart(data['Close'])

            else:
                st.warning(f"❌ Aucune donnée récupérée pour {test_ticker} sur la période spécifiée. "
                           "Vérifiez le ticker ou la période, et votre connexion à Yahoo Finance.")
        except Exception as e:
            st.error(f"❌ Une erreur est survenue lors de la récupération des données : {builtins.str(e)}")
            if "str' object is not callable" in builtins.str(e):
                st.error("⚠️ **Confirmation :** L'erreur `str() object is not callable` persiste. Cela indique fortement "
                         "qu'une variable ou fonction nommée `str` est définie ailleurs dans votre code, "
                         "écrasant la fonction native de Python. **La recherche globale `str = ` est impérative.**")
            elif "No data found" in builtins.str(e) or "empty DataFrame" in builtins.str(e):
                 st.warning("Yahoo Finance n'a pas retourné de données. Le ticker est-il valide ? La période est-elle trop courte ou dans le futur ?")
            else:
                st.error(f"Détail de l'erreur : {builtins.str(e)}")

if __name__ == "__main__":
    test_gldg_data_fetch()
