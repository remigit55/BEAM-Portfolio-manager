import streamlit as st
import pandas as pd

def afficher_parametres():
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    # Titre séparé de la sélection
    st.markdown("#### Devise de référence")

    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # Source de données
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données"):
        try:
            df = pd.read_csv(csv_url)
            st.session_state.df = df
            st.success("Données importées avec succès.")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
