# parametres.py

import streamlit as st
import pandas as pd
import datetime
from taux_change import actualiser_taux_change

def afficher_parametres_globaux():
    """
    Gère l'importation de fichiers, la sélection de la devise de référence,
    et le rafraîchissement des données du portefeuille.
    """
    st.markdown("#### Importation de Données")
    uploaded_file = st.file_uploader("📥 Choisissez un fichier CSV ou Excel", type=["csv", "xlsx"], key="file_uploader_settings")
    if uploaded_file is not None:
        if "uploaded_file_id" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
            try:
                if uploaded_file.name.endswith('.csv'):
                    df_uploaded = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith('.xlsx'):
                    df_uploaded = pd.read_excel(uploaded_file)
                
                st.session_state.df = df_uploaded
                st.session_state.uploaded_file_id = uploaded_file.file_id
                st.success("Fichier importé avec succès !")
                
                st.session_state.sort_column = None
                st.session_state.sort_direction = "asc"
                st.session_state.ticker_names_cache = {}
                st.session_state.last_update_time_fx = datetime.datetime.min # Forcer la mise à jour des taux
                
                st.cache_data.clear()
                st.cache_resource.clear()

                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None
        # Removed else: st.info("Fichier déjà chargé.")
    # Removed elif st.session_state.df is None: st.info("Veuillez importer un fichier...")

    st.markdown("---")
    st.markdown("#### Devise de Référence")
    
    previous_devise = st.session_state.get("devise_cible", "EUR")

    available_currencies = ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"]
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence pour l'affichage",
        available_currencies,
        index=available_currencies.index(st.session_state.get("devise_cible", "EUR")),
        key="devise_selector_settings"
    )

    if st.session_state.devise_cible != previous_devise:
        st.session_state.last_update_time_fx = datetime.datetime.min
        st.success(f"Devise de référence définie sur {st.session_state.devise_cible}. Les taux de change seront mis à jour.")
        st.rerun()

    st.markdown("---")
    st.markdown("#### Source des données du portefeuille (URL)")

    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"L'application peut aussi charger des données depuis cette source : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données du portefeuille depuis URL", key="refresh_portfolio_button_url"):
        try:
            with st.spinner("Chargement des données du portefeuille depuis Google Sheets..."):
                df = pd.read_csv(csv_url)
                st.session_state.df = df
                st.session_state.uploaded_file_id = "url_source_" + str(datetime.datetime.now()) 
                st.success("Données du portefeuille importées avec succès depuis l'URL.")
            
            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'import des données du portefeuille depuis l'URL : {e}")

    st.markdown("---")
    st.markdown("#### Autres réglages (à venir)")
    # Removed st.info("Cette section peut contenir...")
