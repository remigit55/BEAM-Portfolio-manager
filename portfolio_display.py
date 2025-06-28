# portfolio_display.py

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import pytz

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data


def calculer_reallocation_miniere(df, allocations_reelles, objectifs, colonne_cat="Catégorie", colonne_valeur="Valeur Actuelle"):
    if "Minières" not in allocations_reelles or "Minières" not in objectifs:
        return None

    # Calcul des dérives relatives hors Minières
    derive_abs = {
        cat: abs(allocations_reelles[cat] - objectifs.get(cat, 0))
        for cat in allocations_reelles
        if cat != "Minières" and cat in objectifs
    }

    if not derive_abs:
        return None

    # Catégorie avec la plus forte dérive absolue
    cat_ref = max(derive_abs, key=derive_abs.get)

    valeur_cat_ref = df[df[colonne_cat] == cat_ref][colonne_valeur].sum()
    objectif_cat_ref = objectifs[cat_ref]
    objectif_miniere = objectifs["Minières"]
    valeur_actuelle_miniere = df[df[colonne_cat] == "Minières"][colonne_valeur].sum()

    if objectif_cat_ref == 0:
        return None

    # Valeur cible recalculée pour Minières
    valeur_cible_miniere = (valeur_cat_ref / objectif_cat_ref) * objectif_miniere

    # Si sous-pondération, on propose une réallocation
    if allocations_reelles["Minières"] < objectif_miniere:
        return valeur_cible_miniere - valeur_actuelle_miniere
    else:
        return 0


# --- Fonction de conversion de devise ---
def convertir(val, source_devise, devise_cible, fx_rates):
    """
    Convertit une valeur d'une devise source vers la devise cible en utilisant les taux de change fournis.
    Retourne la valeur originale et un taux de 1.0 si le taux de change est manquant ou nul.
    Retourne la valeur convertie et le taux utilisé.
    """
    if pd.isnull(val):
        return np.nan, np.nan  # Retourne NaN pour la valeur et le taux si la valeur est NaN

    source_devise = str(source_devise).strip().upper()  # Nettoyer et normaliser
    devise_cible = str(devise_cible).strip().upper()
    
    if source_devise == devise_cible:
        return val, 1.0  # Si c'est la même devise, pas de conversion, taux = 1.0

    fx_key = source_devise
    raw_taux = fx_rates.get(fx_key)
    
    try:
        taux_scalar = float(raw_taux)
    except (TypeError, ValueError):
        taux_scalar = np.nan

    if pd.isna(taux_scalar) or taux_scalar == 0:
        st.warning(f"Pas de conversion pour {source_devise} vers {devise_cible}: taux manquant ou invalide ({raw_taux}).")
        return val, np.nan  # Retourne la valeur originale et un taux NaN
        
    return val * taux_scalar, taux_scalar  # Retourne la valeur convertie ET le taux utilisé

def afficher_portefeuille():
    """
    Affiche le portefeuille de l'utilisateur, gère les calculs et l'affichage.
    Récupère les données externes via des fonctions dédiées.
    Retourne les totaux convertis pour la synthèse.
    """
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return None, None, None, None

    df = st.session_state.df.copy()

    # Assurez-vous que 'LT' est renommé en 'Objectif_LT'
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    # Initialisation ou rafraîchissement des taux de change
    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        devises_uniques_df = df["Devise"].dropna().str.strip().str.upper().unique().tolist() if "Devise" in df.columns else []
        devises_a_fetch = list(set([devise_cible] + devises_uniques_df))
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
    
    fx_rates = st.session_state.fx_rates

    # Vérifier les taux manquants
    devises_uniques = df["Devise"].dropna().str.strip().str.upper().unique().tolist() if "Devise" in df.columns else []
    missing_rates = [devise for devise in devises_uniques if fx_rates.get(devise) is None and devise != devise_cible.upper()]
    if missing_rates:
        st.warning(f"Taux de change manquants pour les devises : {', '.join(missing_rates)}. Les valeurs ne seront pas converties pour ces devises.")

    # Nettoyage et conversion des colonnes numériques
    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Nettoyage de la colonne Devise
    if "Devise" in df.columns:
        df["Devise"] = df["Devise"].astype(str).str.strip().str.upper().fillna(devise_cible)
    else:
        st.error("Colonne 'Devise' absente. Utilisation de la devise cible par défaut.")
        df["Devise"] = devise_cible

    # GESTION DE LA COLONNE 'CATÉGORIES'
    if "Categories" in df.columns:  
        df["Catégories"] = df["Categories"].astype(str).fillna("").str.strip()  
        df["Catégories"] = df["Catégories"].replace("", np.nan).fillna("Non classé")
    elif any(col.strip().lower() in ["categories", "catégorie", "category"] for col in df.columns):
        # Trouver la colonne correspondante (insensible à la casse et accents)
        cat_col = next(col for col in df.columns if col.strip().lower() in ["categories", "catégorie", "category"])
        df["Catégories"] = df[cat_col].astype(str).fillna("").str.strip()
        df["Catégories"] = df["Catégories"].replace("", np.nan).fillna("Non classé")
    else:
        st.warning("ATTENTION: Aucune colonne 'Categories' ou équivalente introuvable. 'Catégories' sera 'Non classé'.")
        df["Catégories"] = "Non classé"

    # Déterminer la colonne Ticker
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    # Initialisation des caches
    if "ticker_data_cache" not in st.session_state:
        st.session_state.ticker_data_cache = {}
    if "momentum_results_cache" not in st.session_state:
        st.session_state.momentum_results_cache = {}

    # Récupération des données pour chaque ticker
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().unique()
        for ticker in unique_tickers:
            if ticker not in st.session_state.ticker_data_cache:
                st.session_state.ticker_data_cache[ticker] = fetch_yahoo_data(ticker)
            if ticker not in st.session_state.momentum_results_cache:
                st.session_state.momentum_results_cache[ticker] = fetch_momentum_data(ticker)


        # Obtenir l'heure actuelle en UTC
        utc_now = datetime.datetime.now(datetime.timezone.utc)

        # Définir le fuseau horaire cible (par exemple, Paris pour l'heure française)
        # Utilise 'Europe/Paris' pour inclure la gestion de l'heure d'été/hiver
        try:
            paris_tz = pytz.timezone('Europe/Paris')
            # Convertir l'heure UTC en heure locale de Paris
            local_time = utc_now.astimezone(paris_tz)
            # Formater pour l'affichage français (jour/mois/année à HH:MM:SS)
            st.session_state["last_yfinance_update"] = local_time.strftime("%d/%m/%Y à %H:%M:%S")
        except pytz.UnknownTimeZoneError:
            st.warning("Erreur de fuseau horaire 'Europe/Paris'. Affichage en UTC.")
            st.session_state["last_yfinance_update"] = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
        
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))

        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Signal", ""))
        df["Action"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
        df["Justification"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Justification", ""))
    else:
        df["shortName"] = ""
        df["currentPrice"] = np.nan
        df["fiftyTwoWeekHigh"] = np.nan
        df["Momentum (%)"] = np.nan
        df["Z-Score"] = np.nan
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""

    # Calcul des valeurs du portefeuille
    df["Valeur Acquisition"] = df["Quantité"] * df["Acquisition"]
    df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]

    # Conversion des valeurs à la devise cible
    df[['Valeur_conv', 'Taux_FX_Acquisition']] = df.apply(
        lambda x: convertir(x["Valeur Acquisition"], x["Devise"], devise_cible, fx_rates), 
        axis=1, result_type='expand'
    )
    df[['Valeur_Actuelle_conv', 'Taux_FX_Actuel']] = df.apply(
        lambda x: convertir(x["Valeur_Actuelle"], x["Devise"], devise_cible, fx_rates), 
        axis=1, result_type='expand'
    )
    df[['Valeur_H52_conv', 'Taux_FX_H52']] = df.apply(
        lambda x: convertir(x["Valeur_H52"], x["Devise"], devise_cible, fx_rates), 
        axis=1, result_type='expand'
    )
    df[['Valeur_LT_conv', 'Taux_FX_LT']] = df.apply(
        lambda x: convertir(x["Valeur_LT"], x["Devise"], devise_cible, fx_rates), 
        axis=1, result_type='expand'
    )

    # Calcul des totaux globaux convertis
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Calcul Gain/Perte
    df['Gain/Perte'] = df['Valeur_Actuelle_conv'] - df['Valeur_conv']
    df['Gain/Perte (%)'] = np.where(
        df['Valeur_conv'] != 0,
        (df['Gain/Perte'] / df['Valeur_conv']) * 100,
        0
    )

    # Formatage des colonnes pour l'affichage (sans créer de nouvelles colonnes _fmt pour Streamlit)
    # Nous allons appliquer le formatage directement lors de l'affichage avec st.dataframe

    # Définition des colonnes à afficher et de leurs libellés
    cols_to_display = [
        ticker_col, "shortName", "Catégories", "Devise", "Quantité", "Acquisition",
        "Valeur Acquisition",  # Valeur source
        "Valeur_conv",         # Valeur convertie
        "Taux_FX_Acquisition",
        "currentPrice", "Valeur_Actuelle", "Gain/Perte", "Gain/Perte (%)",
        "fiftyTwoWeekHigh", "Valeur_H52", "Objectif_LT", "Valeur_LT",
        "Momentum (%)", "Z-Score", "Signal", "Action", "Justification"
    ]
    labels = {
        ticker_col: "Ticker",
        "shortName": "Nom",
        "Catégories": "Catégories",
        "Devise": "Devise Source",
        "Quantité": "Quantité",
        "Acquisition": "Prix d'Acquisition (Source)",
        "Valeur Acquisition": "Valeur Acquisition (Source)",
        "Valeur_conv": f"Valeur Acquisition ({devise_cible})",
        "Taux_FX_Acquisition": "Taux FX (Source/Cible)",
        "currentPrice": "Prix Actuel",
        "Valeur_Actuelle": f"Valeur Actuelle ({devise_cible})",
        "Gain/Perte": f"Gain/Perte ({devise_cible})",
        "Gain/Perte (%)": "Gain/Perte (%)",
        "fiftyTwoWeekHigh": "Haut 52 Semaines",
        "Valeur_H52": f"Valeur H52 ({devise_cible})",
        "Objectif_LT": "Objectif LT",
        "Valeur_LT": f"Valeur LT ({devise_cible})",
        "Momentum (%)": "Momentum (%)",
        "Z-Score": "Z-Score",
        "Signal": "Signal",
        "Action": "Action",
        "Justification": "Justification"
    }

    # Création du DataFrame pour l'affichage avec seulement les colonnes pertinentes
    # et leurs noms affichables.
    df_display = pd.DataFrame()
    for col in cols_to_display:
        if col == ticker_col:
            if ticker_col in df.columns:
                df_display[labels[ticker_col]] = df[ticker_col]
        elif col in df.columns:
            # Pour les colonnes numériques qui seront formatées, nous utilisons les valeurs brutes ici
            # Le formatage sera appliqué par Streamlit directement.
            if col in ["Quantité", "Acquisition", "currentPrice", "fiftyTwoWeekHigh", "Objectif_LT",
                       "Valeur Acquisition", "Valeur_conv", "Taux_FX_Acquisition",
                       "Valeur_Actuelle", "Gain/Perte", "Gain/Perte (%)",
                       "Valeur_H52", "Valeur_LT", "Momentum (%)", "Z-Score"]:
                df_display[labels[col]] = df[col]
            else:
                df_display[labels[col]] = df[col]
    
    # Définition des formats pour st.dataframe
    # Note: Streamlit apply formatting using Python's f-string capabilities or display functions.
    # We will pass a dictionary of formats to st.dataframe.
    column_config = {}
    
    # Helper to apply currency/percentage formatting
    currency_cols = [
        f"Valeur Acquisition ({devise_cible})",
        f"Valeur Actuelle ({devise_cible})",
        f"Gain/Perte ({devise_cible})",
        f"Valeur H52 ({devise_cible})",
        f"Valeur LT ({devise_cible})"
    ]

    percentage_cols = ["Gain/Perte (%)", "Momentum (%)"]

    for label in df_display.columns:
        if label in currency_cols:
            column_config[label] = st.column_config.NumberColumn(
                label,
                format=f"%.2f {devise_cible}",
                help=f"Valeur en {devise_cible}"
            )
        elif label in percentage_cols:
            column_config[label] = st.column_config.NumberColumn(
                label,
                format="%.2f %%",
                help="Valeur en pourcentage"
            )
        elif label == "Taux FX (Source/Cible)":
            column_config[label] = st.column_config.NumberColumn(
                label,
                format="%.6f",
                help="Taux de change appliqué"
            )
        elif label in ["Prix d'Acquisition (Source)", "Prix Actuel", "Haut 52 Semaines", "Objectif LT"]:
            column_config[label] = st.column_config.NumberColumn(
                label,
                format="%.4f",
                help="Prix unitaire"
            )
        elif label == "Quantité":
            column_config[label] = st.column_config.NumberColumn(
                label,
                format="%d",
                help="Quantité détenue"
            )
        elif label in ["Z-Score"]:
            column_config[label] = st.column_config.NumberColumn(
                label,
                format="%.2f",
                help="Score Z de momentum"
            )
        elif label == "Nom":
            column_config[label] = st.column_config.TextColumn(
                label,
                width="large"
            )
        elif label in ["Justification"]:
            column_config[label] = st.column_config.TextColumn(
                label,
                width="extra_large"
            )


    st.dataframe(df_display, use_container_width=True, column_config=column_config)

    st.session_state.df = df # Ensure the original df (with calculated columns) is saved.

    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """
    Affiche la synthèse globale du portefeuille, y compris les métriques clés et le nouveau
    tableau de répartition par Catégories avec les objectifs.
    """
    devise_cible = st.session_state.get("devise_cible", "EUR")

    if total_valeur is None:
        st.info("Veuillez importer un fichier Excel pour voir la synthèse de votre portefeuille.")
        return

    # Affichage des métriques clés
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label=f"**Valeur d'Acquisition ({devise_cible})**",
            value=f"{format_fr(total_valeur, 2)} {devise_cible}"
        )
    with col2:
        st.metric(
            label=f"**Valeur Actuelle ({devise_cible})**",
            value=f"{format_fr(total_actuelle, 2)} {devise_cible}"
        )
    
    if total_valeur != 0 and pd.notna(total_valeur) and pd.notna(total_actuelle):
        gain_perte_abs = total_actuelle - total_valeur
        pourcentage_gain_perte = (gain_perte_abs / total_valeur) * 100
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"{format_fr(gain_perte_abs, 2)} {devise_cible}",
                delta=f"{format_fr(pourcentage_gain_perte, 2)} %"
            )
    else:
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}",
                delta="N/A %"
            )

    with col4:
        lt_display = format_fr(total_lt, 2) if pd.notna(total_lt) else "N/A"
        st.metric(
            label=f"**Objectif LT ({devise_cible})**",  
            value=f"{lt_display} {devise_cible}"
        )
    st.markdown("---")

    # --- Tableau de Répartition par Catégories ---
    st.markdown("#### Répartition et Objectifs par Catégories")  

    # Définition des allocations cibles par catégorie
    target_allocations = st.session_state.get("target_allocations", {
        "Minières": 0.41,
        "Asie": 0.25,
        "Energie": 0.25,
        "Matériaux": 0.01,
        "Devises": 0.08,
        "Crypto": 0.00,
        "Autre": 0.00  
    })

    if "df" in st.session_state and st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df.copy()
        
        if 'Catégories' not in df.columns:
            st.error("ERREUR : La colonne 'Catégories' est manquante dans le DataFrame pour la synthèse.")
            st.info(f"Colonnes disponibles : {df.columns.tolist()}")
            return

        df['Valeur_Actuelle_conv'] = pd.to_numeric(df['Valeur_Actuelle_conv'], errors='coerce').fillna(0)
        
        # Regroupe par la colonne "Catégories"
        category_values = df.groupby('Catégories')['Valeur_Actuelle_conv'].sum()
        
        # Calcul de la base pour l'objectif
        current_minieres_value = category_values.get("Minières", 0.0)
        target_minieres_pct = target_allocations.get("Minières", 0.0)
        theoretical_portfolio_total_from_minieres = current_minieres_value / target_minieres_pct if target_minieres_pct > 0 else total_actuelle

        if pd.isna(theoretical_portfolio_total_from_minieres) or np.isinf(theoretical_portfolio_total_from_minieres) or theoretical_portfolio_total_from_minieres <= 0:
            theoretical_portfolio_total_from_minieres = total_actuelle  

        results_data = []

        all_relevant_categories = sorted(list(set(target_allocations.keys()) | set(category_values.index.tolist())))
        
        for category in all_relevant_categories:
            target_pct = target_allocations.get(category, 0.0)
            current_value_cat = category_values.get(category, 0.0)
            
            if pd.isna(current_value_cat):
                current_value_cat = 0.0

            current_pct = (current_value_cat / total_actuelle) if total_actuelle > 0 else 0.0
            target_value_for_category = target_pct * theoretical_portfolio_total_from_minieres
            deviation_pct = (current_pct - target_pct)
            value_to_adjust = target_value_for_category - current_value_cat
            
            # Not formatting here, letting st.dataframe handle it later
            results_data.append({
                "Catégories": category,
                "Valeur Actuelle": current_value_cat,
                "Part Actuelle (%)": current_pct * 100,
                "Cible (%)": target_pct * 100,
                "Écart à l'objectif (%)": deviation_pct * 100,
                "Ajustement Nécessaire": value_to_adjust
            })

        df_allocation = pd.DataFrame(results_data)
        # We sort by 'Part Actuelle (%)' as it's a numeric column before displaying
        df_allocation = df_allocation.sort_values(by='Part Actuelle (%)', ascending=False)
        
        # Define column configurations for the allocation table
        allocation_column_config = {
            "Valeur Actuelle": st.column_config.NumberColumn(
                f"Valeur Actuelle ({devise_cible})",
                format=f"%.2f {devise_cible}"
            ),
            "Part Actuelle (%)": st.column_config.NumberColumn(
                "Part Actuelle (%)",
                format="%.2f %%"
            ),
            "Cible (%)": st.column_config.NumberColumn(
                "Cible (%)",
                format="%.2f %%"
            ),
            "Écart à l'objectif (%)": st.column_config.NumberColumn(
                "Écart à l'objectif (%)",
                format="%.2f %%"
            ),
            "Ajustement Nécessaire": st.column_config.NumberColumn(
                f"Ajustement Nécessaire ({devise_cible})",
                format=f"%.2f {devise_cible}"
            )
        }

        st.dataframe(df_allocation, use_container_width=True, column_config=allocation_column_config)
