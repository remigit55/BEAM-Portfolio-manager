import streamlit as st
import pandas as pd
from taux_change import actualiser_taux_change

def afficher_parametres():
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"

    st.markdown("#### Paramètres généraux")

    # Stocker la devise précédente pour détecter un changement
    previous_devise = st.session_state.devise_cible

    # Sélection de la devise
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence",
        ["USD", "EUR", "CAD", "CHF"],
        index=["USD", "EUR", "CAD", "CHF"].index(st.session_state.devise_cible)
    )

    # Si la devise a changé, actualiser les taux
    if st.session_state.devise_cible != previous_devise:
        if "df" in st.session_state and st.session_state.df is not None and "Devise" in st.session_state.df.columns:
            devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            with st.spinner("Mise à jour des taux de change pour la nouvelle devise..."):
                st.session_state.fx_rates = actualiser_taux_change(st.session_state.devise_cible, devises_uniques)
                st.success(f"Taux de change actualisés pour {st.session_state.devise_cible}.")
        else:
            st.warning("Aucun portefeuille chargé, impossible d'actualiser les taux.")

    # URL Google Sheets du portefeuille (CSV)
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"#### Source des données : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données du portefeuille"):
        try:
            with st.spinner("Chargement des données du portefeuille..."):
                df = pd.read_csv(csv_url)
                st.session_state.df = df
                st.success("Données importées avec succès.")
            # Actualiser les taux après le chargement du portefeuille
            if "Devise" in df.columns:
                devises_uniques = sorted(set(df["Devise"].dropna().unique()))
                with st.spinner("Mise à jour des taux de change..."):
                    st.session_state.fx_rates = actualiser_taux_change(st.session_state.devise_cible, devises_uniques)
                    if st.session_state.fx_rates:
                        st.success(f"Taux de change actualisés pour {st.session_state.devise_cible}.")
                    else:
                        st.warning("Impossible d'actualiser les taux de change.")
        except Exception as e:
            st.error(f"Erreur lors de l'import : {e}")
