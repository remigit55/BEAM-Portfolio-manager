# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Import the new modules
from portfolio_journal import load_portfolio_journal
from historical_performance_calculator import reconstruct_historical_performance
from utils import format_fr # Make sure utils.py contains this function

def display_performance_history():
    """
    Displays the portfolio's historical performance with a date filter,
    recalculating values using historical data.
    """
    st.subheader("Reconstruction des Totaux Quotidiens")

    # Load the portfolio journal
    portfolio_journal = load_portfolio_journal()

    if not portfolio_journal:
        st.info("Aucune donnée historique de portefeuille n'a été enregistrée. Chargez un portefeuille et utilisez l'application pour commencer à construire l'historique.")
        return

    # Determine min/max dates from the journal for the date picker
    min_journal_date = min(s['date'] for s in portfolio_journal)
    max_journal_date = max(s['date'] for s in portfolio_journal)
    
    today = datetime.now().date()
    
    # Default end date is today or last journal entry, default start date is 6 months ago or min journal date
    default_end_date = min(today, max_journal_date)
    default_start_date = max(min_journal_date, default_end_date - timedelta(days=180)) # Last 6 months

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Date de début", 
            value=default_start_date,
            min_value=min_journal_date,
            max_value=default_end_date # Can't start after end
        )
    with col_end:
        end_date = st.date_input(
            "Date de fin", 
            value=default_end_date,
            min_value=start_date, # Must be after start
            max_value=today
        )

    # Ensure start_date is not after end_date
    if start_date > end_date:
        st.error("La date de début ne peut pas être postérieure à la date de fin.")
        return

    target_currency = st.session_state.get("devise_cible", "EUR")

    with st.spinner("Reconstruction de l'historique des performances... Cela peut prendre un certain temps."):
        df_reconstructed = reconstruct_historical_performance(
            start_date, end_date, target_currency, portfolio_journal
        )

    if df_reconstructed.empty:
        st.warning("Aucune donnée disponible pour la plage de dates sélectionnée ou impossible de reconstruire l'historique.")
        return

    # Display data in a table
    st.subheader("Données Historiques Reconstruites")
    display_currency = df_reconstructed['Devise'].iloc[0] if not df_reconstructed.empty else 'EUR'

    st.dataframe(df_reconstructed.set_index("Date").style.format({
        "Valeur Acquisition": lambda x: f"{format_fr(x, 2)} {display_currency}",
        "Valeur Actuelle": lambda x: f"{format_fr(x, 2)} {display_currency}",
        "Gain/Perte Absolu": lambda x: f"{format_fr(x, 2)} {display_currency}",
        "Gain/Perte (%)": lambda x: f"{format_fr(x, 2)} %"
    }), use_container_width=True)

    # Display charts
    st.subheader("Tendances des Valeurs du Portefeuille")

    # Long-form data for Plotly
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
