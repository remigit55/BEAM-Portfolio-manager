import streamlit as st
import pandas as pd
from forex_python.converter import CurrencyRates
import datetime

st.set_page_config(page_title="Portefeuille d'investissement", layout="wide")
st.title("BEAM Portfolio Manager")

uploaded_file = st.file_uploader("Importer le fichier Excel du portefeuille", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    onglets_disponibles = xls.sheet_names

    # Devise cible - toujours affichée dans la sidebar
    devise_cible = st.sidebar.selectbox("💶 Devise de référence", options=["USD", "EUR", "CAD", "CHF"], index=1)
    st.sidebar.markdown(f"Affichage consolidé en **{devise_cible}**")

    # Navigation entre les onglets
    menu = st.sidebar.radio(
        "Navigation",
        ["Portefeuille", "Performance", "OD Comptables", "Transactions M&A", "Taux de change"]
    )

    if menu == "Portefeuille":
        if "Portefeuille" in onglets_disponibles:
            df = pd.read_excel(xls, sheet_name="Portefeuille")

            # Récupération automatique des taux de change
            cr = CurrencyRates()
            fx_rates_utilisés = {}

            def get_fx_rate(devise_origine, devise_cible):
                if devise_origine == devise_cible:
                    return 1.0
                try:
                    rate = cr.get_rate(devise_origine, devise_cible)
                    fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = rate
                    return rate
                except:
                    fx_rates_utilisés[f"{devise_origine} → {devise_cible}"] = "Erreur"
                    return None

            # Application des taux de change
            df["Taux FX"] = df["Devise"].apply(lambda d: get_fx_rate(d, devise_cible))
            df["Valeur (devise cible)"] = df["Valeur"] * df["Taux FX"]

            # Affichage
            st.subheader("Portefeuille converti en devise cible")
            st.dataframe(df, use_container_width=True)

            st.markdown(f"**Taux de change utilisés** (vers {devise_cible}) - *{datetime.date.today()}*")
            st.dataframe(pd.DataFrame(list(fx_rates_utilisés.items()), columns=["Conversion", "Taux"]), use_container_width=True)

    elif menu == "Performance":
        if "Performance" in onglets_disponibles:
            perf = pd.read_excel(xls, sheet_name="Performance")
            st.subheader("Performance historique")
            st.line_chart(perf.set_index(perf.columns[0]))

    elif menu == "OD Comptables":
        if "OD_Comptables" in onglets_disponibles:
            od = pd.read_excel(xls, sheet_name="OD_Comptables")
            st.subheader("OD Comptables")
            st.dataframe(od, use_container_width=True)

    elif menu == "Transactions M&A":
        if "Transactions_M&A" in onglets_disponibles:
            ma = pd.read_excel(xls, sheet_name="Transactions_M&A")
            st.subheader("Transactions minières")
            st.dataframe(ma, use_container_width=True)

    elif menu == "Taux de change":
        if "Taux_FX" in onglets_disponibles:
            fx = pd.read_excel(xls, sheet_name="Taux_FX")
            st.subheader("Taux de change (manuel)")
            st.dataframe(fx, use_container_width=True)

else:
    st.info("Veuillez importer un fichier Excel (.xlsx) structuré avec les bons onglets.")

