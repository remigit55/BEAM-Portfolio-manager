import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf # Assurez-vous que yfinance est installé: pip install yfinance

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

# Ajout d'un cache pour les taux de change pour améliorer la performance
@st.cache_data(ttl=3600) # Cache pendant 1 heure
def fetch_fx_rates(base="EUR"):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("rates", {})
    except Exception as e:
        print(f"Erreur lors de la récupération des taux : {e}")
        return {}

# Mise en cache des données Yahoo Finance pour éviter les appels répétés
@st.cache_data(ttl=900) # Cache pendant 15 minutes
def fetch_yahoo_data(t):
    t = str(t).strip().upper()
    # Utilisation d'un cache manuel pour gérer les cas où Yahoo retourne des infos incomplètes
    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    if t in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[t]
        if isinstance(cached, dict) and "shortName" in cached: # Vérifier que le cache contient des données valides
            return cached
        else: # Si les données sont invalides, les supprimer du cache et refetch
            del st.session_state.ticker_names_cache[t]
    
    try:
        # Utilisation de yfinance pour une meilleure robustesse
        ticker_obj = yf.Ticker(t)
        info = ticker_obj.info
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{t}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[t] = result
        time.sleep(0.05) # Petite pause pour respecter les limites d'API
        return result
    except Exception as e:
        # print(f"Erreur lors de la récupération des données Yahoo pour {t}: {e}") # Décommenter pour débug
        return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

# Mise en cache de l'analyse de momentum
@st.cache_data(ttl=3600) # Cache pendant 1 heure
def fetch_momentum_data(ticker, period="5y", interval="1wk"):
    try:
        data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if data.empty:
            return {
                "Momentum (%)": None,
                "Z-Score": None,
                "Signal": "",
                "Action": "",
                "Justification": ""
            }

        # yfinance.download avec auto_adjust=True renvoie souvent une seule colonne 'Close'
        close = data['Close']

        df_m = pd.DataFrame({'Close': close})
        df_m['MA_39'] = df_m['Close'].rolling(window=39).mean()
        df_m['Momentum'] = (df_m['Close'] / df_m['MA_39']) - 1
        # Calcul du Z-Score basé sur une fenêtre glissante
        df_m['Z_Momentum'] = (df_m['Momentum'] - df_m['Momentum'].rolling(10).mean()) / df_m['Momentum'].rolling(10).std()

        latest = df_m.iloc[-1]
        z = latest.get('Z_Momentum')
        m = latest.get('Momentum', 0) * 100

        if pd.isna(z):
            return {
                "Momentum (%)": None,
                "Z-Score": None,
                "Signal": "",
                "Action": "",
                "Justification": ""
            }

        if z > 2:
            signal = "🔥 Surchauffe"
            action = "Alléger / Prendre profits"
            reason = "Momentum extrême, risque de retournement"
        elif z > 1.5:
            signal = "↗ Fort"
            action = "Surveiller"
            reason = "Momentum soutenu, proche de surchauffe"
        elif z > 0.5:
            signal = "↗ Haussier"
            action = "Conserver / Renforcer"
            reason = "Momentum sain"
        elif z > -0.5:
            signal = "➖ Neutre"
            action = "Ne rien faire"
            reason = "Pas de signal exploitable"
        elif z > -1.5:
            signal = "↘ Faible"
            action = "Surveiller / Réduire si confirmé"
            reason = "Dynamique en affaiblissement"
        else:
            signal = "🧊 Survendu"
            action = "Acheter / Renforcer (si signal technique)"
            reason = "Purge excessive, possible bas de cycle"

        return {
            "Momentum (%)": round(m, 2),
            "Z-Score": round(z, 2),
            "Signal": signal,
            "Action": action,
            "Justification": reason
        }
    except Exception as e:
        # print(f"Erreur avec {ticker} pour l'analyse de momentum : {e}") # Décommenter pour débug
        return {
            "Momentum (%)": None,
            "Z-Score": None,
            "Signal": "",
            "Action": "",
            "Justification": ""
        }

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

    # Harmoniser le nom de la colonne pour l’objectif long terme
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")
    if "last_devise_cible" not in st.session_state:
        st.session_state.last_devise_cible = devise_cible
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
    elif st.session_state.last_devise_cible != devise_cible:
        st.session_state.last_devise_cible = devise_cible
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)

    fx_rates = st.session_state.get("fx_rates", {})

    # Normalisation numérique
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                       .str.replace(" ", "", regex=False)
                       .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else: # Créer la colonne si elle n'existe pas, pour éviter les erreurs plus tard
            df[col] = pd.NA

    # Calcul de la valeur
    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]
    else:
        df["Valeur"] = pd.NA


    # Ajout de la colonne Catégorie depuis la colonne F du CSV
    # Vérifie si le DataFrame a au moins 6 colonnes (index 5)
    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = "" # Crée une colonne vide si F n'existe pas

    # Récupération de shortName, Current Price et 52 Week High via Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    if ticker_col:
        # Filtrer les tickers valides pour les appels API
        valid_tickers = df[ticker_col].dropna().astype(str).str.strip().str.upper().unique()
        
        yahoo_results = {t: fetch_yahoo_data(t) for t in valid_tickers}
        momentum_results = {t: fetch_momentum_data(t) for t in valid_tickers}
        
        df["shortName"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("shortName"))
        df["currentPrice"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("currentPrice"))
        df["fiftyTwoWeekHigh"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("fiftyTwoWeekHigh"))
        
        df["Momentum (%)"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Momentum (%)"))
        df["Z-Score"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Z-Score"))
        df["Signal"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Signal"))
        df["Action"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Action"))
        df["Justification"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Justification"))
    else:
        # Initialiser les colonnes si aucun ticker n'est trouvé
        df["shortName"] = pd.NA
        df["currentPrice"] = pd.NA
        df["fiftyTwoWeekHigh"] = pd.NA
        df["Momentum (%)"] = pd.NA
        df["Z-Score"] = pd.NA
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    else:
        df["Valeur_H52"] = pd.NA
        
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = pd.NA

    # Conversion Objectif_LT et calcul de Valeur_LT
    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = pd.NA
    else:
        df["Objectif_LT"] = (
            df["Objectif_LT"]
            .astype(str)
            .str.replace(" ", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]
    
    # Formatage des colonnes numériques pour l'affichage
    def format_fr(x, dec):
        if pd.isnull(x) or x is None: return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    for col, dec in [
        ("Quantité", 0),
        ("Acquisition", 4),
        ("Valeur", 2),
        ("currentPrice", 4),
        ("fiftyTwoWeekHigh", 4),
        ("Valeur_H52", 2),
        ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4),
        ("Valeur_LT", 2),
        ("Momentum (%)", 2),
        ("Z-Score", 2)
    ]:
        if col in df.columns:
            # S'assurer que la colonne est numérique avant de la formater
            df[col] = pd.to_numeric(df[col], errors='coerce') 
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))
        else:
            df[f"{col}_fmt"] = "" # Créer la colonne formatée vide si l'originale n'existe pas

    # Conversion en devise cible
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise) or val is None: return 0
        if devise.upper() == devise_cible.upper(): return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    if "Devise" in df.columns:
        df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
        df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
        df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
        df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)
    else: # Si la colonne 'Devise' est manquante, assume que tout est dans la devise cible
        df["Valeur_conv"] = df["Valeur"].fillna(0)
        df["Valeur_Actuelle_conv"] = df["Valeur_Actuelle"].fillna(0)
        df["Valeur_H52_conv"] = df["Valeur_H52"].fillna(0)
        df["Valeur_LT_conv"] = df["Valeur_LT"].fillna(0)

    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Préparer les colonnes pour l'affichage (utilisez les labels définis)
    cols_to_display_internal = [
        ticker_col,
        "shortName",
        "Catégorie",
        "Devise",
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "Valeur_Actuelle_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Objectif_LT_fmt",
        "Valeur_LT_fmt",
        "Momentum (%)_fmt",
        "Z-Score_fmt",
        "Signal",
        "Action",
        "Justification"
    ]
    labels_display = [
        "Ticker",
        "Nom",
        "Catégorie",
        "Devise",
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Valeur Actuelle",
        "Haut 52 Semaines",
        "Valeur H52",
        "Objectif LT",
        "Valeur LT",
        "Momentum (%)",
        "Z-Score",
        "Signal",
        "Action",
        "Justification"
    ]

    # Filtrer les colonnes qui existent réellement dans df avant de créer df_disp
    final_cols_internal = []
    final_labels = []
    for internal_col, label in zip(cols_to_display_internal, labels_display):
        # Pour les colonnes formatées, vérifier l'existence de la colonne non formatée si nécessaire
        if internal_col.endswith('_fmt'):
            original_col = internal_col.replace('_fmt', '')
            if original_col in df.columns:
                final_cols_internal.append(internal_col)
                final_labels.append(label)
            elif internal_col in df.columns: # si la colonne _fmt existe directement
                final_cols_internal.append(internal_col)
                final_labels.append(label)
        elif internal_col in df.columns:
            final_cols_internal.append(internal_col)
            final_labels.append(label)
            
    df_disp = df[final_cols_internal].copy()
    df_disp.columns = final_labels


    # --- Gestion du tri via les query parameters de l'URL ---
    query_params = st.query_params
    sort_column_from_url = query_params.get("sort_column", None)
    sort_direction_from_url = query_params.get("sort_direction", "asc") # Default to asc

    if sort_column_from_url and sort_column_from_url in df_disp.columns:
        # Trouver la colonne originale non formatée pour le tri numérique
        original_sort_col = None
        for i, label in enumerate(labels_display):
            if label == sort_column_from_url:
                original_sort_col = cols_to_display_internal[i].replace("_fmt", "")
                break

        # Tenter de convertir en numérique si c'est une colonne de valeur/quantité
        is_numeric_sort = original_sort_col in [
            "Quantité", "Acquisition", "Valeur", "currentPrice", "Valeur_Actuelle",
            "fiftyTwoWeekHigh", "Valeur_H52", "Objectif_LT", "Valeur_LT",
            "Momentum (%)", "Z-Score"
        ]

        if is_numeric_sort and original_sort_col in df.columns:
            df_disp = df_disp.sort_values(
                by=sort_column_from_url,
                ascending=(sort_direction_from_url == "asc"),
                key=lambda x: pd.to_numeric(
                    df[original_sort_col], errors='coerce'
                ).reindex(x.index).fillna(
                    -float('inf') if sort_direction_from_url == 'asc' else float('inf')
                )
            )
        else:
            # Tri par texte pour les autres colonnes ou si la conversion numérique échoue
            df_disp = df_disp.sort_values(
                by=sort_column_from_url,
                ascending=(sort_direction_from_url == "asc"),
                key=lambda x: x.astype(str).str.lower()
            )

    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)

    # --- HTML pour la table ---
    # Récupérer les paramètres de tri actuels pour les passer au JS
    current_sort_col_js = safe_escape(sort_column_from_url if sort_column_from_url else "")
    current_sort_dir_js = safe_escape(sort_direction_from_url)

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
        min-width: 2200px; /* Assurez-vous que cette largeur est suffisante pour toutes les colonnes */
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
        cursor: pointer; /* Indique que l'en-tête est cliquable */
      }}
      .portfolio-table th:hover {{
        background: #4a4a4a;
      }}
      .portfolio-table td {{
        padding: 6px;
        text-align: right;
        border: none;
        font-size: 11px;
        white-space: nowrap;
      }}
      /* Styles pour l'alignement à gauche des colonnes spécifiques */
      .portfolio-table td:nth-child(1), /* Ticker */
      .portfolio-table td:nth-child(2), /* Nom */
      .portfolio-table td:nth-child(3), /* Catégorie */
      .portfolio-table td:nth-child(16), /* Signal */
      .portfolio-table td:nth-child(17), /* Action */
      .portfolio-table td:nth-child(18) {{ /* Justification */
        text-align: left;
        white-space: normal;
      }}
      /* Ajustement des largeurs de colonne */
      .portfolio-table th:nth-child(1), .portfolio-table td:nth-child(1) {{ width: 80px; }}
      .portfolio-table th:nth-child(2), .portfolio-table td:nth-child(2) {{ width: 200px; }}
      .portfolio-table th:nth-child(3), .portfolio-table td:nth-child(3) {{ width: 100px; }}
      .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4), /* Devise */
      .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5), /* Quantité */
      .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6), /* Prix d'Acquisition */
      .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7), /* Valeur */
      .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8), /* Prix Actuel */
      .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9), /* Valeur Actuelle */
      .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10), /* Haut 52 Semaines */
      .portfolio-table th:nth-child(11), .portfolio-table td:nth-child(11), /* Valeur H52 */
      .portfolio-table th:nth-child(12), .portfolio-table td:nth-child(12), /* Objectif LT */
      .portfolio-table th:nth-child(13), .portfolio-table td:nth-child(13), /* Valeur LT */
      .portfolio-table th:nth-child(14), .portfolio-table td:nth-child(14), /* Momentum (%) */
      .portfolio-table th:nth-child(15), .portfolio-table td:nth-child(15) {{ /* Z-Score */
        width: 80px;
      }}
      .portfolio-table th:nth-child(16), .portfolio-table td:nth-child(16), /* Signal */
      .portfolio-table th:nth-child(17), .portfolio-table td:nth-child(17), /* Action */
      .portfolio-table th:nth-child(18), .portfolio-table td:nth-child(18) {{ /* Justification */
        width: 150px;
      }}
      .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
      .total-row td {{
        background: #A49B6D;
        color: white;
        font-weight: bold;
      }}
      /* Style pour les indicateurs de tri */
      .sort-asc::after {{ content: ' ▲'; }}
      .sort-desc::after {{ content: ' ▼'; }}
    </style>
    
    <script>
      // Récupérer les paramètres de tri actuels passés par Python
      const currentSortColumn = "{current_sort_col_js}";
      const currentSortDirection = "{current_sort_dir_js}";
    
      function sortTable(columnLabel) {{
        let newDirection = 'asc';
        // Si la colonne cliquée est déjà celle triée, inverser la direction
        if (columnLabel === currentSortColumn) {{
          newDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
        }}
        
        // Construire la nouvelle URL avec les paramètres de tri
        // Cela va provoquer un rechargement complet de la page Streamlit
        const urlParams = new URLSearchParams(window.location.search);
        urlParams.set('sort_column', columnLabel);
        urlParams.set('sort_direction', newDirection);
        window.location.search = urlParams.toString();
      }}
    
      window.onload = function() {{
        const headers = document.querySelectorAll('.portfolio-table th');
        headers.forEach(header => {{
          // Ajouter le gestionnaire d'événement de clic
          header.addEventListener('click', function() {{
            // Supprimer l'indicateur de tri s'il est présent avant de passer le label
            const labelText = this.textContent.trim().replace(' ▲', '').replace(' ▼', '');
            sortTable(labelText);
          }});
          
          // Ajouter l'indicateur visuel de tri à la colonne actuellement triée
          const labelText = header.textContent.trim();
          if (labelText === currentSortColumn) {{
            header.classList.add(currentSortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
          }}
        }});
      }};
    </script>
    
    <div class="scroll-wrapper">
      <table class="portfolio-table">
        <thead><tr>
    """

    # Ajouter les en-têtes du tableau (le JS ajoutera les listeners de clic)
    for lbl in df_disp.columns: # Utiliser les colonnes de df_disp pour s'assurer qu'elles existent
        html_code += f'<th>{safe_escape(lbl)}</th>'

    html_code += """
        </tr></thead>
        <tbody>
    """

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in df_disp.columns: # Utiliser les colonnes de df_disp pour itérer
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    # Ligne TOTAL
    # Le nombre de cellules vides doit correspondre au nombre de colonnes - 1 (pour le total)
    # df_disp.shape[1] donne le nombre de colonnes affichées
    num_cols = df_disp.shape[1]
    
    # Trouver les indices des colonnes de totalisation
    try:
        idx_valeur = list(df_disp.columns).index("Valeur")
        idx_actuelle = list(df_disp.columns).index("Valeur Actuelle")
        idx_h52 = list(df_disp.columns).index("Valeur H52")
        idx_lt = list(df_disp.columns).index("Valeur LT")
    except ValueError:
        idx_valeur, idx_actuelle, idx_h52, idx_lt = -1, -1, -1, -1 # Valeur par défaut si non trouvées

    # Créer une liste de cellules vides pour la ligne de total, puis insérer les totaux aux bons indices
    total_row_cells = [""] * num_cols
    total_row_cells[0] = f"TOTAL ({safe_escape(devise_cible)})" # Première cellule pour le label total

    if idx_valeur != -1: total_row_cells[idx_valeur] = safe_escape(total_valeur_str)
    if idx_actuelle != -1: total_row_cells[idx_actuelle] = safe_escape(total_actuelle_str)
    if idx_h52 != -1: total_row_cells[idx_h52] = safe_escape(total_h52_str)
    if idx_lt != -1: total_row_cells[idx_lt] = safe_escape(total_lt_str)

    html_code += "<tr class='total-row'>"
    for cell_content in total_row_cells:
        html_code += f"<td>{cell_content}</td>"
    html_code += "</tr>"


    html_code += """
        </tbody>
      </table>
    </div>
    """

    components.html(html_code, height=600, scrolling=True)

# --- Structure de l'application principale ---
def main():
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("Gestion de Portefeuille d'Investissement")

    # Sidebar pour l'importation de fichiers et les paramètres
    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_csv(uploaded_file)
                st.session_state.df = df_uploaded
                st.success("Fichier importé avec succès !")
                # Réinitialiser le tri après un nouvel import
                if "sort_column" in st.session_state:
                    del st.session_state.sort_column
                if "sort_direction" in st.session_state:
                    del st.session_state.sort_direction
                st.rerun() # Recharger pour appliquer les changements
            except Exception as e:
                st.error(f"Erreur lors de la lecture du fichier : {e}")
                st.session_state.df = None

        st.header("Paramètres de Devise")
        selected_devise = st.selectbox(
            "Devise cible pour l'affichage",
            ["EUR", "USD", "GBP", "JPY", "CAD", "CHF"],
            index=["EUR", "USD", "GBP", "JPY", "CAD", "CHF"].index(st.session_state.get("devise_cible", "EUR"))
        )
        if selected_devise != st.session_state.get("devise_cible", "EUR"):
            st.session_state.devise_cible = selected_devise
            # Pas besoin de rerun ici, le changement de selectbox fait déjà un rerun.
            # La logique de fetch_fx_rates gérera le changement dans afficher_portefeuille.
            
    afficher_portefeuille()

if __name__ == "__main__":
    main()
