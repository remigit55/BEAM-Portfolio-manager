# portfolio_display.py

import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components
import datetime
import pytz

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

# ... (reste du code jusqu'à la fonction afficher_portefeuille reste inchangé) ...

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

    # Formatage des colonnes pour l'affichage
    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Objectif_LT", 4),
        ("Momentum (%)", 2), ("Z-Score", 2), ("Gain/Perte (%)", 2),
        ("Taux_FX_Acquisition", 6), ("Taux_FX_Actuel", 6), ("Taux_FX_H52", 6), ("Taux_FX_LT", 6),
        ("Valeur Acquisition", 2), ("Valeur_Actuelle", 2), ("Valeur_H52", 2), ("Valeur_LT", 2), ("Gain/Perte", 2)
    ]:
        if col_name in df.columns:
            if col_name == "Valeur Acquisition":
                df[f"{col_name}_fmt"] = [
                    f"{format_fr(val, dec_places)} {dev}" if pd.notnull(val) else ""
                    for val, dev in zip(df[col_name], df["Devise"])
                ]
            elif col_name in ["Valeur_Actuelle", "Valeur_H52", "Valeur_LT"]:
                conv_col = f"{col_name}_conv"
                if conv_col in df.columns:
                    df[f"{col_name}_fmt"] = df[conv_col].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
                else:
                    st.warning(f"Colonne convertie {conv_col} manquante pour {col_name}. Utilisation de la valeur non convertie.")
                    df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
            elif col_name == "Gain/Perte":
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} {devise_cible}" if pd.notnull(x) else "")
            elif col_name in ["Gain/Perte (%)", "Momentum (%)"]:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: f"{format_fr(x, dec_places)} %" if pd.notnull(x) else "")
            elif col_name.startswith("Taux_FX_"):
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) if pd.notnull(x) else "N/A")
            else:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) if pd.notnull(x) else "")

    # Définition des colonnes à afficher et de leurs libellés
    cols = [
        ticker_col, "shortName", "Catégories", "Devise",
        "Quantité_fmt", "Acquisition_fmt",
        "Valeur Acquisition_fmt",
        "Valeur_Actuelle_conv",  # Utiliser la valeur convertie directement
        "Taux_FX_Acquisition_fmt",
        "currentPrice_fmt", "Valeur_Actuelle_fmt", "Gain/Perte_fmt", "Gain/Perte (%)_fmt",
        "fiftyTwoWeekHigh_fmt", "Valeur_H52_fmt", "Objectif_LT_fmt", "Valeur_LT_fmt",
        "Momentum (%)_fmt", "Z-Score_fmt",
        "Signal", "Action", "Justification"
    ]
    labels = [
        "Ticker", "Nom", "Catégories", "Devise Source",
        "Quantité", "Prix d'Acquisition (Source)",
        "Valeur Acquisition (Source)",
        f"Valeur Acquisition ({devise_cible})",
        "Taux FX (Source/Cible)",
        "Prix Actuel", f"Valeur Actuelle ({devise_cible})", f"Gain/Perte ({devise_cible})", "Gain/Perte (%)",
        "Haut 52 Semaines", f"Valeur H52 ({devise_cible})", "Objectif LT", f"Valeur LT ({devise_cible})",
        "Momentum (%)", "Z-Score",
        "Signal", "Action", "Justification"
    ]

    # Sélection des colonnes existantes
    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        if col_name == ticker_col and ticker_col is not None:
            if ticker_col in df.columns:
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
        elif col_name.endswith("_fmt") or col_name in ["Valeur_Actuelle_conv"]:
            if col_name in df.columns:
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
            else:
                base_col_name = col_name[:-4] if col_name.endswith("_fmt") else col_name
                if base_col_name in df.columns:
                    st.warning(f"Colonne formatée {col_name} manquante. Utilisation de {base_col_name}.")
                    existing_cols_in_df.append(base_col_name)
                    existing_labels.append(labels[i])
        elif col_name in df.columns:
            existing_cols_in_df.append(col_name)
            existing_labels.append(labels[i])

    if not existing_cols_in_df:
        st.warning("Aucune colonne de données valide à afficher.")
        return total_valeur, total_actuelle, total_h52, total_lt

    df_disp = df[existing_cols_in_df].copy()
    df_disp.columns = existing_labels

    # Gestion du tri
    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    if st.session_state.sort_column:
        sort_col_label = st.session_state.sort_column
        if sort_col_label in df_disp.columns:
            original_col_name = next((c for c, l in zip(existing_cols_in_df, existing_labels) if l == sort_col_label), None)
            if original_col_name and original_col_name in df.columns and pd.api.types.is_numeric_dtype(df[original_col_name]):
                df_disp = df.sort_values(
                    by=original_col_name,
                    ascending=(st.session_state.sort_direction == "asc")
                )[existing_cols_in_df]
                df_disp.columns = existing_labels
            else:
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: x.astype(str).str.lower() if x.dtype == "object" else x
                )

    # Configuration des colonnes pour st.table()
    column_configs = {
        "Ticker": st.column_config.TextColumn(align="left"),
        "Nom": st.column_config.TextColumn(align="left"),
        "Catégories": st.column_config.TextColumn(align="left"),
        "Devise Source": st.column_config.TextColumn(align="left"),
        "Signal": st.column_config.TextColumn(align="left"),
        "Action": st.column_config.TextColumn(align="left"),
        "Justification": st.column_config.TextColumn(align="left"),
    }
    for label in df_disp.columns:
        if label not in column_configs and any(x in label for x in ["Quantité", "Prix", "Valeur", "Taux", "Gain", "Momentum", "Z-Score", "Objectif"]):
            column_configs[label] = st.column_config.NumberColumn(format="%.2f %s", align="right")

    # Affichage du tableau
    st.table(df_disp)

    st.session_state.df = df

    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """
    Affiche la synthèse globale du portefeuille, y compris les métriques clés et le nouveau
    tableau de répartition par Catégories avec les objectifs.
    """
    devise_cible = st.session_state.get("devise_cible", "EUR")

    if total_valeur is None:
        st.info("Veuillez importer un fichier
