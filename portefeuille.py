import streamlit as st
from streamlit import cache_data
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components

# --- Fonctions utilitaires ---

def fetch_fx_rates(base="EUR"):
    """
    Récupère les taux de change les plus récents par rapport à une devise de base.
    Gère les erreurs de connexion ou de réponse de l'API.
    """
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Lève une exception pour les codes d'état HTTP d'erreur
        data = response.json()
        return data.get("rates", {})
    except requests.exceptions.RequestException as e:
        st.error(f"Erreur réseau ou timeout lors de la récupération des taux de change : {e}")
        return {}
    except Exception as e:
        st.error(f"Erreur inattendue lors de la récupération des taux de change : {e}")
        return {}

def format_fr(x, dec):
    """
    Formate un nombre en chaîne de caractères avec la virgule comme séparateur décimal
    et l'espace comme séparateur de milliers (format français).
    """
    if pd.isnull(x):
        return ""
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",")

@st.cache_data(ttl=900)  # Cache les données Yahoo pour 15 minutes (900 secondes)
def fetch_yahoo_data(ticker):
    """
    Récupère le nom court, le prix actuel et le plus haut sur 52 semaines pour un ticker donné
    depuis l'API Yahoo Finance. Utilise un cache de session pour éviter des requêtes répétées.
    """
    ticker = str(ticker).strip().upper()
    if ticker in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[ticker]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else:  # Si le cache contient une entrée invalide ou incomplète, la supprimer
            del st.session_state.ticker_names_cache[ticker]

    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        # Utilisation d'un User-Agent pour simuler un navigateur et éviter certains blocages
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        data = r.json()
        meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
        
        name = meta.get("shortName", f"https://finance.yahoo.com/quote/{ticker}")
        current_price = meta.get("regularMarketPrice", None)
        fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
        
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[ticker] = result
        time.sleep(0.5)  # Pause pour éviter de surcharger l'API Yahoo Finance
        return result
    except requests.exceptions.RequestException as req_e:
        st.warning(f"Erreur réseau ou timeout lors de la récupération des données pour '{ticker}': {req_e}")
        return {"shortName": f"https://finance.yahoo.com/quote/{ticker}", "currentPrice": None, "fiftyTwoWeekHigh": None}
    except Exception as e:
        st.warning(f"Erreur lors du traitement des données pour '{ticker}': {e}")
        return {"shortName": f"https://finance.yahoo.com/quote/{ticker}", "currentPrice": None, "fiftyTwoWeekHigh": None}

# --- Fonction principale d'affichage du portefeuille ---

def afficher_portefeuille():
    """
    Prépare les données du portefeuille et génère une table HTML interactive
    avec tri des colonnes via JavaScript, affichée dans Streamlit.
    """
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée. Veuillez importer un fichier Excel.")
        return

    df = st.session_state.df.copy()

    # Harmoniser le nom de la colonne pour l'objectif long terme
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    # Récupération et mise en cache des taux de change si nécessaire
    devise_cible = st.session_state.get("devise_cible", "EUR")
    if "last_devise_cible" not in st.session_state or st.session_state.last_devise_cible != devise_cible:
        st.session_state.last_devise_cible = devise_cible
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
    fx_rates = st.session_state.get("fx_rates", {})

    # Nettoyage et conversion des colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            # Supprime les espaces et remplace les virgules par des points pour la conversion numérique
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce") # Convertit en numérique, met NaN pour les erreurs

    # Calcul de la valeur d'acquisition
    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Détermination de la colonne "Catégorie" (la 6ème colonne si elle existe)
    df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("") if len(df.columns) > 5 else ""

    # Initialisation du cache des noms de tickers si ce n'est pas déjà fait
    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    # Traitement des tickers (Yahoo Finance Data)
    ticker_col = "Ticker" if "Ticker" in df.columns else ("Tickers" if "Tickers" in df.columns else None)
    if ticker_col and not df[ticker_col].empty: # Assurez-vous que la colonne existe et n'est pas vide
        # Applique la fonction de récupération Yahoo sur la colonne des tickers
        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"])
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"])
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"])
    else: # Si pas de colonne ticker ou vide, initialise les colonnes de Yahoo à None
        df["shortName"] = None
        df["currentPrice"] = None
        df["fiftyTwoWeekHigh"] = None

    # Calcul des valeurs basées sur les prix Yahoo
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    # Traitement et calcul de l'objectif long terme
    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = pd.NA
    else:
        df["Objectif_LT"] = df["Objectif_LT"].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]
    total_valeur_lt = df["Valeur_LT"].sum()

    # Application du formatage français pour l'affichage
    for col, dec in [
        ("Quantité", 0), ("Acquisition", 4), ("Valeur", 2),
        ("currentPrice", 4), ("fiftyTwoWeekHigh", 4),
        ("Valeur_H52", 2), ("Valeur_Actuelle", 2),
        ("Objectif_LT", 4), ("Valeur_LT", 2),
    ]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Fonction de conversion de devise
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise):
            return 0
        if devise.upper() == devise_cible.upper():
            return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    # Application de la conversion aux valeurs monétaires
    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)

    # Calcul des totaux convertis
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Définition des colonnes et labels pour l'affichage
    cols_definition = [
        (ticker_col, "Ticker"),
        ("shortName", "Nom"),
        ("Catégorie", "Catégorie"),
        ("Quantité_fmt", "Quantité"),
        ("Acquisition_fmt", "Prix d'Acquisition"),
        ("Valeur_fmt", "Valeur"),
        ("currentPrice_fmt", "Prix Actuel"),
        ("Valeur_Actuelle_fmt", "Valeur Actuelle"),
        ("fiftyTwoWeekHigh_fmt", "Haut 52 Semaines"),
        ("Valeur_H52_fmt", "Valeur H52"),
        ("Objectif_LT_fmt", "Objectif LT"),
        ("Valeur_LT_fmt", "Valeur LT"),
        ("Devise", "Devise")
    ]

    # Filtrer les colonnes et labels qui existent réellement dans le DataFrame
    cols_to_display = [col for col, _ in cols_definition if col in df.columns]
    labels_to_display = [label for col, label in cols_definition if col in df.columns]

    df_disp = df[cols_to_display].copy()
    df_disp.columns = labels_to_display

    # --- Génération du HTML avec CSS et JavaScript pour le tri ---
    html_code = f"""
    <style>
    .table-container {{
        max-height: 500px;
        overflow-y: auto;
        border: 1px solid #ddd;
        border-radius: 5px;
        margin-bottom: 20px; /* Ajoute un peu d'espace sous la table */
    }}
    .portfolio-table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: auto;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        min-width: max-content;
    }}
    .portfolio-table th {{
        background: #363636;
        color: white;
        padding: 8px 12px;
        text-align: center;
        border: 1px solid #444;
        position: sticky;
        top: 0;
        z-index: 2;
        font-size: 13px;
        cursor: pointer;
        white-space: nowrap;
    }}
    .portfolio-table td {{
        padding: 7px 12px;
        text-align: right;
        border: 1px solid #e0e0e0;
        font-size: 12px;
        white-space: nowrap;
    }}
    .portfolio-table td:nth-child(1),
    .portfolio-table td:nth-child(2),
    .portfolio-table td:nth-child(3) {{
        text-align: left;
    }}
    .portfolio-table tr:nth-child(even) {{ background: #f8f8f8; }}
    .portfolio-table tr:hover {{ background: #e6f7ff; }}

    .total-row td {{
        background: #6c757d;
        color: white;
        font-weight: bold;
        padding: 10px 12px;
        border-top: 2px solid #5a6268;
        position: sticky;
        bottom: 0;
        z-index: 1;
        text-align: right; /* Aligne le texte du total à droite */
    }}
    .total-row td:first-child {{
        text-align: left; /* Aligne "TOTAL (EUR)" à gauche */
    }}
    </style>
    <div class="table-container">
        <table class="portfolio-table">
            <thead>
                <tr>"""
    # Génération des en-têtes de table avec la fonction de tri JavaScript
    for i, label in enumerate(labels_to_display):
        html_code += f'<th onclick="sortTable({i})">{html.escape(label)}</th>'
    html_code += """
                </tr>
            </thead>
            <tbody>"""

    # Génération des lignes de données
    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in labels_to_display:
            val = row[lbl]
            val_str = str(val) if pd.notnull(val) else ""
            html_code += f"<td>{html.escape(val_str)}</td>"
        html_code += "</tr>"

    # Génération du pied de page avec les totaux
    html_code += f"""
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td>TOTAL ({devise_cible})</td>"""

    # Remplit les cellules du pied de page avec les totaux ou des cellules vides
    # Cette partie a été rendue plus robuste pour correspondre aux labels_to_display
    total_values_map = {
        "Valeur": total_valeur,
        "Valeur Actuelle": total_actuelle,
        "Valeur H52": total_h52,
        "Valeur LT": total_lt
    }

    # Iterer sur les labels_to_display pour s'assurer que l'ordre est correct
    for i, label in enumerate(labels_to_display):
        if i == 0: # La première cellule est déjà "TOTAL (devise_cible)"
            continue
        if label in total_values_map:
            html_code += f"<td>{format_fr(total_values_map[label], 2)}</td>"
        else:
            html_code += "<td></td>" # Cellule vide pour les colonnes sans total

    html_code += """
                </tr>
            </tfoot>
        </table>
    </div>

    <script>
    function sortTable(n) {
        var table = document.querySelector(".portfolio-table");
        var tbody = table.querySelector("tbody");
        var rows = Array.from(tbody.rows);
        var dir = table.querySelectorAll("th")[n].getAttribute("data-dir") || "asc";
        dir = (dir === "asc") ? "desc" : "asc";
        
        // Supprimer les indicateurs de tri existants et définir le nouveau
        table.querySelectorAll("th").forEach(th => {
            th.removeAttribute("data-dir");
            th.innerHTML = th.innerHTML.replace(/ ▲| ▼/g, "");
        });
        table.querySelectorAll("th")[n].setAttribute("data-dir", dir);
        table.querySelectorAll("th")[n].innerHTML += dir === "asc" ? " ▲" : " ▼";

        rows.sort((a, b) => {
            var x = a.cells[n].textContent.trim();
            var y = b.cells[n].textContent.trim();

            // Tente de convertir en nombre pour un tri numérique
            // Gère les formats français (virgule décimale, espace pour milliers)
            var xNum = parseFloat(x.replace(/ /g, "").replace(",", "."));
            var yNum = parseFloat(y.replace(/ /g, "").replace(",", "."));

            if (!isNaN(xNum) && !isNaN(yNum)) {
                return dir === "asc" ? xNum - yNum : yNum - xNum;
            }
            // Sinon, tri alphanumérique insensible à la casse
            return dir === "asc" ? x.localeCompare(y, undefined, {sensitivity: 'base'}) : y.localeCompare(x, undefined, {sensitivity: 'base'});
        });
        
        tbody.innerHTML = ""; // Vide le corps de la table
        rows.forEach(row => tbody.appendChild(row)); // Rajoute les lignes triées
    }
    </script>
    """
    components.html(html_code, height=600, scrolling=True)

# --- Section principale de l'application Streamlit ---

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("📊 Gestion de Portefeuille")

    # --- Barre latérale pour l'importation et les options ---
    st.sidebar.header("Options d'importation et de devise")

    uploaded_file = st.sidebar.file_uploader("📥 Importez votre fichier Excel", type=["xlsx"])

    if uploaded_file is not None:
        try:
            # Charger le DataFrame seulement si un nouveau fichier est téléchargé ou si df n'est pas encore défini
            if "df" not in st.session_state or st.session_state.get("uploaded_file_id") != uploaded_file.file_id:
                st.session_state.df = pd.read_excel(uploaded_file)
                st.session_state.uploaded_file_id = uploaded_file.file_id # Stocker l'ID du fichier pour détecter les changements
                st.sidebar.success("Fichier importé avec succès !")
                # Réinitialiser le cache des tickers si un nouveau fichier est chargé pour éviter des données obsolètes
                if "ticker_names_cache" in st.session_state:
                    del st.session_state.ticker_names_cache
        except Exception as e:
            st.error(f"❌ Erreur lors de la lecture du fichier Excel : {e}")
            st.session_state.df = None
    elif "df" not in st.session_state: # Initialiser df si aucun fichier n'est encore chargé
        st.session_state.df = None

    # Sélecteur de devise cible
    devise_options = ["EUR", "USD", "GBP", "CHF", "JPY"]
    current_devise = st.session_state.get("devise_cible", "EUR")
    st.session_state.devise_cible = st.sidebar.selectbox(
        "💱 Convertir toutes les valeurs en :",
        devise_options,
        index=devise_options.index(current_devise) if current_devise in devise_options else 0,
        key="devise_select" # Ajout d'une clé explicite pour le selectbox
    )

    # --- Affichage du portefeuille ---
    st.header("📈 Résumé de votre Portefeuille")

    # Appel de la fonction qui contient toute la logique de traitement et l'affichage de la table
    afficher_portefeuille()

    st.markdown("---")
    st.info("💡 Importez un fichier Excel pour visualiser et analyser votre portefeuille. Assurez-vous que les colonnes 'Quantité', 'Acquisition', 'Devise' et 'Ticker' (ou 'Tickers') sont présentes pour des calculs optimaux.")
