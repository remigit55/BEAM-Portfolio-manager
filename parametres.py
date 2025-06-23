import streamlit as st
import pandas as pd
import datetime
from data_fetcher import fetch_fx_rates

def afficher_parametres_globaux():
    """
    Gère la sélection de la devise de référence, les sources de données (importation de fichier
    et URL Google Sheets), et d'autres paramètres.
    """
    # --- 1. Choix de la Devise de Référence ---
    st.markdown("#### Devise de Référence")

    previous_devise = st.session_state.get("devise_cible", "EUR")
    devise_changed = False

    available_currencies = ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"]
    st.session_state.devise_cible = st.selectbox(
        "Sélectionnez la devise de référence pour l'affichage des valeurs du portefeuille et des taux de change.",
        available_currencies,
        index=available_currencies.index(previous_devise),
        key="devise_selector_settings"
    )

    if st.session_state.devise_cible != previous_devise:
        with st.spinner(f"Mise à jour des taux de change pour {st.session_state.devise_cible}..."):
            st.session_state.fx_rates = fetch_fx_rates(st.session_state.devise_cible)
            st.session_state.last_update_time_fx = datetime.datetime.now()
            st.session_state.last_devise_cible_for_fx_update = st.session_state.devise_cible
        st.success(f"Devise de référence définie sur **{st.session_state.devise_cible}**. Taux de change mis à jour.")
        devise_changed = True

    st.markdown("---")

    # --- 2. Sources de Données du Portefeuille ---
    st.markdown("#### Sources de Données et Importation")
    st.markdown("##### Importer un fichier CSV ou Excel")
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
                    st.session_state.uploaded_file_id = uploaded_file.file_id
                    st.session_state.url_data_loaded = False
                    st.success("Fichier importé avec succès !")

                    st.session_state.sort_column = None
                    st.session_state.sort_direction = "asc"
                    st.session_state.ticker_names_cache = {}
                    st.session_state.last_update_time_fx = datetime.datetime.min

                    st.cache_data.clear()
                    st.cache_resource.clear()

                    st.rerun()
            except Exception as e:
                st.error(f"❌ Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None

    st.markdown("<br>", unsafe_allow_html=True) 
    st.markdown("##### Charger depuis Google Sheets (URL)")
    csv_url = "https://docs.google.com/sheets/d/e/2PACX-1vQiqdLmDURL-e4NP8FdSfk5A7kEhQV1Rt4zRBEL8pWu32TJ23nCFr43_rOjhqbAxg/pub?gid=1944300861&single=true&output=csv"
    st.markdown(f"L'application charge les données du portefeuille depuis cette source par défaut : [Google Sheets CSV]({csv_url})")

    if st.button("Rafraîchir les données depuis Google Sheets URL", key="refresh_portfolio_button_url"):
        try:
            with st.spinner("Chargement des données du portefeuille depuis Google Sheets..."):
                df_url = pd.read_csv(csv_url)
                st.session_state.df = df_url
                st.session_state.uploaded_file_id = "url_source_" + str(datetime.datetime.now())
                st.session_state.url_data_loaded = True
                st.success("Données du portefeuille importées avec succès depuis l'URL.")

            st.session_state.last_update_time_fx = datetime.datetime.min
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erreur lors de l'import des données du portefeuille depuis l'URL : {e}")

    st.markdown("---")

    # --- 3. Réglages des Objectifs de Répartition ---
    st.markdown("#### Objectifs de Répartition par Catégorie")

    with st.form("form_objectifs_catégories"):
        st.write("Définissez les objectifs de répartition par catégorie (% du portefeuille).")
        new_allocations = {}
        total_alloc_input = 0

        columns = st.columns(len(st.session_state["target_allocations"]))
        for i, (cat, val) in enumerate(st.session_state["target_allocations"].items()):
            with columns[i]:
                pct = st.number_input(f"{cat}", min_value=0.0, max_value=100.0, value=val * 100, step=0.1, key=f"input_{cat}")
                new_allocations[cat] = pct / 100
                total_alloc_input += pct

        st.markdown(f"**Total alloué : {total_alloc_input:.2f}%**")

        submitted = st.form_submit_button("Enregistrer les objectifs")
        if submitted:
            if abs(total_alloc_input - 100.0) > 0.1:
                st.error("❌ La somme des allocations doit faire exactement 100 %. Vous avez actuellement {:.2f} %.".format(total_alloc_input))
            else:
                st.session_state["target_allocations"] = new_allocations
                st.success("✅ Objectifs mis à jour.")
                st.rerun()

    st.markdown("---")

    # --- 4. Autres Réglages ---
    st.markdown("#### Autres Réglages")
    st.markdown("Cette section peut contenir d'autres options de configuration à l'avenir.")

    # --- 5. Relancer l'app si la devise a changé ---
    if devise_changed:
        st.session_state.force_refresh_calculs = True
