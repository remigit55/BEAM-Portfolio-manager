import streamlit as st
import pandas as pd
import datetime
from taux_change import actualiser_taux_change # Nécessaire pour actualiser les taux

def afficher_parametres_globaux():
    """
    Gère la sélection de la devise de référence, les sources de données (importation de fichier
    et URL Google Sheets), et d'autres paramètres.
    """
    # --- 1. Choix de la Devise de Référence ---
    st.markdown("#### Devise de Référence")
    
    # Stocker la devise précédente pour détecter un changement
    previous_devise = st.session_state.get("devise_cible", "EUR")

    # Sélection de la devise avec la liste complète
    available_currencies = ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"]
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence pour l'affichage des valeurs du portefeuille et des taux de change.",
        available_currencies,
        index=available_currencies.index(st.session_state.get("devise_cible", "EUR")),
        key="devise_selector_settings" # Clé unique pour le selectbox
    )

    # Si la devise a changé, actualiser les taux
    if st.session_state.devise_cible != previous_devise:
        # On force la mise à jour des taux au prochain rerun
        st.session_state.last_update_time_fx = datetime.datetime.min
        st.success(f"Devise de référence définie sur **{st.session_state.devise_cible}**. Les taux de change seront mis à jour au prochain rechargement.")
        st.rerun() # Recharger l'application pour que la nouvelle devise soit prise en compte partout

    st.markdown("---")

    # --- 2. Sources de Données du Portefeuille ---
    st.markdown("#### Sources de Données et Importation")

    # Section 2.1: Importation de Fichier Local
    st.markdown("##### 📥 Importer un fichier CSV ou Excel")
    uploaded_file = st.file_uploader("Choisissez un fichier", type=["csv", "xlsx"], key="file_uploader_settings")
    if uploaded_file is not None:
        if "uploaded_file_id" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
            try:
                with st.spinner("Chargement du fichier..."):
                    if uploaded_file.name.endswith('.csv'):
                        df_uploaded = pd.read_csv(uploaded_file)
                    elif uploaded_file.name.endswith('.xlsx'):
                        df_uploaded = pd.read_excel(uploaded_file)
                    
                    st.session_state.df = df_uploaded
                    st.session_state.uploaded_file_id = uploaded_file.file_id # Suivre le fichier unique
                    st.session_state.url_data_loaded = False # Marquer que les données ne viennent plus de l'URL
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
        
    # Section 2.2: Chargement depuis Google Sheets URL
    st.markdown("##### 🔗 Charger depuis Google Sheets (URL)")
    csv_url = "https://docs.google.com/sheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"L'application charge les données du portefeuille depuis cette source par défaut : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données depuis Google Sheets URL", key="refresh_portfolio_button_url"): # Clé unique
        try:
            with st.spinner("Chargement des données du portefeuille depuis Google Sheets..."):
                df_url = pd.read_csv(csv_url)
                st.session_state.df = df_url
                # Utiliser un ID unique pour le chargement URL pour s'assurer que c'est bien considéré comme "nouveau"
                st.session_state.uploaded_file_id = "url_source_" + str(datetime.datetime.now())
                st.session_state.url_data_loaded = True # Marquer que les données proviennent de l'URL
                st.success("Données du portefeuille importées avec succès depuis l'URL.")
            
            # Après le rafraîchissement des données, on force la mise à jour des taux de change
            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'import des données du portefeuille depuis l'URL : {e}")

    st.markdown("---")

    # --- 3. Autres Réglages ---
    st.markdown("#### Autres Réglages")
    st.markdown("Cette section peut contenir d'autres options de configuration à l'avenir.")
    # Ajoutez ici d'autres options de paramètres si nécessaire
