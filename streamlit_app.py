import streamlit as st
import pandas as pd

st.set_page_config(page_title="Portefeuille d'investissement", layout="wide")
st.title("BEAM Portfolio Manager")

uploaded_file = st.file_uploader("Importer le fichier Excel du portefeuille", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    onglets_disponibles = xls.sheet_names

    menu = st.sidebar.radio(
        "Navigation",
        ["Portefeuille", "Performance", "OD Comptables", "Transactions M&A", "Taux de change"]
    )

    if menu == "Portefeuille":
        if "Portefeuille" in onglets_disponibles:
            df = pd.read_excel(xls, sheet_name="Portefeuille")
            st.subheader("Positions actuelles")
            st.dataframe(df, use_container_width=True)

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
            st.subheader("💱 Taux de change")
            st.dataframe(fx, use_container_width=True)

else:
    st.info("Veuillez importer un fichier Excel (.xlsx) structuré avec les bons onglets.")
