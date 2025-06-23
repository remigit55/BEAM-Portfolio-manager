import streamlit as st
import pandas as pd
import numpy as np
import streamlit.components.v1 as components

from utils import safe_escape, format_fr
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

def calculer_reallocation_miniere(df, allocations_reelles, objectifs, colonne_cat="Catégories", colonne_valeur_conv="Valeur_Actuelle_conv"):
    if "Minières" not in objectifs:
        return None

    derive_abs = {}
    for cat, real_pct in allocations_reelles.items():
        if cat != "Minières" and cat in objectifs:
            target_pct = objectifs.get(cat, 0)
            derive_abs[cat] = abs(real_pct - target_pct)

    if not derive_abs:
        return None

    cat_ref = max(derive_abs, key=derive_abs.get)

    valeur_cat_ref = df[df[colonne_cat] == cat_ref][colonne_valeur_conv].sum()

    part_actuelle_cat_ref = allocations_reelles.get(cat_ref, 0.0)

    objectif_miniere_pct = objectifs["Minières"]
    valeur_actuelle_miniere = df[df[colonne_cat] == "Minières"][colonne_valeur_conv].sum()

    if part_actuelle_cat_ref == 0:
        return None

    total_theorique_portefeuille = valeur_cat_ref / part_actuelle_cat_ref

    valeur_cible_miniere = total_theorique_portefeuille * objectif_miniere_pct

    ajustement_necessaire = valeur_cible_miniere - valeur_actuelle_miniere

    return ajustement_necessaire

def convertir(val, source_devise, devise_cible, fx_rates):
    if pd.isnull(val):
        return np.nan, np.nan
    source_devise = str(source_devise).strip().upper()
    devise_cible = str(devise_cible).strip().upper()
    if source_devise == devise_cible:
        return val, 1.0
    fx_key = source_devise
    raw_taux = fx_rates.get(fx_key)
    try:
        taux_scalar = float(raw_taux)
    except (TypeError, ValueError):
        taux_scalar = np.nan
    if pd.isna(taux_scalar) or taux_scalar == 0:
        st.warning(f"Pas de conversion pour {source_devise} vers {devise_cible}: taux manquant ou invalide ({raw_taux}).")
        return val, np.nan
    return val * taux_scalar, taux_scalar

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None or st.session_state.df.empty:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return None, None, None, None
    df = st.session_state.df.copy()
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)
    devise_cible = st.session_state.get("devise_cible", "EUR")
    if "fx_rates" not in st.session_state or st.session_state.fx_rates is None:
        devises_uniques_df = df["Devise"].dropna().str.strip().str.upper().unique().tolist() if "Devise" in df.columns else []
        devises_a_fetch = list(set([devise_cible] + devises_uniques_df))
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
    fx_rates = st.session_state.fx_rates
    devises_uniques = df["Devise"].dropna().str.strip().str.upper().unique().tolist() if "Devise" in df.columns else []
    missing_rates = [devise for devise in devises_uniques if fx_rates.get(devise) is None and devise != devise_cible.upper()]
    if missing_rates:
        st.warning(f"Taux de change manquants pour les devises : {', '.join(missing_rates)}. Les valeurs ne seront pas converties pour ces devises.")
    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "Devise" in df.columns:
        df["Devise"] = df["Devise"].astype(str).str.strip().str.upper().fillna(devise_cible)
    else:
        st.error("Colonne 'Devise' absente. Utilisation de la devise cible par défaut.")
        df["Devise"] = devise_cible
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
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if "ticker_data_cache" not in st.session_state:
        st.session_state.ticker_data_cache = {}
    if "momentum_results_cache" not in st.session_state:
        st.session_state.momentum_results_cache = {}
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().unique()
        for ticker in unique_tickers:
            if ticker not in st.session_state.ticker_data_cache:
                st.session_state.ticker_data_cache[ticker] = fetch_yahoo_data(ticker)
            if ticker not in st.session_state.momentum_results_cache:
                st.session_state.momentum_results_cache[ticker] = fetch_momentum_data(ticker)
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
    df["Valeur Acquisition"] = df["Quantité"] * df["Acquisition"]
    df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]
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
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()
    df['Gain/Perte'] = df['Valeur_Actuelle_conv'] - df['Valeur_conv']
    df['Gain/Perte (%)'] = np.where(
        df['Valeur_conv'] != 0,
        (df['Gain/Perte'] / df['Valeur_conv']) * 100,
        0
    )
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
    cols = [
        ticker_col, "shortName", "Catégories", "Devise", 
        "Quantité_fmt", "Acquisition_fmt", 
        "Valeur Acquisition_fmt",
        "Valeur_conv",
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
    existing_cols_in_df = []
    existing_labels = []
    for i, col_name in enumerate(cols):
        if col_name == ticker_col and ticker_col is not None:
            if ticker_col in df.columns:
                existing_cols_in_df.append(ticker_col)
                existing_labels.append(labels[i])
        elif col_name.endswith("_fmt"):
            if col_name in df.columns:
                existing_cols_in_df.append(col_name)
                existing_labels.append(labels[i])
            else:
                base_col_name = col_name[:-4]
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
                df = df.sort_values(
                    by=original_col_name,
                    ascending=(st.session_state.sort_direction == "asc")
                )
                df_disp = df[existing_cols_in_df].copy()
                df_disp.columns = existing_labels
            else:
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
        "Catégories": "100px",  
        "Devise Source": "60px",
        "Valeur Acquisition (Source)": "120px",  
        "Taux FX (Source/Cible)": "100px",  
        "Signal": "100px",
        "Action": "150px",
        "Justification": "200px",
    }
    left_aligned_labels = ["Ticker", "Nom", "Catégories", "Signal", "Action", "Justification", "Devise Source"]
    for i, label in enumerate(df_disp.columns):
        col_idx = i + 1  
        if label in width_specific_cols:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: {width_specific_cols[label]}; }}"
        else:
            css_col_widths += f".portfolio-table th:nth-child({col_idx}), .portfolio-table td:nth-child({col_idx}) {{ width: 100px; }}"
        if label in left_aligned_labels:
            css_col_widths += f".portfolio-table td:nth-child({col_idx}) {{ text-align: left !important; white-space: normal; }}"
            css_col_widths += f".portfolio-table th:nth-child({col_idx}) {{ text-align: left !important; }}"
    html_code = f"""
    <style>
        .portfolio-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9em;
            text-align: right;
        }}
        .portfolio-table th, .portfolio-table td {{
            border: 1px solid #ddd;
            padding: 8px;
            white-space: nowrap;
        }}
        .portfolio-table th {{
            background-color: #f2f2f2;
            cursor: pointer;
        }}
        .portfolio-table th:hover {{
            background-color: #e0e0e0;
        }}
        .portfolio-table tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .portfolio-table tr:hover {{
            background-color: #f1f1f1;
        }}
        .total-row {{
            font-weight: bold;
            background-color: #e6e6e6;
        }}
        {css_col_widths}
    </style>
    <script>
        function sortTable(columnIndex, tableId) {{
            var table = document.getElementById(tableId);
            var rows = Array.from(table.rows).slice(1);
            var isAscending = true;
            var currentSortColumn = '{st.session_state.sort_column if "sort_column" in st.session_state else "None"}';
            var currentSortDirection = '{st.session_state.sort_direction if "sort_direction" in st.session_state else "asc"}';

            var header = table.rows[0].cells[columnIndex].innerText.replace(' ▲', '').replace(' ▼', '').trim();

            if (currentSortColumn === header) {{
                isAscending = (currentSortDirection === "desc");
            }}

            rows.sort(function(a, b) {{
                var aText = a.cells[columnIndex].innerText.trim();
                var bText = b.cells[columnIndex].innerText.trim();

                var aNum = parseFloat(aText.replace(/[^0-9.,-]+/g, '').replace(',', '.'));
                var bNum = parseFloat(bText.replace(/[^0-9.,-]+/g, '').replace(',', '.'));

                var comparison = 0;
                if (!isNaN(aNum) && !isNaN(bNum)) {{
                    comparison = aNum - bNum;
                }} else {{
                    comparison = aText.localeCompare(bText);
                }}

                return isAscending ? comparison : -comparison;
            }});

            while (table.rows.length > 1) {{
                table.deleteRow(1);
            }}
            rows.forEach(function(row) {{
                table.appendChild(row);
            }});

            var newSortDirection = isAscending ? "asc" : "desc";
            if (currentSortColumn === header && currentSortDirection === newSortDirection) {
                header = '';
                newSortDirection = 'asc';
            }

            var urlParams = new URLSearchParams(window.location.search);
            urlParams.set('sort_column', header);
            urlParams.set('sort_direction', newSortDirection);
            window.location.search = urlParams.toString();
        }}
    </script>
    <table class="portfolio-table" id="portfolioTable">
        <thead>
            <tr>
    """    for i, lbl in enumerate(df_disp.columns):
        sort_icon = ""
        if st.session_state.sort_column == lbl:
            sort_icon = " ▲" if st.session_state.sort_direction == "asc" else " ▼"
        html_code += f'<th onclick="sortTable({i}, \'portfolioTable\')">{safe_escape(lbl)}{sort_icon}</th>'
    html_code += """
            </tr>
        </thead>
        <tbody>
    """    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"
    html_code += """
        </tbody>
        <tfoot>
            <tr class="total-row">
    """    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    total_cols_mapping = {
        f"Valeur Acquisition ({devise_cible})": total_valeur_str,
        f"Valeur Actuelle ({devise_cible})": total_actuelle_str,
        f"Valeur H52 ({devise_cible})": total_h52_str,  
        f"Valeur LT ({devise_cible})": total_lt_str
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
    for cell_content in total_row_cells:
        html_code += f"<td>{cell_content}</td>"
    html_code += """
            </tr>
        </tfoot>
    </table>
    """    components.html(html_code, height=600, scrolling=True)
    st.session_state.df = df  
    return total_valeur, total_actuelle, total_h52, total_lt

def afficher_synthese_globale(total_valeur, total_actuelle, total_h52, total_lt):
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
        category_values = df.groupby('Catégories')['Valeur_Actuelle_conv'].sum()
        
        allocations_reelles_pct = {
            cat: (val / total_actuelle) if total_actuelle > 0 else 0.0
            for cat, val in category_values.items()
        }

        ecart_miniere = calculer_reallocation_miniere(df, allocations_reelles_pct, target_allocations, "Catégories", "Valeur_Actuelle_conv")

        if ecart_miniere is not None and abs(ecart_miniere) > 1e-2:
            st.markdown(f"🔁 Suggestion d'ajustement **Minières** : {format_fr(ecart_miniere, 2)} {devise_cible}", unsafe_allow_html=True)
            st.markdown("---")

        results_data = []
        all_relevant_categories = sorted(list(set(target_allocations.keys()) | set(category_values.index.tolist())))
        for category in all_relevant_categories:
            target_pct = target_allocations.get(category, 0.0)
            current_value_cat = category_values.get(category, 0.0)
            if pd.isna(current_value_cat):
                current_value_cat = 0.0
            current_pct = (current_value_cat / total_actuelle) if total_actuelle > 0 else 0.0
            
            target_value_for_category = target_pct * total_actuelle

            deviation_pct = (current_pct - target_pct)
            value_to_adjust = target_value_for_category - current_value_cat

            results_data.append({
                "Catégories": category,
                "Valeur Actuelle": current_value_cat,
                "Part Actuelle (%)": current_pct * 100,
                "Cible (%)": target_pct * 100,
                "Écart à l'objectif (%)": deviation_pct * 100,
                "Ajustement Nécessaire": value_to_adjust
            })
        df_allocation = pd.DataFrame(results_data)
        df_allocation = df_allocation.sort_values(by='Part Actuelle (%)', ascending=False)
        df_allocation["Valeur Actuelle_fmt"] = df_allocation["Valeur Actuelle"].apply(lambda x: f"{format_fr(x, 2)} {devise_cible}")
        df_allocation["Part Actuelle (%_fmt)"] = df_allocation["Part Actuelle (%)"].apply(lambda x: f"{format_fr(x, 2)} %")
        df_allocation["Cible (%_fmt)"] = df_allocation["Cible (%)"].apply(lambda x: f"{format_fr(x, 2)} %")
        df_allocation["Écart à l'objectif (%_fmt)"] = df_allocation["Écart à l'objectif (%)"].apply(lambda x: f"{format_fr(x, 2)} %")
        df_allocation[f"Ajustement Nécessaire_fmt"] = df_allocation["Ajustement Nécessaire"].apply(lambda x: f"{format_fr(x, 2)} {devise_cible}")
        cols_to_display = [
            "Catégories",
            "Valeur Actuelle_fmt",
            "Part Actuelle (%_fmt)",
            "Cible (%_fmt)",
            "Écart à l'objectif (%_fmt)",
            f"Ajustement Nécessaire_fmt"
        ]
        labels_for_display = [
            "Catégories",
            "Valeur Actuelle",
            "Part Actuelle (%)",
            "Cible (%)",
            "Écart à l'objectif (%)",
            f"Ajustement Nécessaire"
        ]
        df_disp_cat = df_allocation[cols_to_display].copy()
        df_disp_cat.columns = labels_for_display
        if "sort_column_cat" not in st.session_state:
            st.session_state.sort_column_cat = None
        if "sort_direction_cat" not in st.session_state:
            st.session_state.sort_direction_cat = "asc"
        if st.session_state.sort_column_cat:
            sort_col_label_cat = st.session_state.sort_column_cat
            if sort_col_label_cat in df_disp_cat.columns:
                original_col_for_sort = None
                if sort_col_label_cat == "Valeur Actuelle":
                    original_col_for_sort = "Valeur Actuelle"
                elif sort_col_label_cat == "Part Actuelle (%)":
                    original_col_for_sort = "Part Actuelle (%)"
                elif sort_col_label_cat == "Cible (%)":
                    original_col_for_sort = "Cible (%)"
                elif sort_col_label_cat == "Écart à l'objectif (%)":
                    original_col_for_sort = "Écart à l'objectif (%)"
                elif sort_col_label_cat == "Ajustement Nécessaire":
                    original_col_for_sort = "Ajustement Nécessaire"
                if original_col_for_sort and pd.api.types.is_numeric_dtype(df_allocation[original_col_for_sort]):
                    df_disp_cat = df_allocation.sort_values(
                        by=original_col_for_sort,
                        ascending=(st.session_state.sort_direction_cat == "asc")
                    )[cols_to_display]
                    df_disp_cat.columns = labels_for_display
                else:
                    df_disp_cat = df_disp_cat.sort_values(
                        by=sort_col_label_cat,
                        ascending=(st.session_state.sort_direction_cat == "asc"),
                        key=lambda x: x.astype(str).str.lower()
                    )
        css_col_widths_cat = ""
        width_specific_cols_cat = {
            "Catégories": "120px",
            "Valeur Actuelle": "120px",
            "Part Actuelle (%)": "100px",
            "Cible (%)": "80px",
            "Écart à l'objectif (%)": "120px",
            "Ajustement Nécessaire": "150px"
        }
        left_aligned_labels_cat = ["Catégories"]
        for i, label in enumerate(df_disp_cat.columns):
            col_idx = i + 1
            if label in width_specific_cols_cat:
                css_col_widths_cat += f".category-table th:nth-child({col_idx}), .category-table td:nth-child({col_idx}) {{ width: {width_specific_cols_cat[label]}; }}"
            else:
                css_col_widths_cat += f".category-table th:nth-child({col_idx}), .category-table td:nth-child({col_idx}) {{ width: auto; }}"
            if label in left_aligned_labels_cat:
                css_col_widths_cat += f".category-table td:nth-child({col_idx}) {{ text-align: left !important; white-space: normal; }}"
                css_col_widths_cat += f".category-table th:nth-child({col_idx}) {{ text-align: left !important; }}"
        html_code_cat = f"""
        <style>
            .category-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9em;
                text-align: right;
            }}
            .category-table th, .category-table td {{
                border: 1px solid #ddd;
                padding: 8px;
                white-space: nowrap;
            }}
            .category-table th {{
                background-color: #f2f2f2;
                cursor: pointer;
            }}
            .category-table th:hover {{
                background-color: #e0e0e0;
            }}
            .category-table tr:nth-child(even) {{
                background-color: #f9f9f9;
            }}
            .category-table tr:hover {{
                background-color: #f1f1f1;
            }}
            {css_col_widths_cat}
        </style>
        <script>
            function sortTableCat(columnIndex, tableId) {{
                var table = document.getElementById(tableId);
                var rows = Array.from(table.rows).slice(1);
                var isAscending = true;
                var currentSortColumn = '{st.session_state.sort_column_cat if "sort_column_cat" in st.session_state else "None"}';
                var currentSortDirection = '{st.session_state.sort_direction_cat if "sort_direction_cat" in st.session_state else "asc"}';
    
                var header = table.rows[0].cells[columnIndex].innerText.replace(' ▲', '').replace(' ▼', '').trim();
    
                if (currentSortColumn === header) {{
                    isAscending = (currentSortDirection === "desc");
                }}
    
                rows.sort(function(a, b) {{
                    var aText = a.cells[columnIndex].innerText.trim();
                    var bText = b.cells[columnIndex].innerText.trim();
    
                    var aNum = parseFloat(aText.replace(/[^0-9.,-]+/g, '').replace(',', '.'));
                    var bNum = parseFloat(bText.replace(/[^0-9.,-]+/g, '').replace(',', '.'));
    
                    var comparison = 0;
                    if (!isNaN(aNum) && !isNaN(bNum)) {{
                        comparison = aNum - bNum;
                    }} else {{
                        comparison = aText.localeCompare(bText);
                    }}
    
                    return isAscending ? comparison : -comparison;
                }});
    
                while (table.rows.length > 1) {{
                    table.deleteRow(1);
                }}
                rows.forEach(function(row) {{
                    table.appendChild(row);
                }});

                var newSortDirection = isAscending ? "asc" : "desc";
                if (currentSortColumn === header && currentSortDirection === newSortDirection) {
                    header = '';
                    newSortDirection = 'asc';
                }

                var urlParams = new URLSearchParams(window.location.search);
                urlParams.set('sort_column_cat', header);
                urlParams.set('sort_direction_cat', newSortDirection);
                window.location.search = urlParams.toString();
            }}
        </script>
        <table class="category-table" id="categoryTable">
            <thead>
                <tr>
"""        for i, lbl in enumerate(df_disp_cat.columns):
            sort_icon = ""
            if st.session_state.sort_column_cat == lbl:
                sort_icon = " ▲" if st.session_state.sort_direction_cat == "asc" else " ▼"
            html_code_cat += f'<th onclick="sortTableCat({i}, \'categoryTable\')">{safe_escape(lbl)}{sort_icon}</th>'
        html_code_cat += """
                </tr>
            </thead>
            <tbody>
"""        for _, row in df_disp_cat.iterrows():
            html_code_cat += "<tr>"
            for lbl in df_disp_cat.columns:
                val = row[lbl]
                val_str = safe_escape(str(val)) if pd.notnull(val) else ""
                html_code_cat += f"<td>{val_str}</td>"
            html_code_cat += "</tr>"
        html_code_cat += """
            </tbody>
        </table>
"""        components.html(html_code_cat, height=450, scrolling=True)
    else:
        st.info("Le DataFrame de votre portefeuille n'est pas disponible ou est vide. Veuillez importer votre portefeuille.")
