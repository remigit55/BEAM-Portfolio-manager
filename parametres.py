import streamlit as st
import pandas as pd
import datetime

def afficher_parametres_globaux(load_or_reload_portfolio):
    """
    Affiche l'interface des paramètres globaux pour gérer le portefeuille, la devise cible,
    la volatilité cible et les allocations cibles.
    """
    st.header("Paramètres Globaux")

    # Section pour charger le portefeuille
    st.subheader("Chargement du portefeuille")
    source_type = st.radio("Source des données du portefeuille", ["Fichier Excel/CSV", "Google Sheets"], key="source_type")

    if source_type == "Fichier Excel/CSV":
        # Use session state directly to avoid widget state assignment issues
        uploaded_file = st.file_uploader("Choisir un fichier Excel ou CSV", type=["csv", "xlsx"], key="portfolio_file_uploader") # Changed key
        
        # Check if a new file has been uploaded or if the file_uploader widget state has changed
        if uploaded_file is not None and (
            "uploaded_file_id" not in st.session_state or 
            st.session_state.uploaded_file_id != uploaded_file.file_id
        ):
            st.session_state.portfolio_file = uploaded_file
            st.session_state.uploaded_file_id = uploaded_file.file_id # Store the new file_id
            try:
                load_or_reload_portfolio(source_type="fichier", uploaded_file=uploaded_file)
            except Exception as e:
                st.error(f"Erreur lors du chargement du fichier: {e}")
        elif st.session_state.get("portfolio_file") is not None and st.session_state.get("uploaded_file_id") == getattr(st.session_state.portfolio_file, 'file_id', None):
            # If the same file is selected again, or on rerun, and it's already in state
            st.info(f"Fichier déjà chargé: {st.session_state.portfolio_file.name}")
        else:
            st.info("Veuillez charger un fichier Excel ou CSV.")

    else:  # Google Sheets
        google_sheets_url = st.text_input(
            "URL de Google Sheets (publiée au format CSV ou avec permissions adéquates)", # More descriptive text
            value=st.session_state.get("google_sheets_url", ""),
            key="google_sheets_url_input"
        )
        
        # Use a button for explicit refresh from URL
        if st.button("Charger/Recharger depuis Google Sheets", key="load_google_sheets_btn"):
            if google_sheets_url and isinstance(google_sheets_url, str) and google_sheets_url.strip():
                try:
                    st.session_state.google_sheets_url = google_sheets_url # Update session state URL
                    load_or_reload_portfolio(source_type="google_sheets", google_sheets_url=google_sheets_url)
                except Exception as e:
                    st.error(f"Erreur lors du chargement depuis Google Sheets: {e}")
            else:
                st.error("Veuillez fournir une URL Google Sheets valide.")
        
        # Display current URL if available
        if st.session_state.get("google_sheets_url"):
            st.info(f"URL de Google Sheet actuelle: [{st.session_state.google_sheets_url}]({st.session_state.google_sheets_url})")


    # Section pour la devise cible
    st.subheader("Devise cible")
    devise_options = ["EUR", "USD", "CAD", "GBP", "CHF", "JPY"]
    current_devise = st.session_state.get("devise_cible", "EUR")
    devise_cible = st.selectbox(
        "Sélectionner la devise cible pour l'affichage des valeurs et des calculs.",
        options=devise_options,
        index=devise_options.index(current_devise) if current_devise in devise_options else 0,
        key="devise_cible_select"
    )
    if devise_cible != current_devise:
        st.session_state.devise_cible = devise_cible
        st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc) # Force FX update
        st.success(f"Devise cible mise à jour en **{devise_cible}**. Les taux de change seront actualisés.")
        st.rerun() # Rerun to apply currency changes immediately

    # Section pour la volatilité cible
    st.subheader("Volatilité cible")
    current_volatility = st.session_state.get("target_volatility", 0.15)
    target_volatility_input_val = st.number_input( # Renamed for clarity
        "Volatilité cible (en %)",
        min_value=0.0,
        max_value=100.0,
        value=float(current_volatility * 100), # Display as percentage
        step=0.1,
        key="target_volatility_input"
    )
    # Only update if the value actually changed to avoid unnecessary reruns
    if abs((target_volatility_input_val / 100.0) - current_volatility) > 0.0001:
        st.session_state.target_volatility = target_volatility_input_val / 100.0
        st.success(f"Volatilité cible mise à jour à {target_volatility_input_val:.1f}%.")
        st.rerun()

    # Section pour les allocations cibles
    st.subheader("Allocations cibles par catégorie")
    
    # Get unique categories from the loaded DataFrame
    if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Catégorie' in st.session_state.df.columns:
        categories = st.session_state.df['Catégorie'].dropna().astype(str).unique().tolist()
    else:
        categories = []
        st.info("Chargez votre portefeuille pour définir les allocations par catégorie.")

    # Initialize target_allocations in session state if not already done
    if 'target_allocations' not in st.session_state or not isinstance(st.session_state.target_allocations, dict):
        st.session_state.target_allocations = {}

    target_allocations = st.session_state.target_allocations.copy()

    with st.form("form_objectifs_categories"):
        new_allocations = {}
        total_alloc_input = 0.0
        
        # Ensure that inputs are created for all categories present in the df
        for category in categories:
            if not isinstance(category, str):
                st.warning(f"Catégorie invalide trouvée: {category} (type: {type(category)}). Ignorée pour l'allocation cible.")
                continue
            
            # Get current value from session state, default to 0 if not set for this category
            current_value = target_allocations.get(category, 0.0) * 100 # Convert to percentage for display
            
            pct = st.number_input(
                f"{category}",
                min_value=0.0,
                max_value=100.0,
                value=float(current_value),
                step=0.1,
                key=f"input_{category.replace(' ', '_').replace('/', '_')}" # Ensure unique key
            )
            new_allocations[category] = pct / 100.0 # Store as decimal
            total_alloc_input += pct
        
        # Add any categories already in target_allocations but not in the current df categories
        for existing_cat in target_allocations.keys():
            if existing_cat not in categories:
                # If a category exists in target_allocations but not in current df, still display it
                current_value = target_allocations.get(existing_cat, 0.0) * 100
                pct = st.number_input(
                    f"{existing_cat} (ancienne catégorie)", # Indicate it's from previous data
                    min_value=0.0,
                    max_value=100.0,
                    value=float(current_value),
                    step=0.1,
                    key=f"input_old_{existing_cat.replace(' ', '_').replace('/', '_')}"
                )
                new_allocations[existing_cat] = pct / 100.0
                total_alloc_input += pct


        st.markdown(f"**Total alloué : {total_alloc_input:.2f}%**")

        submitted = st.form_submit_button("Enregistrer les objectifs", key="save_allocations_button")
        if submitted:
            if abs(total_alloc_input - 100.0) > 0.1: # Allow for slight floating point inaccuracies
                st.error("❌ La somme des allocations doit faire exactement 100 %. Vous avez actuellement {:.2f} %.".format(total_alloc_input))
            else:
                st.session_state.target_allocations = new_allocations
                st.success("✅ Objectifs mis à jour.")
                st.rerun() # Rerun to update calculations based on new allocations

    # Afficher l'état actuel
    st.subheader("État actuel des paramètres")
    st.write(f"**Devise cible**: {st.session_state.get('devise_cible', 'N/A')}")
    st.write(f"**Volatilité cible**: {st.session_state.get('target_volatility', 0.0) * 100:.1f}%")
    st.write("**Allocations cibles**:")
    if st.session_state.get('target_allocations'):
        for cat, alloc in st.session_state['target_allocations'].items():
            st.write(f"- {cat}: {alloc * 100:.1f}%")
    else:
        st.write("Aucune allocation cible définie.")
