import streamlit as st
import pandas as pd

def afficher_parametres():
    st.markdown("#### Paramètres généraux")

    # Sélecteur de devise (dans le corps principal)
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # URL source
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"

    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")

    # Bouton d'importation
    if st.button("Rafraîchir les données"):
        try:
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.success("Données importées avec succès.")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
