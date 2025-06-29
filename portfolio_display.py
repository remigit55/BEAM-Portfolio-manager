# -*- coding: utf-8 -*-
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

def convertir(val, source_devise, devise_cible, fx_rates_or_scalar, fx_adjustment_factor=1.0):
    """
    Convertit une valeur d'une devise source vers la devise cible en utilisant les taux de change fournis.
    Peut accepter un dictionnaire de taux de change (clé: devise source, valeur: taux)
    ou un taux scalaire direct.
    Applique également un facteur d'ajustement supplémentaire au taux de change.
    Retourne la valeur convertie et le taux utilisé (après ajustement).
    """
    if pd.isnull(val):
        return np.nan, np.nan  # Retourne NaN pour la valeur et le taux si la valeur est NaN

    source_devise = str(source_devise).strip().upper()  # Nettoyer et normaliser
    devise_cible = str(devise_cible).strip().upper()
    
    if source_devise == devise_cible:
        return val, 1.0  # Si c'est la même devise, pas de conversion, taux = 1.0

    taux_scalar = np.nan
    if isinstance(fx_rates_or_scalar, dict):
        # Si c'est un dictionnaire, on cherche le taux par la devise source
        fx_key = source_devise
        raw_taux = fx_rates_or_scalar.get(fx_key)
        try:
            taux_scalar = float(raw_taux)
        except (TypeError, ValueError):
            taux_scalar = np.nan
    elif isinstance(fx_rates_or_scalar, (float, int, np.floating, np.integer)):
        # Si c'est un scalaire, on l'utilise directement
        taux_scalar = float(fx_rates_or_scalar)
    else:
        st.warning(f"Type de taux de change inattendu: {type(fx_rates_or_scalar)}. Utilisation de 1.0.")
        taux_scalar = 1.0  # Valeur par défaut si le type est inattendu

    if pd.isna(taux_scalar) or taux_scalar == 0:
        st.warning(f"Pas de conversion pour {source_devise} vers {devise_cible}: taux manquant ou invalide ({taux_scalar}).")
        return val, np.nan  # Retourne la valeur originale et un taux NaN
    
    # Appliquer le facteur d'ajustement au taux de change
    if pd.notnull(fx_adjustment_factor) and fx_adjustment_factor != 0:
        taux_scalar /= fx_adjustment_factor
        
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

    # Nettoyage et migration des colonnes numériques
    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Lecture et traitement de la colonne 'H' pour le facteur d'ajustement FX
    if "H" in df.columns:
        df["Facteur_Ajustement_FX"] = df["H"].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
        df["Facteur_Ajustement_FX"] = pd.to_numeric(df["Facteur_Ajustement_FX"], errors="coerce").fillna(1.0)
    else:
        df["Facteur_Ajustement_FX"] = 1.0

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
        try:
            paris_tz = pytz.timezone('Europe/Paris')
            local_time = utc_now.astimezone(paris_tz)
            st.session_state["last_yfinance_update"] = local_time.strftime("%d/%m/%Y à %H:%M:%S")
        except pytz.UnknownTimeZoneError:
            st.warning("Erreur de fuseau horaire 'Europe/Paris'. Affichage en UTC.")
            st.session_state["last_yfinance_update"] = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M:%S")
        
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))

        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
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
        lambda x: convertir(x["Valeur Acquisition"], x["Devise"], devise_cible, fx_rates, x["Facteur_Ajustement_FX"]), 
        axis=1, result_type='expand'
    )
    df[['Valeur_Actuelle_conv', 'Taux_FX_Actuel']] = df.apply(
        lambda x: convertir(x["Valeur_Actuelle"], x["Devise"], devise_cible, fx_rates, x["Facteur_Ajustement_FX"]), 
        axis=1, result_type='expand'
    )
    df[['Valeur_H52_conv', 'Taux_FX_H52']] = df.apply(
        lambda x: convertir(x["Valeur_H52"], x["Devise"], devise_cible, fx_rates, x["Facteur_Ajustement_FX"]), 
        axis=1, result_type='expand'
    )
    df[['Valeur_LT_conv', 'Taux_FX_LT']] = df.apply(
        lambda x: convertir(x["Valeur_LT"], x["Devise"], devise_cible, fx_rates, x["Facteur_Ajustement_FX"]), 
        axis=1, result_type='expand'
    )

    # Calcul des totaux pour la synthèse
    total_valeur = pd.to_numeric(df["Valeur_conv"], errors='coerce').sum(skipna=True)
    total_actuelle = pd.to_numeric(df["Valeur_Actuelle_conv"], errors='coerce').sum(skipna=True)
    total_h52 = pd.to_numeric(df["Valeur_H52_conv"], errors='coerce').sum(skipna=True)
    total_lt = pd.to_numeric(df["Valeur_LT_conv"], errors='coerce').sum(skipna=True)

    # Calcul Gain/Perte
    df['Gain/Perte'] = df['Valeur_Actuelle_conv'] - df['Valeur_conv']
    df['Gain/Perte (%)'] = np.where(
        df['Valeur_conv'] != 0,
        (df['Gain/Perte'] / df['Valeur_conv']) * 100,
        0
    )

    # Formatage des colonnes pour l'affichage
    # Les colonnes avec "_fmt" seront celles affichées dans le dataframe final
    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Objectif_LT", 4),
        ("Momentum (%)", 2), ("Z-Score", 2), ("Gain/Perte (%)", 2),
        ("Taux_FX_Acquisition", 6), ("Taux_FX_Actuel", 6), ("Taux_FX_H52", 6), ("Taux_FX_LT", 6),
        ("Valeur Acquisition", 2), ("Valeur_Actuelle", 2), ("Valeur_H52", 2), ("Valeur_LT", 2), ("Gain/Perte", 2)
    ]:
        if col_name in df.columns:
            if col_name == "Valeur Acquisition":
                # Formatage avec la devise source correspondante
                df[f"{col_name}_fmt"] = [
                    f"{format_fr(val, dec_places)} {dev}" if pd.notnull(val) else ""
                    for val, dev in zip(df[col_name], df["Devise"])
                ]
            elif col_name in ["Valeur_Actuelle", "Valeur_H52", "Valeur_LT"]:
                # Utiliser les valeurs converties pour l'affichage en devise cible
                conv_col = f"{col_name}_conv"
                if conv_col in df.columns:
                    df[f"{col_name}_fmt"] = df[conv_col].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
                else:
                    # Fallback si la colonne convertie n'existe pas (ne devrait pas arriver avec le code actuel)
                    df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
            elif col_name == "Gain/Perte":
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
            elif col_name in ["Gain/Perte (%)", "Momentum (%)"]:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} %" if pd.notnull(x) else "")
            elif col_name.startswith("Taux_FX_"):
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)}" if pd.notnull(x) else "N/A")
            else:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)}" if pd.notnull(x) else "")

    # Définition des colonnes à afficher et de leurs libellés
    cols = [
        ticker_col, "shortName", "Catégories", "Devise", 
        "Quantité_fmt", "Acquisition_fmt", 
        "Valeur Acquisition_fmt",  
        "Valeur_conv",  # Cette colonne contient la valeur d'acquisition convertie en devise cible
        "Taux_FX_Acquisition_fmt", 
        "currentPrice_fmt", "Valeur_Actuelle_fmt", "Gain/Perte_fmt", "Gain/Perte (%)_fmt",
        "fiftyTwoWeekHigh_fmt", "Valeur_H52_fmt", "Objectif_LT_fmt", "Valeur_LT_fmt",
        "Momentum (%)_fmt", "Z-Score_fmt",
        "Signal", "Action", "Justification"
    ]
    labels = [
        "Ticker", "Nom", "Catégories", "Devise Source", 
        "Quantité", "Prix d'Acquisition (Source)", 
        "Valeur Acquisition (Source)", # Valeur d'acquisition dans la devise source
        f"Valeur Acquisition ({devise_cible})", # Valeur d'acquisition convertie
        "Taux FX (Source/Cible)", 
        "Prix Actuel", f"Valeur Actuelle ({devise_cible})", f"Gain/Perte ({devise_cible})", "Gain/Perte (%)",
        "Haut 52 Semaines", f"Valeur H52 ({devise_cible})", "Objectif LT", f"Valeur LT ({devise_cible})",
        "Momentum (%)", "Z-Score",
        "Signal", "Action", "Justification"
    ]

    # Sélection des colonnes existantes avec priorité aux colonnes formatées
    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        if col_name == ticker_col and ticker_col is not None:
            if ticker_col in df.columns:
                existing_cols_in_df.append(ticker_col)
                existing_labels.append(labels[i])
        elif col_name.endswith("_fmt"): # C'est une colonne formatée
            if col_name in df.columns:
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
            else: # Fallback si la colonne _fmt n'est pas générée pour une raison quelconque
                base_col_name = col_name[:-4] # Supprime "_fmt"
                if base_col_name in df.columns:
                    existing_cols_in_df.append(base_col_name)
                    existing_labels.append(labels[i])
        elif col_name in df.columns: # Colonne non formatée mais existante
            existing_cols_in_df.append(col_name)
            existing_labels.append(labels[i])

    if not existing_cols_in_df:
        st.warning("Aucune colonne de données valide à afficher.")
        return total_valeur, total_actuelle, total_h52, total_lt

    df_disp = df[existing_cols_in_df].copy()
    df_disp.columns = existing_labels  

    # Définition du dictionnaire de formatage pour st.dataframe.style.format
    # Note: Puisque nous pré-formatons les colonnes avec "_fmt", le .style.format
    # doit simplement s'assurer que ces colonnes sont traitées comme des chaînes.
    # Pour les colonnes non-fmt (comme 'shortName', 'Signal', etc.), on peut les convertir en str.
    format_dict_portfolio = {
        "Quantité": lambda x: x,
        "Prix d'Acquisition (Source)": lambda x: x,
        "Valeur Acquisition (Source)": lambda x: x,
        f"Valeur Acquisition ({devise_cible})": lambda x: f"{format_fr(x, 2)} {devise_cible}" if pd.notnull(x) else "",
        "Taux FX (Source/Cible)": lambda x: x,
        "Prix Actuel": lambda x: x,
        f"Valeur Actuelle ({devise_cible})": lambda x: x,
        f"Gain/Perte ({devise_cible})": lambda x: x,
        "Gain/Perte (%)": lambda x: x,
        "Haut 52 Semaines": lambda x: x,
        f"Valeur H52 ({devise_cible})": lambda x: x,
        "Objectif LT": lambda x: x,
        f"Valeur LT ({devise_cible})": lambda x: x,
        "Momentum (%)": lambda x: x,
        "Z-Score": lambda x: x,
        "Ticker": lambda x: str(x) if pd.notnull(x) else "",
        "Nom": lambda x: str(x) if pd.notnull(x) else "",
        "Catégories": lambda x: str(x) if pd.notnull(x) else "",
        "Devise Source": lambda x: str(x) if pd.notnull(x) else "",
        "Signal": lambda x: str(x) if pd.notnull(x) else "",
        "Action": lambda x: str(x) if pd.notnull(x) else "",
        "Justification": lambda x: str(x) if pd.notnull(x) else ""
    }

    # Filtrer le dictionnaire de formatage
    filtered_format_dict_portfolio = {k: v for k, v in format_dict_portfolio.items() if k in df_disp.columns}

    # Définition des colonnes numériques et textuelles pour l'alignement CSS
    # Mise à jour de la liste des colonnes numériques selon votre demande
    numeric_columns = [
        "Quantité", "Prix d'Acquisition (Source)", "Valeur Acquisition (Source)",
        f"Valeur Acquisition ({devise_cible})", "Taux FX (Source/Cible)", "Prix Actuel",
        f"Valeur Actuelle ({devise_cible})", f"Gain/Perte ({devise_cible})", "Gain/Perte (%)",
        "Haut 52 Semaines", f"Valeur H52 ({devise_cible})", "Objectif LT", f"Valeur LT ({devise_cible})",
        "Momentum (%)", "Z-Score"
    ]
    text_columns = ["Ticker", "Nom", "Catégories", "Devise Source", "Signal", "Action", "Justification"]
    
    css_alignments = """
        [data-testid="stDataFrame"] * { box-sizing: border-box; }
        [data-testid="stDataFrame"] div[role="grid"] table {
            width: 100% !important;
            table-layout: auto; /* Permet aux colonnes de s'ajuster en largeur */
        }
    """
    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1 # nth-child est 1-indexé
        if label in numeric_columns:
            css_alignments += f"""
                [data-testid="stDataFrame"] div[role="grid"] table tbody tr td:nth-child({col_idx}),
                [data-testid="stDataFrame"] div[role="grid"] table thead tr th:nth-child({col_idx}) {{
                    text-align: right !important;
                    white-space: nowrap !important; /* Empêche le texte de se couper */
                    padding-right: 10px !important;
                }}
            """
        elif label in text_columns:
            css_alignments += f"""
                [data-testid="stDataFrame"] div[role="grid"] table tbody tr td:nth-child({col_idx}),
                [data-testid="stDataFrame"] div[role="grid"] table thead tr th:nth-child({col_idx}) {{
                    text-align: left !important;
                    white-space: normal !important; /* Permet au texte de se couper */
                    padding-left: 10px !important;
                }}
            """

    st.markdown(f"""
        <style>
            {css_alignments}
        </style>
    """, unsafe_allow_html=True)

    # Affichage du tableau du portefeuille
    st.markdown("##### Détail du Portefeuille")
    st.dataframe(df_disp.style.format(filtered_format_dict_portfolio), use_container_width=True, hide_index=True)

    st.session_state.df = df  

    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """
    Affiche la synthèse globale du portefeuille, y compris les métriques clés et le tableau de répartition par Catégories.
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

    # Tableau de Répartition par Catégories
    st.markdown("#### Répartition et Objectifs par Catégories")  

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
            
            # Logique spécifique pour la réallocation des Minières
            if category == "Minières":
                temp_allocations_reelles = {
                    cat: (category_values.get(cat, 0.0) / total_actuelle) if total_actuelle > 0 else 0.0
                    for cat in all_relevant_categories
                }
                value_to_adjust = calculer_reallocation_miniere(df, temp_allocations_reelles, target_allocations, "Catégories", "Valeur_Actuelle_conv")
                if value_to_adjust is None:
                    value_to_adjust = np.nan
            else:
                value_to_adjust = target_value_for_category - current_value_cat
            
            results_data.append({
                "Catégories": category,
                "Valeur Actuelle": current_value_cat,
                "Part Actuelle (%)": current_pct * 100,
                "Cible (%)": target_pct * 100,
                "Écart à l'objectif (%)": (current_pct - target_pct) * 100,
                "Ajustement Nécessaire": value_to_adjust
            })

        df_allocation = pd.DataFrame(results_data)
        df_allocation = df_allocation.sort_values(by='Part Actuelle (%)', ascending=False)
        
        # Définition des colonnes à afficher
        cols_to_display_cat = [
            "Catégories",
            "Valeur Actuelle",
            "Part Actuelle (%)",
            "Cible (%)",
            "Écart à l'objectif (%)",
            "Ajustement Nécessaire"
        ]
        labels_for_display_cat = [
            "Catégories",
            "Valeur Actuelle",
            "Part Actuelle (%)",
            "Cible (%)",
            "Écart à l'objectif (%)",
            f"Ajustement Nécessaire ({devise_cible})"
        ]

        df_disp_cat = df_allocation[cols_to_display_cat].copy()
        df_disp_cat.columns = labels_for_display_cat

        # Définition du dictionnaire de formatage
        format_dict_category = {
            "Valeur Actuelle": lambda x: f"{format_fr(x, 2)} {devise_cible}",
            "Part Actuelle (%)": lambda x: f"{format_fr(x, 2)} %",
            "Cible (%)": lambda x: f"{format_fr(x, 2)} %",
            "Écart à l'objectif (%)": lambda x: f"{format_fr(x, 2)} %",
            f"Ajustement Nécessaire ({devise_cible})": lambda x: f"{format_fr(x, 2)} {devise_cible}" if pd.notnull(x) else "N/A"
        }

        # Filtrer le dictionnaire de formatage
        filtered_format_dict_category = {k: v for k, v in format_dict_category.items() if k in df_disp_cat.columns}
        
        # Affichage du tableau de répartition
        st.dataframe(df_disp_cat.style.format(filtered_format_dict_category), use_container_width=True, hide_index=True)

    else:
        st.info("Aucune donnée de portefeuille chargée pour calculer la répartition par catégories.")
