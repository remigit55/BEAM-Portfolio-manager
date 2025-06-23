# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données.
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

# --- Fonction de conversion de devise ---
def convertir(val, source_devise, devise_cible, fx_rates):
    """
    Convertit une valeur d'une devise source vers la devise cible en utilisant les taux de change fournis.
    Retourne la valeur originale et un taux de 1.0 si le taux de change est manquant ou nul.
    Retourne la valeur convertie et le taux utilisé.
    """
    if pd.isnull(val):
        return np.nan, np.nan # Retourne NaN pour la valeur et le taux si la valeur est NaN

    source_devise = str(source_devise).upper()
    devise_cible = str(devise_cible).upper()
    
    if source_devise == devise_cible:
        return val, 1.0 # Si c'est la même devise, pas de conversion, taux = 1.0

    # Correction ici : Utilise la devise source comme clé pour la recherche du taux
    # Compatible avec le data_fetcher.py utilisant yfinance qui renvoie des clés comme "USD"
    fx_key = source_devise 
    raw_taux = fx_rates.get(fx_key)
    
    try:
        taux_scalar = float(raw_taux)
    except (TypeError, ValueError):
        taux_scalar = np.nan

    if pd.isna(taux_scalar) or taux_scalar == 0:
        return val, np.nan # Retourne la valeur non convertie si le taux est manquant
    
    return val * taux_scalar, taux_scalar


def afficher_portefeuille():
    """
    Affiche le portefeuille de l'utilisateur, gère les calculs et l'affichage.
    Récupère les données externes via des fonctions dédiées.
    Retourne les totaux convertis pour la synthèse.
    """
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return None, None, None, None, None # Ajout d'un 5ème None pour df_repartition si besoin

    df = st.session_state.df.copy()

    # Renommer la colonne "LT" en "Objectif_LT" si elle existe et "Objectif_LT" n'existe pas
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    fx_rates = fetch_fx_rates(devise_cible)

    # Nettoyage et conversion des colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Calcul des valeurs
    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]
    else:
        df["Valeur"] = np.nan

    # --- NOUVELLE GESTION DE LA COLONNE CATÉGORIE ---
    st.write("DEBUG (afficher_portefeuille): Colonnes du DataFrame avant traitement Catégorie:", df.columns.tolist())
    st.write("DEBUG (afficher_portefeuille): Nombre de colonnes:", len(df.columns))

    if "Categories" in df.columns:
        # Renommer "Categories" en "Catégorie" (avec accent et sans 's')
        df.rename(columns={"Categories": "Catégorie"}, inplace=True)
        # Assurer que la colonne est de type string et remplir les NaN/vides
        df["Catégorie"] = df["Catégorie"].astype(str).str.strip().replace("", np.nan).fillna("Non classé")
        st.write("DEBUG (afficher_portefeuille): Contenu de la colonne 'Categories' (renommée en 'Catégorie') (premières lignes):")
        st.dataframe(df["Catégorie"].head())
    elif "Catégorie" in df.columns:
        # Si la colonne est déjà nommée "Catégorie", assurez-vous qu'elle est traitée
        df["Catégorie"] = df["Catégorie"].astype(str).str.strip().replace("", np.nan).fillna("Non classé")
        st.write("DEBUG (afficher_portefeuille): Contenu de la colonne 'Catégorie' (premières lignes):")
        st.dataframe(df["Catégorie"].head())
    else:
        # Si ni "Categories" ni "Catégorie" n'existent, créer une colonne "Non classé"
        df["Catégorie"] = "Non classé"
    
    st.write("DEBUG (afficher_portefeuille): Colonne 'Catégorie' créée/traitée. Contenu unique:", df["Catégorie"].unique())
    st.write("DEBUG (afficher_portefeuille): Le DataFrame contient bien la colonne 'Catégorie' ?", "Catégorie" in df.columns)
    # --- FIN NOUVELLE GESTION DE LA COLONNE CATÉGORIE ---


    # Déterminer la colonne Ticker (Tickers est un fallback)
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    # Cache pour les données Yahoo Finance
    if "ticker_data_cache" not in st.session_state:
        st.session_state.ticker_data_cache = {}

    # Récupération des données Yahoo Finance
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().unique()
        for ticker in unique_tickers:
            if ticker not in st.session_state.ticker_data_cache:
                st.session_state.ticker_data_cache[ticker] = fetch_yahoo_data(ticker)
        
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))
    else:
        df["shortName"] = ""
        df["currentPrice"] = np.nan
        df["fiftyTwoWeekHigh"] = np.nan

    df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    # Traitement de l'objectif long terme
    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = np.nan
    else:
        df["Objectif_LT"] = (
            df["Objectif_LT"]
              .astype(str)
              .str.replace(" ", "", regex=False)
              .str.replace(",", ".", regex=False)
        )
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]

    # Cache pour les résultats Momentum
    if "momentum_results_cache" not in st.session_state:
        st.session_state.momentum_results_cache = {}
            
    # Récupération des données Momentum
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers_for_momentum = df[ticker_col].dropna().unique()
        for ticker in unique_tickers_for_momentum:
            if ticker not in st.session_state.momentum_results_cache:
                st.session_state.momentum_results_cache[ticker] = fetch_momentum_data(ticker)
        
        df["Last Price"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Last Price", np.nan))
        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Signal", ""))
        df["Action"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
        df["Justification"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Justification", ""))
    else:
        df["Last Price"] = np.nan
        df["Momentum (%)"] = np.nan
        df["Z-Score"] = np.nan
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""

    # --- DEPLACÉ ICI : APPLICATION DES CONVERSIONS DE DEVISES ---
    # Ces colonnes doivent exister avant d'être formatées
    df["Devise"] = df["Devise"].fillna("EUR").astype(str).str.upper() # S'assurer que la colonne Devise existe et est en majuscules

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"], devise_cible, fx_rates)[0], axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"], devise_cible, fx_rates)[0], axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"], devise_cible, fx_rates)[0], axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"], devise_cible, fx_rates)[0], axis=1)
    # --- FIN DU DEPLACEMENT ---


    # Formatage des colonnes (inclut maintenant les colonnes converties)
    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("Valeur", 2), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Valeur_H52", 2), ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4), ("Valeur_LT", 2), 
        ("Momentum (%)", 2), ("Z-Score", 2),
        # LIGNES POUR LES VALEURS CONVERTIES
        ("Valeur_conv", 2),
        ("Valeur_Actuelle_conv", 2),
        ("Valeur_H52_conv", 2),
        ("Valeur_LT_conv", 2)
    ]:
        if col_name in df.columns: # Cette condition est maintenant plus fiable car les colonnes _conv existent
            df[f"{col_name}_fmt"] = df[col_name].map(lambda x: format_fr(x, dec_places))
            

    # Calcul des totaux convertis pour la synthèse
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Définition des colonnes à afficher et de leurs libellés
    # Inclut maintenant les colonnes converties
    cols = [
        ticker_col, "shortName", "Catégorie", "Devise",
        "Quantité_fmt", "Acquisition_fmt", "Valeur_fmt", # Valeur originale
        "Valeur_conv_fmt", # NOUVEAU : Valeur d'Acquisition convertie
        "currentPrice_fmt", "Valeur_Actuelle_fmt", # Valeur Actuelle originale
        "Valeur_Actuelle_conv_fmt", # NOUVEAU : Valeur Actuelle convertie
        "fiftyTwoWeekHigh_fmt", "Valeur_H52_fmt", # Valeur H52 originale
        "Valeur_H52_conv_fmt", # NOUVEAU : Valeur H52 convertie
        "Objectif_LT_fmt", "Valeur_LT_fmt", # Valeur LT originale
        "Valeur_LT_conv_fmt", # NOUVEAU : Valeur LT convertie
        "Momentum (%)_fmt", "Z-Score_fmt",
        "Signal", "Action", "Justification"
    ]
    labels = [
        "Ticker", "Nom", "Catégorie", "Devise",
        "Quantité", "Prix d'Acquisition", "Valeur (Org.)", # Libellé ajusté
        f"Valeur Acq. ({devise_cible})", # NOUVEAU libellé
        "Prix Actuel", "Valeur Actuelle (Org.)", # Libellé ajusté
        f"Valeur Act. ({devise_cible})", # NOUVEAU libellé
        "Haut 52 Semaines", "Valeur H52 (Org.)", # Libellé ajusté
        f"Valeur H52 ({devise_cible})", # NOUVEAU libellé
        "Objectif LT", "Valeur LT (Org.)", # Libellé ajusté
        f"Valeur LT ({devise_cible})", # NOUVEAU libellé
        "Momentum (%)", "Z-Score",
        "Signal", "Action", "Justification"
    ]

    # Filtrage des colonnes existantes
    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        # Pour le ticker_col, s'assurer qu'il est valide et existe
        if col_name == ticker_col and ticker_col is not None and ticker_col in df.columns:
            existing_cols_in_df.append(ticker_col)
            existing_labels.append(labels[i])
        # Pour les colonnes formatées (_fmt)
        elif col_name.endswith("_fmt"):
            base_col_name = col_name[:-4] # Enlever '_fmt'
            # Vérifier si la colonne originale (non formatée) existe
            # Ou si la colonne formatée a été directement créée (cas des _conv_fmt)
            if base_col_name in df.columns or col_name in df.columns: # Vérifier les deux cas
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
        # Pour les autres colonnes (non _fmt)
        elif col_name in df.columns:
            existing_cols_in_df.append(col_name)
            existing_labels.append(labels[i])
            
    if not existing_cols_in_df:
        st.warning("Aucune colonne de données valide à afficher.")
        return total_valeur, total_actuelle, total_h52, total_lt, df # Retourne df même vide pour la catégorie mix

    # Créer le DataFrame à afficher avec les colonnes sélectionnées
    df_disp = df[existing_cols_in_df].copy()
    df_disp.columns = existing_labels

    # Gestion du tri des colonnes
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
                    # Tenter de retrouver la colonne numérique sous-jacente pour le tri numérique
                    original_col_name = original_col_name.replace("_fmt", "")
                
                # Prioriser la colonne numérique si elle existe dans le df original
                if original_col_name in df.columns and pd.api.types.is_numeric_dtype(df[original_col_name]):
                    # Utiliser la colonne numérique pour le tri
                    df_disp = df_disp.sort_values(
                        by=sort_col_label,
                        ascending=(st.session_state.sort_direction == "asc"),
                        key=lambda x: df[original_col_name] # Trie sur la colonne numérique originale
                    )
                else:
                    # Trie alphabétique si ce n'est pas numérique ou si la colonne numérique n'est pas trouvée
                    df_disp = df_disp.sort_values(
                        by=sort_col_label,
                        ascending=(st.session_state.sort_direction == "asc"),
                        key=lambda x: x.astype(str).str.lower()
                    )
            except ValueError:
                # Si le libellé de tri n'est pas trouvé, revenir au tri alphabétique par défaut
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

    # Styles CSS pour le tableau
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
    
    left_aligned_labels = ["Ticker", "Nom", "Catégorie", "Signal", "Action", "Justification"]
    left_align_selectors = []

    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1 # nth-child est 1-basé
        
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}\n"
        else:
            # Largeur par défaut pour les autres colonnes
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 120px; }}\n" # Augmenté pour les nouvelles colonnes
        
        if label in left_aligned_labels:
            left_align_selectors.append(f"td:nth-child({col_idx})")

    if left_align_selectors:
        css_col_widths += f".portfolio-table {', '.join(left_align_selectors)} {{ text-align: left; white-space: normal; }}\n"

    # Construction du code HTML pour le tableau
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
        min-width: 2500px; /* Augmenté pour les nouvelles colonnes */
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
    </style>
    <div class="scroll-wrapper">
      <table class="portfolio-table">
        <thead><tr>
    """

    # Entêtes de colonne avec gestion du tri
    for lbl in df_disp.columns:
        col_name_for_sort = lbl
        is_sortable = "true"
        
        # Le tri sera basé sur le libellé affiché dans le HTML
        # Le JavaScript gérera le renvoi de ce libellé
        html_code += f'<th id="sort-{col_name_for_sort}" data-sortable="{is_sortable}" style="cursor:pointer;">'
        html_code += f'{safe_escape(lbl)}'
        if st.session_state.sort_column == lbl:
            html_code += ' &#x25B2;' if st.session_state.sort_direction == "asc" else ' &#x25BC;'
        html_code += '</th>'

    html_code += """
        </tr></thead>
        <tbody>
    """

    # Lignes de données
    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    # Ligne Total
    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    
    # Mapping des totaux aux libellés d'affichage corrects
    total_cols_mapping = {
        f"Valeur Acq. ({devise_cible})": total_valeur_str,
        f"Valeur Act. ({devise_cible})": total_actuelle_str,
        f"Valeur H52 ({devise_cible})": total_h52_str,
        f"Valeur LT ({devise_cible})": total_lt_str
    }

    # Remplir les cellules de la ligne total
    for display_label, total_value_str in total_cols_mapping.items():
        if display_label in df_disp.columns:
            idx = list(df_disp.columns).index(display_label)
            total_row_cells[idx] = safe_escape(total_value_str)

    # La première cellule de la ligne total
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
            document.querySelectorAll('.portfolio-table th[data-sortable="true"]').forEach(function(header) {
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

    # Retourne le DataFrame df qui contient toutes les colonnes nécessaires (y compris les _conv)
    # afin que afficher_repartition_categorie puisse l'utiliser.
    return total_valeur, total_actuelle, total_h52, total_lt, df 


def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
    """
    Affiche la synthèse globale du portefeuille.
    """
    devise_cible = st.session_state.get("devise_cible", "EUR")

    if total_valeur is None:
        st.info("Veuillez importer un fichier Excel pour voir la synthèse de votre portefeuille.")
        return

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
                delta=f"{format_fr(pourcentage_gain_perte, 2)}%"
            )
    else:
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}"
            )
    
    with col4:
        st.metric(
            label=f"**Objectif Long Terme ({devise_cible})**",
            value=f"{format_fr(total_lt, 2)} {devise_cible}"
        )


def afficher_repartition_categorie(df):
    """
    Affiche la répartition du portefeuille par catégorie.
    """
    st.write("DEBUG (afficher_repartition_categorie): Est-ce que df est None ?", df is None)
    st.write("DEBUG (afficher_repartition_categorie): La colonne 'Catégorie' existe ?", "Catégorie" in df.columns)
    if "Catégorie" in df.columns:
        st.write("DEBUG (afficher_repartition_categorie): Valeurs uniques dans 'Catégorie':", df["Catégorie"].unique())
    st.write("DEBUG (afficher_repartition_categorie): La colonne 'Valeur_Actuelle_conv' existe ?", "Valeur_Actuelle_conv" in df.columns)

    if df is not None and "Catégorie" in df.columns and "Valeur_Actuelle_conv" in df.columns:
        df_repartition = df.groupby("Catégorie")["Valeur_Actuelle_conv"].sum().reset_index()
        df_repartition.columns = ["Catégorie", "Valeur_Actuelle_conv"]
        total_valeur_actuelle = df_repartition["Valeur_Actuelle_conv"].sum()
        
        if total_valeur_actuelle > 0:
            df_repartition["Pourcentage (%)"] = (df_repartition["Valeur_Actuelle_conv"] / total_valeur_actuelle) * 100
        else:
            df_repartition["Pourcentage (%)"] = 0

        # Sort by percentage descending
        df_repartition = df_repartition.sort_values(by="Pourcentage (%)", ascending=False)

        # Formatting for display
        df_disp_cat = df_repartition.copy()
        df_disp_cat["Valeur_Actuelle_conv_fmt"] = df_disp_cat["Valeur_Actuelle_conv"].map(lambda x: format_fr(x, 2))
        df_disp_cat["Pourcentage (%)_fmt"] = df_disp_cat["Pourcentage (%)"].map(lambda x: format_fr(x, 2))

        devise_cible = st.session_state.get("devise_cible", "EUR")

        # HTML table generation
        html_code_cat = f"""
        <style>
            .scroll-wrapper-cat {{
                overflow-x: auto;
                overflow-y: auto;
                max-height: 400px; /* Adjusted height for category table */
                width: 100%;
                display: block;
            }}
            .category-table {{
                width: 100%;
                border-collapse: collapse;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .category-table th {{
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
            }}
            .category-table td {{
                padding: 6px;
                text-align: right;
                border: none;
                font-size: 11px;
                white-space: nowrap;
            }}
            .category-table tr:nth-child(even) {{ background: #efefef; }}
            .category-table td:first-child {{ text-align: left; }} /* Align category name to left */
            .category-table .total-cat-row td {{
                background: #A49B6D;
                color: white;
                font-weight: bold;
            }}
        </style>
        <div class="scroll-wrapper-cat">
            <table class="category-table">
                <thead>
                    <tr>
                        <th>Catégorie</th>
                        <th>Valeur Actuelle ({safe_escape(devise_cible)})</th>
                        <th>Pourcentage (%)</th>
                    </tr>
                </thead>
                <tbody>
        """
        for _, row in df_disp_cat.iterrows():
            html_code_cat += "<tr>"
            html_code_cat += f"<td>{safe_escape(row['Catégorie'])}</td>"
            html_code_cat += f"<td>{row['Valeur_Actuelle_conv_fmt']}</td>"
            html_code_cat += f"<td>{row['Pourcentage (%)_fmt']}%</td>" # Ajout du signe %
            html_code_cat += "</tr>"

        # Ligne Total pour la répartition par catégorie
        html_code_cat += "<tr class='total-cat-row'>"
        html_code_cat += f"<td>Total</td>"
        html_code_cat += f"<td>{format_fr(total_valeur_actuelle, 2)} {safe_escape(devise_cible)}</td>"
        html_code_cat += f"<td>100.00%</td>"
        html_code_cat += "</tr>"

        html_code_cat += """
                </tbody>
            </table>
        </div>
        """
        
        components.html(html_code_cat, height=450, scrolling=True)

    else:
        st.info("Le DataFrame de votre portefeuille n'est pas disponible ou ne contient pas la colonne 'Catégorie' pour calculer la répartition.")
        st.warning("Veuillez importer votre portefeuille et vérifier la présence de la colonne 'Categories' dans votre fichier source.")
