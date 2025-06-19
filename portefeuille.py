import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf # Import de yfinance

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

# Mise en cache pour les taux de change
@st.cache_data(ttl=3600) # Cache pendant 1 heure pour les taux
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

# Mise en cache pour les données Yahoo Finance
@st.cache_data(ttl=900) # Cache pendant 15 minutes pour Yahoo Finance
def fetch_yahoo_data(t):
    t = str(t).strip().upper()
    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    if t in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[t]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else:
            del st.session_state.ticker_names_cache[t] # Supprimer l'entrée si le cache est invalide
    
    try:
        # Utilisation de yfinance pour une meilleure robustesse
        ticker_obj = yf.Ticker(t)
        info = ticker_obj.info
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{t}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[t] = result
        time.sleep(0.05) # Petite pause pour éviter de surcharger l'API
        return result
    except Exception as e:
        # print(f"Erreur lors de la récupération des données Yahoo pour {t}: {e}") # Décommenter pour debug
        return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

# Mise en cache pour les données de momentum
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

        # Assurez-vous que 'Close' est bien une colonne et non un MultiIndex
        if isinstance(data.columns, pd.MultiIndex):
            close = data['Close'][ticker] # Si le téléchargement est pour plusieurs tickers
        else:
            close = data['Close'] # Si le téléchargement est pour un seul ticker

        df_m = pd.DataFrame({'Close': close})
        df_m['MA_39'] = df_m['Close'].rolling(window=39).mean()
        df_m['Momentum'] = (df_m['Close'] / df_m['MA_39']) - 1
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
        # print(f"Erreur avec {ticker} pour Momentum: {e}") # Décommenter pour debug
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

    # Calcul de la valeur
    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Ajout de la colonne Catégorie depuis la colonne F du CSV (index 5)
    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Récupération de shortName, Current Price et 52 Week High via Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    # Assurez-vous que la colonne ticker_col existe et n'est pas vide avant de faire des appels API
    if ticker_col and not df[ticker_col].dropna().empty:
        # Collecter tous les tickers uniques pour éviter les appels redondants
        unique_tickers = df[ticker_col].dropna().astype(str).str.strip().str.upper().unique()
        
        # Récupérer les données Yahoo et Momentum pour tous les tickers uniques
        yahoo_results = {t: fetch_yahoo_data(t) for t in unique_tickers}
        momentum_results = {t: fetch_momentum_data(t) for t in unique_tickers}
        
        # Appliquer les résultats aux lignes du DataFrame original
        df["shortName"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("shortName"))
        df["currentPrice"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("currentPrice"))
        df["fiftyTwoWeekHigh"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("fiftyTwoWeekHigh"))
        
        df["Momentum (%)"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Momentum (%)"))
        df["Z-Score"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Z-Score"))
        df["Signal"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Signal"))
        df["Action"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Action"))
        df["Justification"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Justification"))
    else:
        # Initialiser les colonnes si aucun ticker n'est trouvé ou si la colonne est vide
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
        df["Valeur_H52"] = pd.NA # Assurez-vous que la colonne existe
    
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = pd.NA # Assurez-vous que la colonne existe

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

    # Formatage des colonnes numériques
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
        ("Momentum (%)", 2), # Ajout pour le Momentum
        ("Z-Score", 2)       # Ajout pour le Z-Score
    ]:
        if col in df.columns: # Vérifier si la colonne existe avant de la formater
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))
        else:
            df[f"{col}_fmt"] = "" # Crée une colonne vide si la base n'existe pas

    # Conversion en devise cible
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise): return 0
        if devise == devise_cible: return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    if "Devise" in df.columns:
        df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
        df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
        df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
        df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)
    else: # Fallback si la colonne Devise n'existe pas
        df["Valeur_conv"] = df["Valeur"].fillna(0)
        df["Valeur_Actuelle_conv"] = df["Valeur_Actuelle"].fillna(0)
        df["Valeur_H52_conv"] = df["Valeur_H52"].fillna(0)
        df["Valeur_LT_conv"] = df["Valeur_LT"].fillna(0)


    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum() # Utilisez total_lt pour le pied de tableau

    # Définition des colonnes internes et des labels d'affichage
    cols_internal = [
        ticker_col, # Utilisez le nom de colonne dynamique
        "shortName",
        "Catégorie",
        "Devise", # Ajout de la devise ici
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "Valeur_Actuelle_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Objectif_LT_fmt",
        "Valeur_LT_fmt",
        "Momentum (%)_fmt", # Ajout des colonnes de momentum formatées
        "Z-Score_fmt",      # Ajout des colonnes de momentum formatées
        "Signal",
        "Action",
        "Justification"
    ]
    labels_display = [
        "Ticker",
        "Nom",
        "Catégorie",
        "Devise", # Ajout de la devise ici
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Valeur Actuelle",
        "Haut 52 Semaines",
        "Valeur H52",
        "Objectif LT",
        "Valeur LT",
        "Momentum (%)", # Labels d'affichage pour momentum
        "Z-Score",      # Labels d'affichage pour Z-Score
        "Signal",
        "Action",
        "Justification"
    ]

    # Filtrer les colonnes pour s'assurer qu'elles existent dans le DataFrame
    final_cols_internal = []
    final_labels = []
    for i, col_name in enumerate(cols_internal):
        # Vérifier si la colonne non formatée existe ou si la colonne formatée peut être basée sur une colonne non formatée existante
        if col_name in df.columns or (col_name and col_name.endswith("_fmt") and col_name.replace("_fmt", "") in df.columns):
            final_cols_internal.append(col_name)
            final_labels.append(labels_display[i])
        elif col_name == "shortName" and "shortName" in df.columns: # Gérer shortName qui n'est pas forcément _fmt
            final_cols_internal.append(col_name)
            final_labels.append(labels_display[i])
        elif col_name in ["Signal", "Action", "Justification"] and col_name in df.columns: # Gérer les colonnes de texte de momentum
            final_cols_internal.append(col_name)
            final_labels.append(labels_display[i])
        elif col_name == "Devise" and "Devise" in df.columns: # Gérer la colonne devise
            final_cols_internal.append(col_name)
            final_labels.append(labels_display[i])
            
    df_disp = df[final_cols_internal].copy()
    df_disp.columns = final_labels

    # Récupérer les paramètres de tri Streamlit pour initialiser le tri JS
    query_params = st.query_params
    initial_sort_col = query_params.get("sort_column", None)
    initial_sort_dir = query_params.get("sort_direction", "asc")

    # Si un tri est spécifié dans l'URL, appliquez-le au DataFrame Python AVANT le rendu HTML
    # Cela garantit que le tableau est trié à la première visualisation
    if initial_sort_col and initial_sort_col in df_disp.columns:
        # Tente de trouver la colonne interne correspondante pour le tri numérique
        original_col_for_sort = None
        try:
            idx = final_labels.index(initial_sort_col)
            original_col_for_sort = final_cols_internal[idx]
            if original_col_for_sort.endswith("_fmt"):
                original_col_for_sort = original_col_for_sort.replace("_fmt", "")
        except ValueError:
            pass # Si le label n'est pas trouvé, pas de colonne originale spécifique

        if original_col_for_sort in df.columns and pd.api.types.is_numeric_dtype(df[original_col_for_sort]):
            # Tri numérique en utilisant la colonne originale non formatée
            # Assurez-vous que l'index de df correspond à celui de df_disp pour le key lambda
            df_disp = df_disp.sort_values(
                by=initial_sort_col,
                ascending=(initial_sort_dir == "asc"),
                key=lambda x: pd.to_numeric(df[original_col_for_sort].reindex(x.index), errors='coerce').fillna(
                    -float('inf') if initial_sort_dir == 'asc' else float('inf')
                )
            )
        else:
            # Tri alphabétique (pour les colonnes non numériques ou si la colonne originale n'est pas trouvée)
            df_disp = df_disp.sort_values(
                by=initial_sort_col,
                ascending=(initial_sort_dir == "asc"),
                key=lambda x: x.astype(str).str.lower()
            )
    
    # Construction du HTML
    # Note: Le script sortTable sera dans le HTML pour un tri côté client
    html_code = f"""
    <style>
    .table-container {{ max-height: 500px; overflow-y: auto; }}
    .portfolio-table {{ width: 100%; border-collapse: collapse; table-layout: auto; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    .portfolio-table th {{
      background: #363636; color: white; padding: 6px; text-align: center; border: none;
      position: sticky; top: 0; z-index: 2; font-size: 12px; cursor: pointer;
    }}
    .portfolio-table th:hover {{
      background: #4a4a4a;
    }}
    .portfolio-table td {{
      padding: 6px; text-align: right; border: none; font-size: 11px;
      white-space: nowrap; /* Empêche le wrapping, mais peut être retiré si nécessaire */
    }}
    .portfolio-table td:first-child, /* Ticker */
    .portfolio-table td:nth-child(2), /* Nom */
    .portfolio-table td:nth-child(3), /* Catégorie */
    .portfolio-table td:nth-child(16), /* Signal (adapté au nouveau nombre de colonnes) */
    .portfolio-table td:nth-child(17), /* Action */
    .portfolio-table td:nth-child(18) {{ /* Justification */
      text-align: left;
      white-space: normal; /* Autorise le wrapping pour ces colonnes */
    }}
    .portfolio-table tr:nth-child(even) {{ background: #efefef; }}
    .total-row td {{
      background: #A49B6D; color: white; font-weight: bold;
    }}
    /* Styles pour les indicateurs de tri */
    .sort-asc::after {{ content: ' ▲'; }}
    .sort-desc::after {{ content: ' ▼'; }}
    </style>
    
    <div class="table-container">
      <table class="portfolio-table">
        <thead><tr>
    """
    
    # En-têtes du tableau avec le gestionnaire de clic JS
    for i, label in enumerate(final_labels):
        # Ajouter l'indicateur de tri initial si la colonne est triée à l'origine
        sort_indicator = ""
        if label == initial_sort_col:
            sort_indicator = " ▲" if initial_sort_dir == "asc" else " ▼"
        html_code += f'<th data-column-index="{i}">{safe_escape(label)}{sort_indicator}</th>'
    
    html_code += """
        </tr></thead>
        <tbody>
    """

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in final_labels:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    # Ligne TOTAL
    num_cols_displayed = len(df_disp.columns)
    total_row_cells = [""] * num_cols_displayed
    
    # Trouver l'indice des colonnes de totalisation
    try:
        idx_valeur = final_labels.index("Valeur")
        total_row_cells[idx_valeur] = format_fr(total_valeur, 2)
    except ValueError: pass
    
    try:
        idx_actuelle = final_labels.index("Valeur Actuelle")
        total_row_cells[idx_actuelle] = format_fr(total_actuelle, 2)
    except ValueError: pass
        
    try:
        idx_h52 = final_labels.index("Valeur H52")
        total_row_cells[idx_h52] = format_fr(total_h52, 2)
    except ValueError: pass
        
    try:
        idx_lt = final_labels.index("Valeur LT")
        total_row_cells[idx_lt] = format_fr(total_lt, 2)
    except ValueError: pass

    # La première cellule pour "TOTAL (Devise)"
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
    function sortTable(n) {
      var table = document.querySelector(".portfolio-table");
      var tbody = table.querySelector("tbody");
      var rows = Array.from(tbody.rows);
      var currentHeader = table.querySelectorAll("th")[n];
      var dir = currentHeader.getAttribute("data-dir") || "asc";
      
      // Inverser la direction pour le prochain clic si c'est la même colonne
      dir = (dir === "asc") ? "desc" : "asc";
      
      // Nettoyer tous les indicateurs et attributs
      table.querySelectorAll("th").forEach(th => {
        th.removeAttribute("data-dir");
        th.classList.remove("sort-asc", "sort-desc");
        th.innerHTML = th.innerHTML.replace(/ ▲| ▼/g, "");
      });
      
      // Appliquer le nouvel indicateur et attribut à l'en-tête cliqué
      currentHeader.setAttribute("data-dir", dir);
      currentHeader.classList.add(dir === "asc" ? "sort-asc" : "sort-desc");
    
      rows.sort((a, b) => {
        var x = a.cells[n].textContent.trim();
        var y = b.cells[n].textContent.trim();
    
        // Tente de convertir en nombre. Gère les espaces et virgules.
        var xNum = parseFloat(x.replace(/ /g, "").replace(",", "."));
        var yNum = parseFloat(y.replace(/ /g, "").replace(",", "."));
    
        // Si les deux sont des nombres valides, trier numériquement
        if (!isNaN(xNum) && !isNaN(yNum)) {
          return dir === "asc" ? xNum - yNum : yNum - xNum;
        }
        // Sinon, trier alphabétiquement (insensible à la casse)
        return dir === "asc" ? x.localeCompare(y, undefined, {sensitivity: 'base'}) : y.localeCompare(x, undefined, {sensitivity: 'base'});
      });
      
      // Replacer les lignes triées dans le tableau
      tbody.innerHTML = ""; // Vide le corps du tableau
      rows.forEach(row => tbody.appendChild(row)); // Ajoute les lignes triées
    }
    </script>"""

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
                # Pas besoin de vider les query_params ici car le tri est client-side
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
            # Pas besoin de st.rerun() ici si l'affichage se met à jour automatiquement via session_state
            # mais si les taux de change doivent être rechargés, un rerun serait nécessaire.
            # Pour l'instant, on se base sur la logique fetch_fx_rates qui met à jour session_state.fx_rates
            st.rerun() # Un rerun est nécessaire pour que les calculs de conversion se mettent à jour


    afficher_portefeuille()

if __name__ == "__main__":
    main()
