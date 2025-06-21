# performance.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date

# Import the new modules
from portfolio_journal import load_portfolio_journal
from historical_performance_calculator import reconstruct_historical_performance
from utils import format_fr # Make sure utils.py contains this function

# NOUVEAUX IMPORTS NÉCESSAIRES POUR LE TEST GLDG
import yfinance as yf
from historical_data_fetcher import fetch_stock_history
import builtins

def display_performance_history():
    """
    Displays the portfolio's historical performance with a date filter,
    recalculating values using historical data, and includes a GLDG historical data test.
    """
    
    # Création des onglets dans la section Performance
    performance_tabs = st.tabs(["Performance Globale", "Test Historique GLDG"])

    with performance_tabs[0]: # Onglet Performance Globale
        st.subheader("Reconstruction des Totaux Quotidiens")

        # Load the portfolio journal
        portfolio_journal = load_portfolio_journal()

        if not portfolio_journal:
            st.info("Aucune donnée historique de portefeuille n'a été enregistrée. Chargez un portefeuille et utilisez l'application pour commencer à construire l'historique.")
            return

        # --- DÉBUT DE LA VÉRIFICATION AMÉLIORÉE DU JOURNAL ---
        # Filtre les snapshots potentiellement invalides ou vides
        valid_snapshots = [
            s for s in portfolio_journal 
            if 'portfolio_data' in s 
            and isinstance(s['portfolio_data'], pd.DataFrame) 
            and not s['portfolio_data'].empty
        ]
        
        if not valid_snapshots:
            st.warning("Le journal historique du portefeuille est vide ou ne contient pas de snapshots valides. Veuillez vous assurer que le portefeuille est correctement enregistré via la page Portefeuille (ou via l'import de données).")
            return

        # Utilise uniquement les snapshots valides pour la suite
        portfolio_journal = valid_snapshots
        # --- FIN DE LA VÉRIFICATION AMÉLIORÉE ---

        # 👉 Ajout temporaire d’un ancien snapshot si un seul est disponible
        if len(portfolio_journal) == 1:
            ancien_snapshot = portfolio_journal[0].copy()
            ancien_snapshot["date"] = portfolio_journal[0]["date"] - timedelta(days=7)
            # S'assurer que portfolio_data est aussi une copie profonde pour éviter les références
            ancien_snapshot["portfolio_data"] = ancien_snapshot["portfolio_data"].copy() 
            portfolio_journal.insert(0, ancien_snapshot)
        
        # Ensuite on peut calculer les bornes normalement
        min_journal_date = min(s['date'] for s in portfolio_journal)
        max_journal_date = (datetime.now() - timedelta(days=1)).date()

        
        today = datetime.now().date()
        
        # Default end date is today or last journal date if today is too far in the future
        default_end_date = min(max_journal_date, today)

        date_range = st.date_input(
            "Sélectionnez la période d'analyse de la performance :",
            value=(min_journal_date, default_end_date),
            min_value=min_journal_date,
            max_value=today,
            key="performance_date_range"
        )

        if len(date_range) == 2:
            start_date_perf, end_date_perf = date_range[0], date_range[1]
        else:
            st.warning("Veuillez sélectionner une période valide (date de début et de fin).")
            return

        st.info(f"Calcul de la performance historique du {start_date_perf.strftime('%Y-%m-%d')} au {end_date_perf.strftime('%Y-%m-%d')}...")

        # CONVERSION DES DATES AU FORMAT DATETIME.DATETIME POUR LA COMPATIBILITÉ
        start_datetime_perf = datetime.combine(start_date_perf, datetime.min.time())
        end_datetime_perf = datetime.combine(end_date_perf, datetime.max.time())

        with st.spinner("Reconstruction de la performance historique (cela peut prendre un certain temps si l'historique est long)..."):
            df_reconstructed = reconstruct_historical_performance(
                start_datetime_perf,
                end_datetime_perf,
                st.session_state.get("devise_cible", "EUR")
            )

        if df_reconstructed.empty:
            st.warning("Aucune donnée reconstruite pour la période sélectionnée. Assurez-vous d'avoir des snapshots de portefeuille et que les cours des tickers/taux de change sont disponibles.")
            return

        display_currency = st.session_state.get("devise_cible", "EUR")

        # Display reconstructed data
        st.subheader("Historique des Valeurs du Portefeuille")
        st.dataframe(df_reconstructed.style.format({
            "Valeur Acquisition": format_fr,
            "Valeur Actuelle": format_fr,
            "Gain/Perte Absolu": format_fr,
            "Gain/Perte (%)": lambda x: f"{format_fr(x, 2)} %"
        }), use_container_width=True)

        # Display charts
        st.subheader("Tendances des Valeurs du Portefeuille")

        df_melted = df_reconstructed.melt(
            id_vars=["Date", "Devise"], 
            value_vars=["Valeur Acquisition", "Valeur Actuelle"],
            var_name="Type de Valeur", 
            value_name="Montant"
        )

        fig_values = px.line(
            df_melted,
            x="Date",
            y="Montant",
            color="Type de Valeur",
            title="Évolution des Valeurs du Portefeuille",
            labels={"Montant": f"Montant ({display_currency})", "Date": "Date"}
        )
        fig_values.update_layout(hovermode="x unified")
        st.plotly_chart(fig_values, use_container_width=True)

        st.subheader("Tendance du Gain/Perte")
        fig_gain_loss = px.line(
            df_reconstructed,
            x="Date",
            y="Gain/Perte Absolu",
            title="Évolution du Gain/Perte Absolu Quotidien",
            labels={"Gain/Perte Absolu": f"Gain/Perte Absolu ({display_currency})", "Date": "Date"}
        )
        fig_gain_loss.update_layout(hovermode="x unified")
        st.plotly_chart(fig_gain_loss, use_container_width=True)

        fig_gain_loss_percent = px.line(
            df_reconstructed,
            x="Date",
            y="Gain/Perte (%)",
            title="Évolution du Gain/Perte Quotidien (%)",
            labels={"Gain/Perte (%)": "Gain/Perte (%)", "Date": "Date"}
        )
        fig_gain_loss_percent.update_layout(hovermode="x unified")
        st.plotly_chart(fig_gain_loss_percent, use_container_width=True)


    with performance_tabs[1]: # Onglet : Test Historique GLDG
        st.subheader("📊 Test de Récupération des Données Historiques GLDG")
        st.write("Cet onglet sert à vérifier spécifiquement la récupération des données historiques de GLDG.")

        today = datetime.now()
        default_start_date_gldg = today - timedelta(days=30)
        
        start_date_gldg = st.date_input(
            "Date de début (GLDG)",
            value=default_start_date_gldg,
            min_value=datetime(1990, 1, 1).date(),
            max_value=today.date(),
            key="start_date_gldg_test"
        )
        end_date_gldg = st.date_input(
            "Date de fin (GLDG)",
            value=today.date(),
            min_value=datetime(1990, 1, 1).date(),
            max_value=today.date(),
            key="end_date_gldg_test"
        )

        if st.button("Récupérer les données GLDG"):
            st.info(f"Tentative de récupération des données pour GLDG du {start_date_gldg.strftime('%Y-%m-%d')} au {end_date_gldg.strftime('%Y-%m-%d')}...")
            
            try:
                start_dt_gldg = datetime.combine(start_date_gldg, datetime.min.time())
                end_dt_gldg = datetime.combine(end_date_gldg, datetime.max.time())
                
                historical_prices = fetch_stock_history("GLDG", start_dt_gldg, end_dt_gldg)

                if not historical_prices.empty:
                    st.success(f"✅ Données récupérées avec succès pour GLDG!")
                    st.write("Aperçu des données (5 premières lignes) :")
                    st.dataframe(historical_prices.head(), use_container_width=True)
                    st.write("...")
                    st.write("Aperçu des données (5 dernières lignes) :")
                    st.dataframe(historical_prices.tail(), use_container_width=True)
                    st.write(f"Nombre total de jours : **{len(historical_prices)}**")
                    st.write(f"Type de l'objet retourné : `{builtins.str(type(historical_prices))}`")
                    st.write(f"L'index est un `DatetimeIndex` : `{builtins.isinstance(historical_prices.index, pd.DatetimeIndex)}`")

                    st.subheader("Graphique des cours de clôture GLDG")
                    st.line_chart(historical_prices)

                else:
                    st.warning(f"❌ Aucune donnée récupérée pour GLDG sur la période spécifiée. "
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
