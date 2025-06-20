# portfolio_display.py

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Importations nécessaires pour le calcul de l'élan (momentum)
import numpy as np
from scipy.stats import linregress


# --- Fonctions utilitaires ---

@st.cache_data(ttl=3600) # Cache pour 1 heure
def get_ticker_name(ticker_symbol):
    """Récupère le nom complet du ticker."""
    if ticker_symbol in st.session_state.ticker_names_cache:
        return st.session_state.ticker_names_cache[ticker_symbol]
    
    try:
        ticker_info = yf.Ticker(ticker_symbol).info
        name = ticker_info.get('longName') or ticker_info.get('shortName') or ticker_symbol
        st.session_state.ticker_names_cache[ticker_symbol] = name
        return name
    except Exception:
        st.session_state.ticker_names_cache[ticker_symbol] = ticker_symbol # En cas d'erreur, utilise le symbole
        return ticker_symbol

def get_exchange_rate(devise_source, devise_cible, fx_rates):
    """Récupère le taux de change ou retourne 1 si les devises sont identiques."""
    if devise_source == devise_cible:
        return 1.0
    
    taux = fx_rates.get(f"{devise_source}{devise_cible}", None)
    if taux is None:
        # Tenter le taux inverse si disponible (ex: USD/EUR au lieu de EUR/USD)
        taux_inverse = fx_rates.get(f"{devise_cible}{devise_source}", None)
        if taux_inverse:
            return 1 / taux_inverse
        st.warning(f"Taux de change {devise_source}/{devise_cible} non trouvé. Utilisation de 1:1 pour {devise_source}.")
        return 1.0 # Fallback si le taux n'est pas trouvé
    return taux


@st.cache_data(ttl=60) # Cache pour 1 minute
def get_historical_price(ticker, date):
    """Récupère le prix de clôture d'un ticker à une date donnée."""
    try:
        # Ajuster la date pour s'assurer que nous obtenons un prix valide (jour de bourse)
        data = yf.download(ticker, start=date, end=date + timedelta(days=5), progress=False, show_errors=False)
        if not data.empty:
            return data['Close'].iloc[0]
        
        # Si pas de données à la date exacte, essayer le jour ouvré précédent
        for i in range(1, 5): # Essayer jusqu'à 4 jours avant
            prev_date = date - timedelta(days=i)
            data = yf.download(ticker, start=prev_date, end=prev_date + timedelta(days=1), progress=False, show_errors=False)
            if not data.empty:
                return data['Close'].iloc[0]

        return None # Aucun prix trouvé dans la période
    except Exception:
        return None

# --- Fonctions d'affichage principales ---

def afficher_portefeuille():
    """Affiche le portefeuille détaillé."""
    df = st.session_state.df.copy() # Travailler sur une copie

    # S'assurer que les colonnes nécessaires existent
    required_columns = ["Quantité", "Acquisition", "Devise", "Ticker"]
    for col in required_columns:
        if col not in df.columns:
            st.error(f"La colonne '{col}' est manquante dans votre fichier. Veuillez vérifier le format.")
            return pd.DataFrame(), 0, 0, 0, 0 # Retourne des valeurs par défaut pour éviter des erreurs

    # Convertir 'Acquisition' en numérique
    df['Acquisition'] = pd.to_numeric(df['Acquisition'], errors='coerce')

    # Initialisation des colonnes de prix actuels
    df['Prix Actuel (Original)'] = None
    df['Prix Actuel (Cible)'] = None

    # Récupérer les prix actuels des tickers
    tickers_to_fetch = df['Ticker'].dropna().unique()
    current_prices = {}

    for ticker in tickers_to_fetch:
        try:
            # Récupérer les données de YFinance pour le dernier prix
            ticker_data = yf.Ticker(ticker)
            hist = ticker_data.history(period="1d", interval="1d")
            if not hist.empty:
                current_price = hist['Close'].iloc[0]
                current_prices[ticker] = current_price
            else:
                current_prices[ticker] = None # Pas de prix trouvé
        except Exception:
            current_prices[ticker] = None # En cas d'erreur de récupération

    # Appliquer les prix actuels au DataFrame
    df['Prix Actuel (Original)'] = df['Ticker'].map(current_prices)

    # Convertir les prix dans la devise cible
    df['Prix Actuel (Cible)'] = df.apply(
        lambda row: row['Prix Actuel (Original)'] * get_exchange_rate(row['Devise'], st.session_state.devise_cible, st.session_state.fx_rates)
        if pd.notna(row['Prix Actuel (Original)']) else None,
        axis=1
    )

    # Calcul des valeurs
    df['Valeur à l\'acquisition'] = df['Quantité'] * df['Acquisition']
    df['Valeur actuelle'] = df['Quantité'] * df['Prix Actuel (Cible)']

    # Calcul des plus ou moins-values latentes
    df['Plus/Moins-value Latente'] = df['Valeur actuelle'] - df['Valeur à l\'acquisition']
    df['% Plus/Moins-value'] = (df['Plus/Moins-value Latente'] / df['Valeur à l\'acquisition']) * 100
    df['% Plus/Moins-value'] = df['% Plus/Moins-value'].replace([np.inf, -np.inf], np.nan) # Gérer les divisions par zéro

    # Renommer les colonnes pour l'affichage
    df['Nom de l\'actif'] = df['Ticker'].apply(get_ticker_name)

    # Colonnes à afficher dans le portefeuille
    # Supprimons 'Prix Actuel (Original)' car 'Dernier Prix' n'est plus utile dans l'interface finale
    # La colonne 'Dernier Prix' n'est pas directement créée, elle était implicitement l'original price.
    # L'important est de s'assurer qu'elle n'est pas dans la sélection finale.

    display_cols = [
        'Nom de l\'actif',
        'Ticker',
        'Quantité',
        'Devise',
        'Acquisition',
        'Valeur à l\'acquisition',
        'Prix Actuel (Cible)', # Renommé pour la clarté
        'Valeur actuelle',
        'Plus/Moins-value Latente',
        '% Plus/Moins-value'
    ]

    df_display = df[display_cols].copy()

    # Formatter les colonnes numériques pour l'affichage
    format_mapping = {
        'Acquisition': '{:,.2f} {}'.format,
        'Valeur à l\'acquisition': '{:,.2f} {}'.format,
        'Prix Actuel (Cible)': '{:,.2f} {}'.format,
        'Valeur actuelle': '{:,.2f} {}'.format,
        'Plus/Moins-value Latente': '{:,.2f} {}'.format,
        '% Plus/Moins-value': '{:,.2f} %'.format
    }

    # Appliquer le formatage avec la devise cible
    devise_symbole = st.session_state.get('devise_cible', 'EUR') # Symbole par défaut
    for col, formatter in format_mapping.items():
        if col != '% Plus/Moins-value':
             # Utiliser la devise cible pour le formatage monétaire
            df_display[col] = df_display[col].apply(lambda x: formatter(x, devise_symbole) if pd.notna(x) else "N/A")
        else:
            df_display[col] = df_display[col].apply(lambda x: formatter(x) if pd.notna(x) else "N/A")


    # Calcul des totaux pour la synthèse globale
    total_valeur_acquisition = df['Valeur à l\'acquisition'].sum()
    total_valeur_actuelle = df['Valeur actuelle'].sum()
    total_pm_latente = df['Plus/Moins-value Latente'].sum()
    
    # Calcul du % total de Plus/Moins-value
    total_percent_pm = (total_pm_latente / total_valeur_acquisition) * 100 if total_valeur_acquisition != 0 else 0

    st.subheader(f"Portefeuille en {st.session_state.devise_cible}")

    # Fonction de tri
    def sort_dataframe(df_to_sort, column, direction):
        if column not in df_to_sort.columns:
            return df_to_sort # Retourne l'original si la colonne n'existe pas

        # Gestion des colonnes numériques pour le tri (en retirant les symboles)
        if '€' in df_to_sort[column].astype(str).iloc[0] or '$' in df_to_sort[column].astype(str).iloc[0] or '%' in df_to_sort[column].astype(str).iloc[0] or devise_symbole in df_to_sort[column].astype(str).iloc[0]:
            temp_col = df_to_sort[column].astype(str).str.replace(r'[^\d.,-]+', '', regex=True).str.replace(',', '.', regex=False).astype(float, errors='ignore')
            if pd.api.types.is_numeric_dtype(temp_col):
                return df_to_sort.iloc[temp_col.sort_values(ascending=(direction == "asc")).index]
        
        return df_to_sort.sort_values(by=column, ascending=(direction == "asc"))


    # Tri interactif
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        sort_by = st.selectbox("Trier par", options=df_display.columns.tolist(), index=0, key="sort_by_portfolio")
    with col2:
        sort_direction = st.radio("Direction", options=["Ascendant", "Descendant"], key="sort_direction_portfolio", horizontal=True)

    if sort_by:
        # Appliquer le tri sur le DataFrame original pour conserver les types numériques
        df_sorted_raw = df.copy()
        
        # Mapping des colonnes formatées vers les colonnes brutes pour le tri
        raw_col_map = {
            'Nom de l\'actif': 'Nom de l\'actif',
            'Ticker': 'Ticker',
            'Quantité': 'Quantité',
            'Devise': 'Devise',
            'Acquisition': 'Acquisition',
            'Valeur à l\'acquisition': 'Valeur à l\'acquisition',
            'Prix Actuel (Cible)': 'Prix Actuel (Cible)',
            'Valeur actuelle': 'Valeur actuelle',
            'Plus/Moins-value Latente': 'Plus/Moins-value Latente',
            '% Plus/Moins-value': '% Plus/Moins-value'
        }
        
        col_for_sorting = raw_col_map.get(sort_by, sort_by)

        df_sorted_raw = sort_dataframe(df_sorted_raw, col_for_sorting, sort_direction.lower().replace('ant', ''))
        
        # Après le tri du DataFrame brut, réappliquer le formatage pour l'affichage
        # S'assurer que l'ordre des colonnes est conservé pour l'affichage
        df_display_sorted = df_sorted_raw[display_cols].copy()
        for col, formatter in format_mapping.items():
            if col != '% Plus/Moins-value':
                df_display_sorted[col] = df_display_sorted[col].apply(lambda x: formatter(x, devise_symbole) if pd.notna(x) else "N/A")
            else:
                df_display_sorted[col] = df_display_sorted[col].apply(lambda x: formatter(x) if pd.notna(x) else "N/A")
        
        st.dataframe(df_display_sorted, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_display, use_container_width=True, hide_index=True)

    # Retourner les totaux pour la synthèse globale
    return total_valeur_acquisition, total_valeur_actuelle, total_pm_latente, total_percent_pm


def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """Affiche la synthèse globale du portefeuille."""
    devise_symbole = st.session_state.get('devise_cible', 'EUR') # Récupère la devise cible

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Valeur à l'acquisition",
            value=f"{total_valeur:,.2f} {devise_symbole}" if total_valeur is not None else "N/A",
            delta=None
        )
    with col2:
        if total_actuelle is not None and total_valeur is not None:
            delta_valeur = total_actuelle - total_valeur
            delta_pourcentage = (delta_valeur / total_valeur) * 100 if total_valeur != 0 else 0
            st.metric(
                label="Valeur Actuelle",
                value=f"{total_actuelle:,.2f} {devise_symbole}" if total_actuelle is not None else "N/A",
                delta=f"{delta_valeur:,.2f} {devise_symbole} ({delta_pourcentage:,.2f} %)" if total_valeur != 0 else "0.00 (0.00 %)",
                delta_color="normal" # "inverse" si vous voulez que le rouge soit positif
            )
        else:
             st.metric(
                label="Valeur Actuelle",
                value="N/A",
                delta=None
            )
    with col3:
        # st.metric(
        #     label="Plus/Moins-value Latente (52 semaines)",
        #     value=f"{total_h52:,.2f} {devise_symbole}" if total_h52 is not None else "N/A"
        # )
        st.markdown("##### Performance 52 sem.")
        st.markdown("*(À implémenter)*")
    with col4:
        # st.metric(
        #     label="Plus/Moins-value Latente (Long terme)",
        #     value=f"{total_lt:,.2f} {devise_symbole}" if total_lt is not None else "N/A"
        # )
        st.markdown("##### Performance Long Terme")
        st.markdown("*(À implémenter)*")
