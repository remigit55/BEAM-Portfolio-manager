# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données.
# ASSUREZ-VOUS QUE CES IMPORTS CORRESPONDENT À VOS FICHIERS ET FONCTIONS RÉELS.
# Par exemple, si fetch_fx_rates est dans historical_data_fetcher.py et non data_fetcher.py, ajustez.
# J'ai ajusté l'import ici pour correspondre aux noms dans votre streamlit_app.py si c'est de là que viennent les fonctions.
# Si fetch_yahoo_data et fetch_momentum_data ne sont pas dans data_fetcher, ajustez les imports.
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

# --- Fonction de conversion de devise (déplacée ici pour être globale) ---
def convertir(val, source_devise, devise_cible, fx_rates):
    """
    Convertit une valeur d'une devise source vers la devise cible en utilisant les taux de change fournis.
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
        taux_scalar = np.nan

    if pd.isna(taux_scalar) or taux_scalar == 0:
        # st.warning(f"Taux de change pour {fx_key} non trouvé ou nul. Utilisation de 1:1 pour {source_devise}.")
        return val # Retourne la valeur non convertie si le taux est manquant ou nul
    
    return val * taux_scalar
# --- Fin de la fonction convertir ---


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

    # Utilisation des taux de change déjà en session_state ou récupérés
    # Il est préférable que `fetch_fx_rates` soit appelée une seule fois dans `streamlit_app.py`
    # et stockée dans st.session_state.fx_rates.
    # Pour l'instant, je vais laisser l'appel ici si `st.session_state.fx_rates` n'est pas déjà défini.
    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        # Récupération des devises uniques du DataFrame
        devises_uniques_df = df["Devise"].dropna().unique().tolist() if "Devise" in df.columns else []
        devises_a_fetch = list(set([devise_cible] + devises_uniques_df)) # Assurer que la devise cible est incluse
        st.session_state.fx_rates = fetch_fx_rates(devise_cible, devises_a_fetch) # Assurez-vous que fetch_fx_rates gère plusieurs devises cibles

    fx_rates = st.session_state.fx_rates # Utiliser les taux stockés

    # Nettoyage et conversion des colonnes numériques cruciales pour les calculs
    for col in ["Quantité", "Acquisition", "Objectif_LT"]: # 'Valeur Acquisition' n'est pas dans cette liste pour une raison, je le laisse comme dans votre code.
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0) # Remplir NaN avec 0 après conversion

    # Assurez-vous que la colonne 'Categories' est correctement lue
    # Au lieu de df.iloc[:, 5], nous utilisons directement le nom de la colonne 'Categories'.
    if "Categories" in df.columns: # C'est le nom de colonne discuté
        df["Catégorie"] = df["Categories"].astype(str).fillna("")
    else:
        st.warning("La colonne 'Categories' est introuvable dans votre fichier. La colonne 'Catégorie' sera vide.")
        df["Catégorie"] = ""

    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    # Initialisation des caches pour les données externes
    if "ticker_data_cache" not in st.session_state:
        st.session_state.ticker_data_cache = {}
    if "momentum_results_cache" not in st.session_state:
        st.session_state.momentum_results_cache = {}

    # Récupération des données Yahoo et Momentum
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().unique()
        for ticker in unique_tickers:
            # Récupération Yahoo Data
            if ticker not in st.session_state.ticker_data_cache:
                st.session_state.ticker_data_cache[ticker] = fetch_yahoo_data(ticker)
            
            # Récupération Momentum Data
            if ticker not in st.session_state.momentum_results_cache:
                st.session_state.momentum_results_cache[ticker] = fetch_momentum_data(ticker)
        
        # Application des données Yahoo aux colonnes
        df["shortName"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("shortName", f"https://finance.yahoo.com/quote/{t}"))
        df["currentPrice"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("currentPrice", np.nan))
        df["fiftyTwoWeekHigh"] = df[ticker_col].map(lambda t: st.session_state.ticker_data_cache.get(t, {}).get("fiftyTwoWeekHigh", np.nan))

        # Application des données Momentum aux colonnes
        df["Last Price"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Last Price", np.nan))
        df["Momentum (%)"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Momentum (%)", np.nan))
        df["Z-Score"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Z-Score", np.nan))
        df["Signal"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Signal", ""))
        df["Action"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Action", ""))
        df["Justification"] = df[ticker_col].map(lambda t: st.session_state.momentum_results_cache.get(t, {}).get("Justification", ""))
    else:
        # Initialiser les colonnes si aucun ticker n'est présent
        df["shortName"] = ""
        df["currentPrice"] = np.nan
        df["fiftyTwoWeekHigh"] = np.nan
        df["Last Price"] = np.nan
        df["Momentum (%)"] = np.nan
        df["Z-Score"] = np.nan
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""
    
    # Calcul des valeurs brutes avant conversion de devise
    df["Valeur Acquisition"] = df["Quantité"] * df["Acquisition"] # Assurez-vous que cette colonne existe et est calculée
    df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]


    # Convertir toutes les colonnes de valeur vers la devise cible
    # S'assurer que 'Devise' est bien nettoyée avant d'être utilisée pour la conversion
    df["Devise"] = df["Devise"].fillna(devise_cible).astype(str).str.upper()

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur Acquisition"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"], devise_cible, fx_rates), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"], devise_cible, fx_rates), axis=1)

    # Calcul des totaux après conversion
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Calcul et formatage des colonnes Gain/Perte pour l'affichage
    df['Gain/Perte'] = df['Valeur_Actuelle_conv'] - df['Valeur_conv']
    df['Gain/Perte (%)'] = np.where(
        df['Valeur_conv'] != 0,
        (df['Gain/Perte'] / df['Valeur_conv']) * 100,
        0
    )

    # Formatage des colonnes pour l'affichage dans le tableau HTML
    for col_name, dec_places in [
        ("Quantité", 0), ("Acquisition", 4), ("Valeur Acquisition", 2), ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4), ("Valeur_H52", 2), ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4), ("Valeur_LT", 2), ("Gain/Perte", 2),
        ("Momentum (%)", 2), ("Z-Score", 2), ("Gain/Perte (%)", 2)
    ]:
        if col_name in df.columns:
            # Pour les valeurs monétaires, ajoutez la devise cible au formatage
            if col_name in ["Valeur Acquisition", "Valeur_H52", "Valeur_Actuelle", "Valeur_LT", "Gain/Perte"]:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) + f" {devise_cible}")
            elif col_name == "Gain/Perte (%)" or col_name == "Momentum (%)":
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places) + " %")
            else:
                df[f"{col_name}_fmt"] = df[col_name].apply(lambda x: format_fr(x, dec_places))


    cols = [
        ticker_col, "shortName", "Catégorie", "Devise",
        "Quantité_fmt", "Acquisition_fmt", "Valeur Acquisition_fmt",
        "currentPrice_fmt", "Valeur_Actuelle_fmt", "Gain/Perte_fmt", "Gain/Perte (%)_fmt",
        "fiftyTwoWeekHigh_fmt", "Valeur_H52_fmt", "Objectif_LT_fmt", "Valeur_LT_fmt",
        "Last Price", "Momentum (%)_fmt", "Z-Score_fmt", # Last Price n'est pas formaté avec _fmt car ce n'est pas une valeur monétaire à convertir.
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
        # Handle ticker_col separately as it might not have _fmt
        if col_name == ticker_col and ticker_col is not None:
            if ticker_col in df.columns:
                existing_cols_in_df.append(ticker_col)
                existing_labels.append(labels[i])
        # Handle _fmt columns
        elif col_name.endswith("_fmt"):
            base_col_name = col_name[:-4]
            # Check if the base column or the _fmt column exists
            if f"{base_col_name}_fmt" in df.columns: # Check for the formatted column
                existing_cols_in_df.append(f"{base_col_name}_fmt")
                existing_labels.append(labels[i])
            elif base_col_name in df.columns: # Fallback to unformatted if formatted not available
                existing_cols_in_df.append(base_col_name)
                existing_labels.append(labels[i])
        # Handle other columns without _fmt
        elif col_name in df.columns:
            existing_cols_in_df.append(col_name)
            existing_labels.append(labels[i])
            
    if not existing_cols_in_df:
        st.warning("Aucune colonne de données valide à afficher.")
        return total_valeur, total_actuelle, total_h52, total_lt

    df_disp = df[existing_cols_in_df].copy()
    df_disp.columns = existing_labels

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
                    # Get the original non-formatted column name for sorting numerical values
                    original_col_name = original_col_name[:-4] 
            except ValueError:
                pass

            # Try to sort numerically if the original column was numeric
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
                # Fallback to string sort for non-numeric or missing original columns
                df_disp = df_disp.sort_values(
                    by=sort_col_label,
                    ascending=(st.session_state.sort_direction == "asc"),
                    key=lambda x: x.astype(str).str.lower()
                )
    
    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)

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
        col_idx = i + 1
        
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}\n"
        else:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 100px; }}\n"
        
        if label in left_aligned_labels:
            left_align_selectors.append(f"td:nth-child({col_idx})")

    if left_align_selectors:
        css_col_widths += f".portfolio-table {', '.join(left_align_selectors)} {{ text-align: left; white-space: normal; }}\n"


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
            min-width: 2200px; /* Conserver la largeur minimale si le tableau est large */
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
            cursor: pointer; /* Indiquer que les colonnes sont cliquables */
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

    for lbl in df_disp.columns:
        # Ajout de l'icône de tri si c'est la colonne actuellement triée
        sort_icon = ""
        if st.session_state.sort_column == lbl:
            sort_icon = " ▲" if st.session_state.sort_direction == "asc" else " ▼"
        
        # Ajout d'un id pour le clic JavaScript
        html_code += f'<th id="sort-{safe_escape(lbl)}">{safe_escape(lbl)}{sort_icon}</th>'

    html_code += """
            </tr></thead>
            <tbody>
    """

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    
    total_cols_mapping = {
        "Valeur Acquisition": total_valeur_str, # Ancien "Valeur"
        "Valeur Actuelle": total_actuelle_str,
        "Valeur H52": total_h52_str,
        "Valeur LT": total_lt_str
    }

    # Trouver les indices pour placer les totaux
    for display_label, total_value_str in total_cols_mapping.items():
        if display_label in df_disp.columns:
            try:
                idx = list(df_disp.columns).index(display_label)
                total_row_cells[idx] = safe_escape(total_value_str)
            except ValueError:
                pass # La colonne n'est pas affichée

    # Placer le libellé "TOTAL" dans la première colonne visible
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
        // JavaScript pour la gestion du tri
        document.addEventListener('DOMContentLoaded', function() {
            document.querySelectorAll('.portfolio-table th').forEach(function(header) {
                header.addEventListener('click', function() {
                    const columnLabel = this.id.replace('sort-', '');
                    // Send message back to Streamlit
                    window.parent.postMessage(JSON.stringify({
                        streamlit: {
                            type: 'setComponentValue',
                            // Utilisez une clé unique pour le composant HTML si plusieurs sont sur la page
                            // Ici, nous simulons un événement pour que Streamlit puisse réagir
                            // En production, il faudrait un mécanisme plus robuste comme un st.empty() + replace
                            // ou un composant personnalisé avec une sortie directe.
                            args: ['sort_event', {column: columnLabel}],
                        },
                    }), '*');
                });
            });
        });
    </script>
    """
    
    # Utilisez un st.empty() pour pouvoir rafraîchir le composant HTML avec de nouvelles données/tri
    # Ceci est une simplification. Dans une vraie application, le tri devrait être géré côté Python.
    # Pour que le JavaScript de tri fonctionne vraiment en interagissant avec Streamlit,
    # vous auriez besoin d'une approche plus complexe (ex: st_javascript ou un st.empty() mis à jour).
    # Ici, le JS est informatif, la logique de tri réelle est côté Python.
    components.html(html_code, height=600, scrolling=True)

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

    # --- Métriques existantes : Valeur Acquisition, Actuelle, Gain/Perte, H52/LT ---
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
                delta=f"{format_fr(pourcentage_gain_perte, 2)} %" # Ajout de l'espace avant %
            )
    else:
        with col3:
            st.metric(
                label="**Gain/Perte Total**",
                value=f"N/A {devise_cible}",
                delta="N/A %"
            )

    with col4:
        # Assurez-vous que total_h52 et total_lt sont numériques pour format_fr
        h52_display = format_fr(total_h52, 2) if pd.notna(total_h52) else "N/A"
        lt_display = format_fr(total_lt, 2) if pd.notna(total_lt) else "N/A"
        st.metric(
            label=f"**Valeur H52 / LT ({devise_cible})**",
            value=f"{h52_display} / {lt_display} {devise_cible}"
        )
    st.markdown("---")


    # --- Nouveau Tableau de Répartition par Catégorie (restauré) ---
    st.subheader("Répartition et Objectifs par Catégorie")

    # Définir les cibles
    target_allocations = {
        "Minières": 0.41,   # 41%
        "Asie": 0.25,       # 25%
        "Énergie": 0.25,    # 25%
        "Matériaux": 0.01,  # 1%
        "Devises": 0.08,    # 8%
        "Crypto": 0.00      # 0%
    }

    # Assurez-vous que le DataFrame est disponible et contient la colonne 'Categories'
    if "df" in st.session_state and st.session_state.df is not None and not st.session_state.df.empty:
        df = st.session_state.df.copy()
        
        # UTILISATION DE 'Catégorie' telle que créée dans afficher_portefeuille
        if 'Catégorie' not in df.columns:
            st.warning("La colonne 'Catégorie' est manquante dans votre portefeuille. Impossible de calculer la répartition par catégorie.")
            st.info("Veuillez vous assurer que votre fichier CSV/Excel contient une colonne nommée 'Categories' et que 'afficher_portefeuille' la traite correctement.")
            return

        # Vérifier si la valeur actuelle totale du portefeuille est non nulle
        portfolio_total_value = total_actuelle # Utilise la valeur totale calculée par afficher_portefeuille
        
        if portfolio_total_value <= 0:
            st.info("La valeur totale actuelle du portefeuille est de 0 ou moins. Impossible de calculer la répartition par catégorie de manière significative.")
            return

        # Calculer la valeur actuelle par catégorie.
        # Utiliser 'Valeur_Actuelle_conv' qui est déjà en devise cible.
        df['Valeur_Actuelle_conv'] = pd.to_numeric(df['Valeur_Actuelle_conv'], errors='coerce').fillna(0)
        
        # Groupement par la colonne 'Catégorie' (le nom formaté utilisé en interne)
        category_values = df.groupby('Catégorie')['Valeur_Actuelle_conv'].sum()
        
        results_data = []

        # Récupérer toutes les catégories uniques du DataFrame et les fusionner avec les catégories cibles
        all_relevant_categories = sorted(list(set(target_allocations.keys()) | set(category_values.index.tolist())))
        
        for category in all_relevant_categories:
            target_pct = target_allocations.get(category, 0.0) # 0% si pas de cible définie
            current_value_cat = category_values.get(category, 0)
            current_pct = (current_value_cat / portfolio_total_value) if portfolio_total_value > 0 else 0

            deviation_pct = current_pct - target_pct
            value_to_reach_target = None

            # Calcul spécifique pour "Minières"
            if category == "Minières":
                if current_pct < target_pct:
                    # Formule pour calculer X tel que (Valeur_Minières_Actuelle + X) / (Total_Portefeuille_Actuel + X) = Cible_Minières
                    # X = (cible * Total - Valeur_Minières) / (1 - cible)
                    # S'assurer que le dénominateur (1 - target_pct) n'est pas nul
                    if (1 - target_pct) != 0:
                        value_to_reach_target = (target_pct * portfolio_total_value - current_value_cat) / (1 - target_pct)
                        value_to_reach_target = max(0, value_to_reach_target) # Ne pas afficher de valeur négative
                    else:
                        value_to_reach_target = np.nan # Si la cible est 100%, calcul non applicable
                else:
                    value_to_reach_target = 0 # Si au-dessus ou à la cible, pas besoin d'ajouter
            
            valeur_pour_atteindre_objectif_str = ""
            if value_to_reach_target is not None and pd.notna(value_to_reach_target):
                valeur_pour_atteindre_objectif_str = f"{format_fr(value_to_reach_target, 2)} {devise_cible}"
            
            results_data.append({
                "Catégorie": category,
                "Part Actuelle (%)": format_fr(current_pct * 100, 2),
                "Cible (%)": format_fr(target_pct * 100, 2),
                "Écart à l'objectif (%)": format_fr(deviation_pct * 100, 2),
                f"Valeur pour atteindre objectif ({devise_cible})": valeur_pour_atteindre_objectif_str
            })

        df_allocation = pd.DataFrame(results_data)

        st.dataframe(df_allocation, use_container_width=True, hide_index=True)
    else:
        st.info("Le DataFrame de votre portefeuille n'est pas disponible ou ne contient pas la colonne 'Catégorie' pour calculer la répartition.")
        st.warning("Veuillez importer votre portefeuille et vérifier la présence de la colonne 'Categories' dans votre fichier source.")


# --- Ajoutez ici d'autres fonctions que vous auriez pu avoir dans votre portfolio_display.py ---
# def afficher_graphiques_synthese(df):
#    # Logique pour afficher des graphiques globaux (camembert, barres, etc.)
#    pass

# def afficher_autres_metrics(df):
#    # Logique pour d'autres KPIs spécifiques au portefeuille
#    pass
