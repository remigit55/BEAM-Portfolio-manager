# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données.
# Assurez-vous que data_fetcher.py existe et contient ces fonctions.
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

# --- Fonction de conversion de devise ---
def convertir(val, source_devise, devise_cible, fx_rates):
    """
    Convertit une valeur d'une devise source vers la devise cible en utilisant les taux de change fournis.
    Retourne np.nan si la conversion est impossible (taux manquant/nul).
    """
    if pd.isnull(val):
        return np.nan

    source_devise = str(source_devise).upper()
    devise_cible = str(devise_cible).upper()
    
    if source_devise == devise_cible:
        return val

    # Clé de taux de change attendue dans fx_rates est 'SOURCE/CIBLE'
    fx_key = f"{source_devise}/{devise_cible}"
    raw_taux = fx_rates.get(fx_key)
    
    try:
        taux_scalar = float(raw_taux)
    except (TypeError, ValueError):
        taux_scalar = np.nan # Si le taux n'est pas un nombre valide, il est NaN

    if pd.isna(taux_scalar) or taux_scalar == 0:
        # Si le taux est manquant ou nul, la conversion est impossible.
        # Retourne np.nan pour indiquer l'absence de valeur convertie.
        # Cela permettra aux sommes d'ignorer ces valeurs (sum(skipna=True)).
        return np.nan
    
    return val * taux_scalar


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
    # S'assurer que toutes les devises du DF sont incluses pour la récupération des taux
    devises_uniques_df = df["Devise"].dropna().unique().tolist() if "Devise" in df.columns else []
    devises_a_fetch = list(set([devise_cible] + devises_uniques_df))
    # Ne pas utiliser st.session_state.fx_rates directement dans fetch_fx_rates pour éviter les dépendances circulaires
    # et s'assurer que tous les taux nécessaires sont récupérés.
    st.session_state.fx_rates = fetch_fx_rates(devise_cible, devises_a_fetch)
    
    fx_rates = st.session_state.fx_rates

    # Nettoyage et conversion des colonnes numériques
    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # GESTION DE LA COLONNE 'CATÉGORIE'
    if "Categories" in df.columns: 
        df["Catégorie"] = df["Categories"].astype(str).fillna("Non Classé") 
    else:
        st.warning("ATTENTION (afficher_portefeuille): La colonne 'Categories' est introuvable dans votre fichier d'entrée. La colonne 'Catégorie' sera 'Non Classé' pour l'affichage et la synthèse.")
        df["Catégorie"] = "Non Classé" 

    # Déterminer la colonne Ticker (peut être "Ticker" ou "Tickers")
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    # Initialisation des caches pour les données externes
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
        
        # Mapping des données récupérées au DataFrame
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))

        df["Last Price"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Last Price", np.nan))
        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Signal", ""))
        df["Action"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
        df["Justification"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Justification", ""))
    else:
        # Si pas de tickers, initialiser les colonnes vides pour éviter les erreurs
        df["shortName"] = ""
        df["currentPrice"] = np.nan
        df["fiftyTwoWeekHigh"] = np.nan
        df["Last Price"] = np.nan
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

    df["Devise"] = df["Devise"].fillna(devise_cible).astype(str).str.upper()

    # Conversion des valeurs à la devise cible
    # Utiliser .sum(skipna=True) pour ignorer les NaN résultant de conversions impossibles
    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur Acquisition"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"], devise_cible, fx_rates), axis=1)

    # Calcul des totaux globaux convertis, en ignorant les NaN (skipna=True)
    total_valeur = df["Valeur_conv"].sum(skipna=True)
    total_actuelle = df["Valeur_Actuelle_conv"].sum(skipna=True)
    total_h52 = df["Valeur_H52_conv"].sum(skipna=True)
    total_lt = df["Valeur_LT_conv"].sum(skipna=True)

    # Calcul Gain/Perte
    df['Gain/Perte'] = df['Valeur_Actuelle_conv'] - df['Valeur_conv']
    df['Gain/Perte (%)'] = np.where(
        (df['Valeur_conv'] != 0) & (pd.notna(df['Valeur_conv'])), # Vérifier si Valeur_conv est non-nul et non-NaN
        (df['Gain/Perte'] / df['Valeur_conv']) * 100,
        np.nan # Remplacer par NaN si le calcul n'est pas possible
    )

    # Formatage des colonnes pour l'affichage
    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("Valeur Acquisition", 2), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Valeur_H52", 2), ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4), ("Valeur_LT", 2), ("Gain/Perte", 2),
        ("Momentum (%)", 2), ("Z-Score", 2), ("Gain/Perte (%)", 2)
    ]:
        if col_name in df.columns:
            if col_name in ["Valeur Acquisition", "Valeur_H52", "Valeur_Actuelle", "Valeur_LT", "Gain/Perte"]:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) + f" {devise_cible}" if pd.notna(x) else "N/A")
            elif col_name == "Gain/Perte (%)" or col_name == "Momentum (%)" or col_name == "Z-Score": 
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) + " %" if pd.notna(x) else "N/A")
            else:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) if pd.notna(x) else "N/A")


    # Définition des colonnes à afficher et de leurs libellés
    cols = [
        ticker_col, "shortName", "Catégorie", "Devise",
        "Quantité_fmt", "Acquisition_fmt", "Valeur Acquisition_fmt",
        "currentPrice_fmt", "Valeur_Actuelle_fmt", "Gain/Perte_fmt", "Gain/Perte (%)_fmt",
        "fiftyTwoWeekHigh_fmt", "Valeur_H52_fmt", "Objectif_LT_fmt", "Valeur_LT_fmt",
        "Last Price", "Momentum (%)_fmt", "Z-Score_fmt",
        "Signal", "Action", "Justification"
    ]
    labels = [
        "Ticker", "Nom", "Catégorie", "Devise",
        "Quantité", "Prix d'Acquisition", "Valeur Acquisition",
        "Prix Actuel", "Valeur Actuelle", "Gain/Perte", "Gain/Perte (%)",
        "Haut 52 Semaines", "Valeur H52", "Objectif LT", "Valeur LT",
        "Dernier Prix", "Momentum (%)", "Z-Score",
        "Signal", "Action", "Justification"
    ]

    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        if col_name == ticker_col and ticker_col is not None:
            if ticker_col in df.columns:
                existing_cols_in_df.append(ticker_col)
                existing_labels.append(labels[i])
        elif col_name.endswith("_fmt"):
            base_col_name = col_name[:-4] 
            if f"{base_col_name}_fmt" in df.columns: 
                existing_cols_in_df.append(f"{base_col_name}_fmt")
                existing_labels.append(labels[i])
            elif base_col_name in df.columns: 
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

    # Gestion du tri des colonnes via les en-têtes HTML
    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    if st.session_state.sort_column:
        sort_col_label = st.session_state.sort_column
        if sort_col_label in df_disp.columns:
            original_col_name = None
            try:
                idx = existing_labels.index(sort_col_label)
                original_col_name = existing_cols_in_df[idx]
                if original_col_name.endswith("_fmt"):
                    original_col_name = original_col_name[:-4] 
            except ValueError:
                pass

            if original_col_name and original_col_name in df.columns and pd.api.types.is_numeric_dtype(df[original_col_name]):
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: pd.to_numeric(
                        x.astype(str).str.replace(r'[^\d.,-]', '', regex=True).str.replace(',', '.', regex=False),
                        errors='coerce'
                    ).fillna(-float('inf') if st.session_state.sort_direction == "asc" else float('inf'))
                )
            else:
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: x.astype(str).str.lower()
                )
    
    # Formatage des totaux pour l'affichage
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)

    # Génération du CSS pour les largeurs et alignements de colonnes du tableau principal
    css_col_widths = ""
    width_specific_cols = {
        "Ticker": "80px",
        "Nom": "200px",
        "Catégorie": "100px",
        "Devise": "60px",
        "Signal": "100px",
        "Action": "150px",
        "Justification": "200px",
    }
    
    left_aligned_labels = ["Ticker", "Nom", "Catégorie", "Devise", "Signal", "Action", "Justification"] 

    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1 
        
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}\n"
        else:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 100px; }}\n"
        
        if label in left_aligned_labels:
            css_col_widths += f".portfolio-table td:nth-child({col_idx}) {{ text-align: left !important; white-space: normal; }}\n" 
            css_col_widths += f".portfolio-table th:nth-child({col_idx}) {{ text-align: left !important; }}\n" 
        else: 
            css_col_widths += f".portfolio-table td:nth-child({col_idx}) {{ text-align: right !important; }}\n" 
            css_col_widths += f".portfolio-table th:nth-child({col_idx}) {{ text-align: right !important; }}\n" 

    # Construction du HTML du tableau
    html_code = f"""
    <style>
        .scroll-wrapper {{
            overflow-x: auto !important;
            overflow-y: auto;
            max-height: 500px;
            max-width: none !important;
            width: auto;
            display: block;
            position: relative;
        }}
        .portfolio-table {{
            min-width: 2200px; 
            border-collapse: collapse;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        .portfolio-table th {{
            background: #363636;
            color: white;
            padding: 8px;
            text-align: center;
            border: none;
            position: sticky;
            top: 0;
            z-index: 2;
            font-size: 12px;
            box-sizing: border-box;
            cursor: pointer; 
        }}
        .portfolio-table td {{
            padding: 6px;
            text-align: right; 
            border: none;
            font-size: 11px;
            white-space: nowrap; 
        }}
        {css_col_widths} 

        .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
        .total-row td {{
            background: #A49B6D;
            color: white;
            font-weight: bold;
        }}
        
        /* Styles pour le tableau de synthèse par catégorie */
        .category-summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin-top: 20px;
        }}
        .category-summary-table th {{
            background: #363636;
            color: white;
            padding: 8px;
            text-align: center;
            border: 1px solid #ddd;
            font-size: 12px;
        }}
        .category-summary-table td {{
            padding: 6px;
            border: 1px solid #ddd;
            font-size: 11px;
            white-space: nowrap;
        }}
        .category-summary-table tr:nth-child(even) {{ background: #efefef; }}
        .category-summary-table .text-align-left {{
            text-align: left !important;
        }}
        .category-summary-table .text-align-right {{
            text-align: right !important;
        }}
    </style>
    <div class="scroll-wrapper">
        <table class="portfolio-table">
            <thead><tr>
    """

    # Ajout des en-têtes de colonnes avec icônes de tri
    for lbl in df_disp.columns:
        sort_icon = ""
        if st.session_state.sort_column == lbl:
            sort_icon = " ▲" if st.session_state.sort_direction == "asc" else " ▼"
        
        html_code += f'<th id="sort-{safe_escape(lbl)}">{safe_escape(lbl)}{sort_icon}</th>'

    html_code += """
            </tr></thead>
            <tbody>
    """

    # Ajout des lignes de données
    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    # Ajout de la ligne des totaux
    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    
    total_cols_mapping = {
        "Valeur Acquisition": total_valeur_str,
        "Valeur Actuelle": total_actuelle_str,
        "Valeur H52": total_h52_str,
        "Valeur LT": total_lt_str
    }

    for display_label, total_value_str in total_cols_mapping.items():
        if display_label in df_disp.columns:
            try:
                idx = list(df_disp.columns).index(display_label)
                total_row_cells[idx] = safe_escape(total_value_str)
            except ValueError:
                pass

    if num_cols_displayed > 0:
        total_row_cells[0] = f"TOTAL ({safe_escape(devise_cible)})"

    html_code += "<tr class='total-row'>"
    for cell_content in total_row_cells:
        html_code += f"<td>{cell_content}</td>"
    html_code += "</tr>"

    html_code += """
            </tbody>
        </table>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.portfolio-table th').forEach(function(header) {
                header.addEventListener('click', function() {
                    const columnLabel = this.id.replace('sort-', '');
                    window.parent.postMessage(JSON.stringify({
                        streamlit: {
                            type: 'setComponentValue',
                            args: ['sort_event', {column: columnLabel}],
                        },
                    }), '*');
                });
            });
        });
    </script>
    """
    
    components.html(html_code, height=600, scrolling=True)

    st.session_state.df = df 

    return total_valeur, total_actuelle, total_h52, total_lt


def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """
    Affiche la synthèse globale du portefeuille, y compris les métriques clés et le nouveau
    tableau de répartition par catégorie avec les objectifs.
    """
    devise_cible = st.session_state.get("devise_cible", "EUR")

    if total_valeur is None:
        st.info("Veuillez importer un fichier Excel pour voir la synthèse de votre portefeuille.")
        return

    # Affichage des métriques clés (Valeur d'Acquisition, Actuelle, Gain/Perte)
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
        h52_display = format_fr(total_h52, 2) if pd.notna(total_h52) else "N/A"
        lt_display = format_fr(total_lt, 2) if pd.notna(total_lt) else "N/A"
        st.metric(
            label=f"**Valeur H52 / LT ({devise_cible})**",
            value=f"{h52_display} / {lt_display} {devise_cible}"
        )
    st.markdown("---")


    # --- Nouveau Tableau de Répartition par Catégorie ---
    st.markdown("#### Répartition et Objectifs par Catégorie")

    # Définition des allocations cibles par catégorie
    target_allocations = {
        "Minières": 0.41,
        "Asie": 0.25,
        "Energie": 0.25, # Changed from "Énergie" to "Energie"
        "Matériaux": 0.01,
        "Devises": 0.08,
        "Crypto": 0.00,
        "Autre": 0.00 
    }
    
    # Définir la catégorie de référence pour le calcul de l'ajustement
    REFERENCE_CATEGORY = "Minières" 

    if "df" in st.session_state and st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df.copy()
        
        if 'Catégorie' not in df.columns:
            st.error("ERREUR : La colonne 'Catégorie' est manquante dans le DataFrame pour la synthèse. "
                     "Vérifiez que votre fichier contient une colonne nommée 'Categories' et que "
                     "la fonction 'afficher_portefeuille' la traite correctement.")
            st.info(f"Colonnes disponibles : {df.columns.tolist()}") 
            return

        portfolio_total_value = total_actuelle 
        
        # S'assurer que le portfolio_total_value n'est pas zéro pour éviter division par zéro
        if portfolio_total_value == 0:
            st.info("La valeur totale actuelle du portefeuille est de 0. Impossible de calculer la répartition par catégorie ou l'ajustement.")
            # Afficher un tableau vide ou avec des zéros si désiré, mais les calculs suivants ne seraient pas significatifs.
            df_allocation = pd.DataFrame(columns=[
                "Catégorie", "Valeur Actuelle", "Part Actuelle (%)", 
                "Cible (%)", "Écart à l'objectif (%)", f"Ajustement Nécessaire ({devise_cible})"
            ])
            st.dataframe(df_allocation, use_container_width=True, hide_index=True)
            return


        df['Valeur_Actuelle_conv'] = pd.to_numeric(df['Valeur_Actuelle_conv'], errors='coerce').fillna(0)
        
        category_values = df.groupby('Catégorie')['Valeur_Actuelle_conv'].sum(skipna=True) # sum(skipna=True) ici aussi
        
        # --- Calcul des valeurs de référence pour l'ajustement ---
        valeur_totale_reference = category_values.get(REFERENCE_CATEGORY, 0.0)
        pourcentage_cible_reference = target_allocations.get(REFERENCE_CATEGORY, 0.0)

        ideal_portfolio_total = 0.0
        if pourcentage_cible_reference > 0:
            ideal_portfolio_total = valeur_totale_reference / pourcentage_cible_reference
        elif pourcentage_cible_reference == 0 and valeur_totale_reference > 0:
            st.warning(f"La catégorie de référence '{REFERENCE_CATEGORY}' a une valeur positive ({format_fr(valeur_totale_reference, 2)} {devise_cible}) mais un objectif de 0%. L'ajustement ne peut pas être basé sur cette référence pour les autres catégories.")
            ideal_portfolio_total = 0.0 
        
        results_data = []

        all_relevant_categories = sorted(list(set(target_allocations.keys()) | set(category_values.index.tolist())))
        
        for category in all_relevant_categories:
            target_pct = target_allocations.get(category, 0.0) 
            current_value_cat = category_values.get(category, 0.0) 
            current_pct = (current_value_cat / portfolio_total_value) if portfolio_total_value > 0 else 0.0

            deviation_pct = current_pct - target_pct
            
            value_to_adjust = 0.0
            if ideal_portfolio_total > 0: # Si nous avons une base de référence valide
                # Ajustement=(Valeur Total Minière / Pourcentage Cible Minière * Pourcentage Cible de la catégorie) - Valeur Actuelle Catégorie
                target_value_based_on_reference = ideal_portfolio_total * target_pct
                value_to_adjust = target_value_based_on_reference - current_value_cat
            elif target_pct == 0 and current_value_cat > 0:
                # Si l'objectif est 0% mais qu'il y a une valeur, l'ajustement est de retirer la valeur actuelle.
                value_to_adjust = -current_value_cat
            # Sinon (ideal_portfolio_total est 0 et target_pct est 0, ou ideal_portfolio_total est 0 mais target_pct > 0)
            # value_to_adjust reste 0, ou peut être np.nan si on veut indiquer que l'ajustement n'est pas calculable.
            # Pour l'instant, on laisse 0 si ideal_portfolio_total est 0, cela signifie "pas d'ajustement calculé par cette méthode".
            

            valeur_pour_atteindre_objectif_str = ""
            if pd.notna(value_to_adjust):
                valeur_pour_atteindre_objectif_str = f"{format_fr(value_to_adjust, 2)} {devise_cible}"
            else:
                valeur_pour_atteindre_objectif_str = "N/A" # Si le calcul de l'ajustement est NaN

            results_data.append({
                "Catégorie": category,
                "Valeur Actuelle": f"{format_fr(current_value_cat, 2)} {devise_cible}", 
                "Part Actuelle (%)": f"{format_fr(current_pct * 100, 2)} %", 
                "Cible (%)": f"{format_fr(target_pct * 100, 2)} %", 
                "Écart à l'objectif (%)": f"{format_fr(deviation_pct * 100, 2)} %", 
                f"Ajustement Nécessaire ({devise_cible})": valeur_pour_atteindre_objectif_str
            })

        df_allocation = pd.DataFrame(results_data)
        
        # Tri du DataFrame pour une meilleure lisibilité (toujours par le numérique)
        df_allocation['Part Actuelle (%)_numeric'] = df_allocation['Part Actuelle (%)'].str.replace(' %', '').str.replace(',', '.').astype(float)
        df_allocation = df_allocation.sort_values(by='Part Actuelle (%)_numeric', ascending=False)
        df_allocation = df_allocation.drop(columns=['Part Actuelle (%)_numeric'])

        # --- Affichage du tableau de synthèse avec HTML personnalisé pour le style ---
        summary_html_code = """
        <table class="category-summary-table">
            <thead>
                <tr>
                    <th class="text-align-left">Catégorie</th>
                    <th class="text-align-right">Valeur Actuelle</th>
                    <th class="text-align-right">Part Actuelle (%)</th>
                    <th class="text-align-right">Cible (%)</th>
                    <th class="text-align-right">Écart à l'objectif (%)</th>
                    <th class="text-align-right">Ajustement Nécessaire</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for index, row in df_allocation.iterrows():
            summary_html_code += "<tr>"
            summary_html_code += f"<td class='text-align-left'>{safe_escape(row['Catégorie'])}</td>"
            summary_html_code += f"<td class='text-align-right'>{safe_escape(row['Valeur Actuelle'])}</td>"
            summary_html_code += f"<td class='text-align-right'>{safe_escape(row['Part Actuelle (%)'])}</td>"
            summary_html_code += f"<td class='text-align-right'>{safe_escape(row['Cible (%)'])}</td>"
            summary_html_code += f"<td class='text-align-right'>{safe_escape(row['Écart à l'objectif (%)'])}</td>"
            summary_html_code += f"<td class='text-align-right'>{safe_escape(row[f'Ajustement Nécessaire ({devise_cible})'])}</td>"
            summary_html_code += "</tr>"
        
        summary_html_code += """
            </tbody>
        </table>
        """
        
        components.html(summary_html_code, height=df_allocation.shape[0] * 35 + 100, scrolling=False) # Ajuste la hauteur
        
    else:
        st.info("Le DataFrame de votre portefeuille n'est pas disponible ou ne contient pas la colonne 'Catégorie' pour calculer la répartition.")
        st.warning("Veuillez importer votre portefeuille et vérifier la présence de la colonne 'Categories' dans votre fichier source.")
