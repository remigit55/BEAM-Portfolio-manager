import streamlit as st
import pandas as pd
import datetime

def afficher_parametres_globaux(load_or_reload_portfolio):
    """
    Affiche l'interface des paramètres globaux pour gérer le portefeuille, la devise cible,
    la volatilité cible et les allocations cibles.
    """
    st.write("DEBUG: Entering afficher_parametres_globaux")
    st.write("DEBUG: load_or_reload_portfolio type:", type(load_or_reload_portfolio))
    st.write("DEBUG: Session state keys:", list(st.session_state.keys()))
    st.write("DEBUG: Session state values:", {k: type(v).__name__ for k, v in st.session_state.items()})
    st.write("DEBUG: Full session state:", {k: str(v)[:100] + "..." if len(str(v)) > 100 else str(v) for k, v in st.session_state.items()})
    st.header("Paramètres Globaux")

    # Initialize missing widget keys
    if 'portfolio_file' not in st.session_state:
        st.session_state.portfolio_file = None
    if 'source_type' not in st.session_state:
        st.session_state.source_type = "Fichier Excel/CSV"
    if 'google_sheets_url_input' not in st.session_state:
        st.session_state.google_sheets_url_input = ""
    if 'devise_cible_select' not in st.session_state:
        st.session_state.devise_cible_select = "EUR"
    if 'target_volatility_input' not in st.session_state:
        st.session_state.target_volatility_input = 15.0
    if 'save_allocations' not in st.session_state:
        st.session_state.save_allocations = False

    # Section pour charger le portefeuille
    st.subheader("Chargement du portefeuille")
    source_type = st.radio("Source des données du portefeuille", ["Fichier Excel/CSV", "Google Sheets"], key="source_type")
    st.write("DEBUG: Selected source_type:", source_type, "type:", type(source_type))

    if source_type == "Fichier Excel/CSV":
        uploaded_file = st.file_uploader("Choisir un fichier Excel ou CSV", type=["csv", "xlsx"], key="portfolio_file")
        st.write("DEBUG: uploaded_file:", uploaded_file, "type:", type(uploaded_file))
        if uploaded_file is not None:
            try:
                st.write("DEBUG: Calling load_or_reload_portfolio with source_type='fichier', uploaded_file=", getattr(uploaded_file, 'name', 'Unknown'))
                load_or_reload_portfolio(source_type="fichier", uploaded_file=uploaded_file)
            except Exception as e:
                st.error(f"Erreur lors du chargement du fichier: {e}")
                st.write("DEBUG: Exception in load_or_reload_portfolio (fichier):", str(e))
        else:
            st.info("Veuillez charger un fichier Excel ou CSV.")
            st.write("DEBUG: No file uploaded, skipping load_or_reload_portfolio")

    else:  # Google Sheets
        google_sheets_url = st.text_input(
            "URL de Google Sheets",
            value=st.session_state.get("google_sheets_url", ""),
            key="google_sheets_url_input"
        )
        st.write("DEBUG: google_sheets_url:", google_sheets_url, "type:", type(google_sheets_url))
        if google_sheets_url and isinstance(google_sheets_url, str) and google_sheets_url.strip() and google_sheets_url != st.session_state.get("google_sheets_url", ""):
            try:
                st.write("DEBUG: Calling load_or_reload_portfolio with source_type='google_sheets', google_sheets_url=", google_sheets_url)
                st.session_state.google_sheets_url = google_sheets_url
                load_or_reload_portfolio(source_type="google_sheets", google_sheets_url=google_sheets_url)
            except Exception as e:
                st.error(f"Erreur lors du chargement depuis Google Sheets: {e}")
                st.write("DEBUG: Exception in load_or_reload_portfolio (google_sheets):", str(e))
        else:
            st.info("Veuillez fournir une URL Google Sheets valide.")
            st.write("DEBUG: No valid Google Sheets URL provided or unchanged, skipping load_or_reload_portfolio")

    # Section pour la devise cible
    st.subheader("Devise cible")
    devise_options = ["EUR", "USD", "CAD", "GBP", "CHF", "JPY"]
    current_devise = st.session_state.get("devise_cible", "EUR")
    st.write("DEBUG: Current devise_cible:", current_devise, "type:", type(current_devise))
    devise_cible = st.selectbox(
        "Sélectionner la devise cible",
        options=devise_options,
        index=devise_options.index(current_devise) if current_devise in devise_options else 0,
        key="devise_cible_select"
    )
    if devise_cible != current_devise:
        st.write("DEBUG: Devise cible changed to:", devise_cible)
        st.session_state.devise_cible = devise_cible
        st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
        # st.rerun()  # Commented out to avoid rerun loops during debugging
        st.write("DEBUG: Devise cible updated, st.rerun() skipped for debugging")

    # Section pour la volatilité cible
    st.subheader("Volatilité cible")
    current_volatility = st.session_state.get("target_volatility", 0.15)
    st.write("DEBUG: Current target_volatility:", current_volatility, "type:", type(current_volatility))
    target_volatility = st.number_input(
        "Volatilité cible (en %)",
        min_value=0.0,
        max_value=100.0,
        value=float(current_volatility * 100) if isinstance(current_volatility, (int, float)) else 15.0,
        step=0.1,
        key="target_volatility_input"
    )
    if target_volatility != current_volatility * 100:
        st.write("DEBUG: Target volatility changed to:", target_volatility)
        st.session_state.target_volatility = target_volatility / 100.0
        # st.rerun()  # Commented out to avoid rerun loops during debugging
        st.write("DEBUG: Target volatility updated, st.rerun() skipped for debugging")

    # Section pour les allocations cibles
    st.subheader("Allocations cibles par catégorie")
    if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty and 'Catégorie' in st.session_state.df.columns:
        categories = st.session_state.df['Catégorie'].dropna().astype(str).unique().tolist()
        st.write("DEBUG: Categories found in DataFrame:", categories)
    else:
        categories = []
        st.write("DEBUG: No valid categories found in DataFrame")

    target_allocations = st.session_state.target_allocations.copy() if isinstance(st.session_state.target_allocations, dict) else {}
    st.write("DEBUG: Current target_allocations:", target_allocations, "type:", type(target_allocations))

    for category in categories:
        if not isinstance(category, str):
            st.warning(f"Catégorie invalide: {category} (type: {type(category)}). Ignorée.")
            continue
        allocation = st.number_input(
            f"Allocation cible pour {category} (en %)",
            min_value=0.0,
            max_value=100.0,
            value=float(target_allocations.get(category, 0.0)),
            step=1.0,
            key=f"allocation_{category.replace(' ', '_').replace('/', '_')}"
        )
        target_allocations[category] = allocation

    if st.button("Enregistrer les allocations cibles", key="save_allocations"):
        total_allocation = sum(target_allocations.values())
        if abs(total_allocation - 100.0) > 0.01:
            st.error(f"Erreur: La somme des allocations ({total_allocation}%) doit être égale à 100%.")
            st.write("DEBUG: Invalid total allocation:", total_allocation)
        else:
            st.write("DEBUG: Saving target_allocations:", target_allocations)
            st.session_state.target_allocations = target_allocations
            st.success("Allocations cibles enregistrées avec succès.")

    # Afficher l'état actuel
    st.subheader("État actuel des paramètres")
    st.write(f"**Devise cible**: {st.session_state.devise_cible}")
    st.write(f"**Volatilité cible**: {st.session_state.target_volatility * 100:.1f}%")
    st.write("**Allocations cibles**:")
    if st.session_state.target_allocations:
        for cat, alloc in st.session_state.target_allocations.items():
            st.write(f"{cat}: {alloc:.1f}%")
    else:
        st.write("Aucune allocation cible définie.")
