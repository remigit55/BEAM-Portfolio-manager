# parametres.py

import streamlit as st
import pandas as pd
import datetime # Nécessaire pour datetime.datetime.min
from taux_change import actualiser_taux_change # Nécessaire pour actualiser les taux

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
                
                # Réinitialiser le tri et les caches de données liées au portefeuille après un nouvel import
                st.session_state.sort_column = None
                st.session_state.sort_direction = "asc"
                st.session_state.ticker_names_cache = {}
                st.session_state.last_update_time_fx = datetime.datetime.min # Forcer la mise à jour des taux
                
                st.cache_data.clear() # Efface tous les caches de type cache_data
                st.cache_resource.clear() # Efface tous les caches de type cache_resource

                st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None
        else:
            st.info("Fichier déjà chargé.")
    elif st.session_state.df is None:
        st.info("Veuillez importer un fichier pour charger votre portefeuille.")

    st.markdown("---")
    st.markdown("#### Devise de Référence")
    
    # Stocker la devise précédente pour détecter un changement
    previous_devise = st.session_state.get("devise_cible", "EUR")

    # Sélection de la devise avec la liste complète
    available_currencies = ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"]
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence pour l'affichage",
        available_currencies,
        index=available_currencies.index(st.session_state.get("devise_cible", "EUR")),
        key="devise_selector_settings" # Clé unique pour le selectbox
    )

    # Si la devise a changé, actualiser les taux
    if st.session_state.devise_cible != previous_devise:
        # On force la mise à jour des taux au prochain rerun
        st.session_state.last_update_time_fx = datetime.datetime.min
        st.success(f"Devise de référence définie sur {st.session_state.devise_cible}. Les taux de change seront mis à jour.")
        st.rerun() # Recharger l'application pour que la nouvelle devise soit prise en compte partout

    st.markdown("---")
    st.markdown("#### Source des données du portefeuille (URL)")

    # URL Google Sheets du portefeuille (CSV)
    csv_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"L'application peut aussi charger des données depuis cette source : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données du portefeuille depuis URL", key="refresh_portfolio_button_url"): # Clé unique
        try:
            with st.spinner("Chargement des données du portefeuille depuis Google Sheets..."):
                df = pd.read_csv(csv_url)
                st.session_state.df = df
                # Simuler un fichier téléchargé pour déclencher la logique de rafraîchissement globale
                st.session_state.uploaded_file_id = "url_source_" + str(datetime.datetime.now()) 
                st.success("Données du portefeuille importées avec succès depuis l'URL.")
            
            # Après le rafraîchissement des données, on force la mise à jour des taux de change
            # pour s'assurer que les nouvelles devises du portefeuille sont prises en compte.
            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'import des données du portefeuille depuis l'URL : {e}")

    st.markdown("---")
    st.markdown("#### Autres réglages (à venir)")
    st.info("Cette section peut contenir d'autres options de configuration à l'avenir.")
