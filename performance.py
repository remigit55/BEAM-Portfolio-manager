# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# Import the historical data manager
from historical_data_manager import load_historical_data

def display_performance_history():
    """
    Displays the portfolio's historical performance with a date filter.
    """
    st.header("📊 Historique des Performances du Portefeuille")
    st.subheader("Historique des Totaux Quotidiens")

    df_history = load_historical_data()

    if df_history.empty:
        st.info("Aucune donnée historique de performance disponible pour le moment. Chargez un portefeuille pour commencer à enregistrer l'historique.")
        return

    # Date range filter
    today = datetime.now().date()
    # Default end date is today, default start date is 30 days ago
    default_start_date = df_history["Date"].min().date() if not df_history.empty else today - timedelta(days=30)
    default_end_date = df_history["Date"].max().date() if not df_history.empty else today

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input(
            "Date de début", 
            value=default_start_date,
            min_value=df_history["Date"].min().date(),
            max_value=today
        )
    with col_end:
        end_date = st.date_input(
            "Date de fin", 
            value=default_end_date,
            min_value=df_history["Date"].min().date(),
            max_value=today
        )

    # Ensure start_date is not after end_date
    if start_date > end_date:
        st.error("La date de début ne peut pas être postérieure à la date de fin.")
        return

    # Filter data based on selected date range
    filtered_df = df_history[(df_history["Date"].dt.date >= start_date) & (df_history["Date"].dt.date <= end_date)].copy()
    
    if filtered_df.empty:
        st.warning("Aucune donnée disponible pour la plage de dates sélectionnée.")
        return

    # Calculate Daily Gain/Loss
    filtered_df["Gain/Perte Absolu"] = filtered_df["Valeur Actuelle"] - filtered_df["Valeur Acquisition"]
    
    # Handle division by zero for percentage calculation
    filtered_df["Gain/Perte (%)"] = filtered_df.apply(
        lambda row: (row["Gain/Perte Absolu"] / row["Valeur Acquisition"]) * 100 if row["Valeur Acquisition"] != 0 else 0,
        axis=1
    )

    # Display data in a table
    st.subheader("Données Historiques")
    # Get the currency for formatting from the first row of the filtered data
    display_currency = filtered_df['Devise'].iloc[0] if not filtered_df.empty else 'EUR'

    st.dataframe(filtered_df.set_index("Date").style.format({
        "Valeur Acquisition": lambda x: f"{x:,.2f} {display_currency}",
        "Valeur Actuelle": lambda x: f"{x:,.2f} {display_currency}",
        "Valeur H52": lambda x: f"{x:,.2f} {display_currency}",
        "Valeur LT": lambda x: f"{x:,.2f} {display_currency}",
        "Gain/Perte Absolu": lambda x: f"{x:,.2f} {display_currency}",
        "Gain/Perte (%)": "{:,.2f} %".format
    }), use_container_width=True)

    # Display charts
    st.subheader("Tendances des Valeurs du Portefeuille")

    # Long-form data for Plotly
    df_melted = filtered_df.melt(
        id_vars=["Date", "Devise"], 
        value_vars=["Valeur Acquisition", "Valeur Actuelle", "Valeur H52", "Valeur LT"],
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
    fig_values.update_layout(hovermode="x unified") # Shows all values for a given date on hover
    st.plotly_chart(fig_values, use_container_width=True)

    st.subheader("Tendance du Gain/Perte")
    fig_gain_loss = px.line(
        filtered_df,
        x="Date",
        y="Gain/Perte Absolu",
        title="Évolution du Gain/Perte Absolu Quotidien",
        labels={"Gain/Perte Absolu": f"Gain/Perte Absolu ({display_currency})", "Date": "Date"}
    )
    fig_gain_loss.update_layout(hovermode="x unified")
    st.plotly_chart(fig_gain_loss, use_container_width=True)

    fig_gain_loss_percent = px.line(
        filtered_df,
        x="Date",
        y="Gain/Perte (%)",
        title="Évolution du Gain/Perte Quotidien (%)",
        labels={"Gain/Perte (%)": "Gain/Perte (%)", "Date": "Date"}
    )
    fig_gain_loss_percent.update_layout(hovermode="x unified")
    st.plotly_chart(fig_gain_loss_percent, use_container_width=True)
