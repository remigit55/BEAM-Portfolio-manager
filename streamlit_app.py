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
            
            # Sélection de la devise cible (dans la sidebar)
            devise_cible = st.sidebar.selectbox("💶 Devise de référence", options=["USD", "EUR", "CAD", "CHF"], index=1)
            st.sidebar.markdown(f"💡 Affichage consolidé en **{devise_cible}**")
            
            # Vérifie que la feuille FX est disponible
            if "Taux_FX" in onglets_disponibles:
                fx = pd.read_excel(xls, sheet_name="Taux_FX")
                
                # Crée un dictionnaire des taux FX par devise de cotation
                try:
                    fx_dict = dict(zip(fx["Devise"], fx[devise_cible]))
                    df["Taux FX"] = df["Devise"].map(fx_dict)
                    df["Valeur (devise cible)"] = df["Valeur"] * df["Taux FX"]
                    
                    # Optionnel : affichage clair des taux appliqués
                    st.markdown(f"📌 Taux de change appliqués vers **{devise_cible}** :")
                    st.dataframe(fx.set_index("Devise")[[devise_cible]], use_container_width=True)
                    
                except Exception as e:
                    st.error(f"Erreur lors de l'application des taux de change : {e}")
            else:
                st.warning("❗ La feuille 'Taux_FX' est manquante : conversion en devise cible non appliquée.")

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
