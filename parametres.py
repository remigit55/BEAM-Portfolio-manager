import streamlit as st
import pandas as pd
import datetime # Peut être nécessaire si d'autres parties de parametres.py l'utilisent

def afficher_parametres_globaux(load_or_reload_portfolio):
    """
    Affiche l'interface des paramètres globaux pour gérer le portefeuille, la devise cible,
    la volatilité cible et les allocations cibles.
    """
    st.header("Paramètres Globaux")

    # Section pour charger le portefeuille
    st.subheader("Chargement du portefeuille")
    source_type = st.radio("Source des données du portefeuille", ["Fichier Excel/CSV", "Google Sheets"], key="source_type_radio") # Changé la clé pour éviter conflit si 'source_type' était ailleurs

    if source_type == "Fichier Excel/CSV":
        # Utilisez une clé unique et laissez Streamlit gérer l'état de l'uploader.
        # uploaded_file_object contiendra l'objet fichier ou None.
        uploaded_file_object = st.file_uploader(
            "Choisir un fichier Excel ou CSV",
            type=["csv", "xlsx"],
            key="portfolio_file_uploader_key" # Clé unique pour le file_uploader
        )

        if uploaded_file_object is not None:
            # Si un fichier est uploadé, appelez la fonction de chargement
            load_or_reload_portfolio("fichier", uploaded_file=uploaded_file_object)
            st.success("Fichier portefeuille chargé avec succès !")
            # st.rerun() # Un rerun est souvent automatique après le chargement, ou géré par le script principal

    elif source_type == "Google Sheets":
        # Utiliser st.session_state.get pour une initialisation sûre
        google_sheets_url_input = st.text_input(
            "URL de votre Google Sheet (publiée au format CSV ou avec permissions adéquates)",
            value=st.session_state.get("google_sheets_url_from_input", ""), # Clé mise à jour
            key="google_sheets_url_input_widget_key" # Clé unique pour le widget
        )

        if st.button("Charger/Recharger depuis Google Sheets", key="load_google_sheets_button"):
            if google_sheets_url_input:
                # Mettre à jour la session_state pour que la valeur persiste
                st.session_state.google_sheets_url_from_input = google_sheets_url_input
                load_or_reload_portfolio("google_sheets", google_sheets_url=google_sheets_url_input)
                st.success("Portefeuille chargé depuis Google Sheets !")
                # st.rerun() # Un rerun est souvent automatique après le chargement, ou géré par le script principal
            else:
                st.warning("Veuillez entrer une URL Google Sheets.")

    # --- Paramètres de devise ---
    st.subheader("Paramètres de devise")
    devise_options = ["USD", "EUR", "GBP", "JPY", "CAD", "CHF", "AUD"] # Exemple
    try:
        current_index = devise_options.index(st.session_state.get("devise_cible", "USD")) # Utiliser .get pour la robustesse
    except ValueError:
        current_index = 0

    st.session_state.devise_cible = st.selectbox(
        "Choisissez votre devise d'affichage cible :",
        options=devise_options,
        index=current_index,
        key="devise_cible_selectbox" # Clé unique pour le widget
    )

    # --- Paramètres de volatilité cible ---
    st.subheader("Paramètres de Volatilité")
    st.session_state.target_volatility = st.number_input(
        "Volatilité cible annuelle du portefeuille (en %)",
        min_value=0.0,
        max_value=100.0,
        value=st.session_state.get("target_volatility", 15.0), # Utiliser .get pour la robustesse
        step=0.5,
        format="%.1f",
        key="target_volatility_input_widget_key" # Clé unique pour le widget
    ) / 100.0 # Convertir en décimal

    # --- Paramètres d'allocations cibles ---
    st.subheader("Allocations cibles par catégorie")
    st.info("Veuillez définir les allocations cibles pour chaque catégorie d'actif. La somme doit être égale à 100%.")

    # Initialiser target_allocations si elle n'existe pas ou est vide
    if "target_allocations" not in st.session_state or not st.session_state.target_allocations:
        st.session_state.target_allocations = {}
    
    # Simuler des catégories d'actifs pour les inputs, ou les récupérer du df_portfolio si disponible
    # Pour un exemple robuste, on prend des catégories fixes ou on les déduit de df_portfolio
    if not st.session_state.df.empty and 'Catégorie' in st.session_state.df.columns:
        categories = st.session_state.df['Catégorie'].unique().tolist()
    else:
        categories = ["Actions", "Obligations", "Immobilier", "Liquidités", "Autres"] # Catégories par défaut

    target_allocations = st.session_state.target_allocations.copy()
    for category in categories:
        # Assurez-vous que chaque widget a une clé unique
        allocation = st.number_input(
            f"Allocation cible pour {category} (en %)",
            min_value=0.0,
            max_value=100.0,
            value=float(target_allocations.get(category, 0.0)),
            step=1.0,
            key=f"allocation_{category.replace(' ', '_').replace('/', '_')}_input_key" # Clé unique
        )
        target_allocations[category] = allocation

    if st.button("Enregistrer les allocations cibles", key="save_allocations_button"): # Clé unique
        total_allocation = sum(target_allocations.values())
        if abs(total_allocation - 100.0) > 0.01:
            st.error(f"Erreur: La somme des allocations ({total_allocation}%) doit être égale à 100%.")
        else:
            st.session_state.target_allocations = target_allocations
            st.success("Allocations cibles enregistrées avec succès.")

    # Afficher l'état actuel des paramètres
    st.subheader("État actuel des paramètres")
    st.write(f"**Devise cible**: {st.session_state.get('devise_cible', 'N/A')}")
    st.write(f"**Volatilité cible**: {st.session_state.get('target_volatility', 0.0) * 100:.1f}%")
    st.write("**Allocations cibles**:")
    if st.session_state.get('target_allocations'):
        st.write(st.session_state.target_allocations)
    else:
        st.write("Aucune allocation cible définie.")
