# portefeuille.py

import streamlit as st
from streamlit import cache_data
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components

# --- Fonctions de récupération de données (incluses dans votre code) ---

def fetch_fx_rates(base="EUR"):
    """Récupère les taux de change à partir de l'API exchangerate.host."""
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("rates", {})
    except Exception as e:
        st.error(f"Erreur lors de la récupération des taux de change : {e}")
        return {}

# --- Fonction principale d'affichage du portefeuille (votre code) ---

def afficher_portefeuille():
    """
    Calcule, formate et affiche le portefeuille sous forme de table HTML triable.
    Utilise les données de st.session_state.df.
    """
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée. Veuillez importer un fichier Excel.")
        return

    df = st.session_state.df.copy()

    # Harmoniser le nom de la colonne pour l’objectif long terme
    if "LT" in df.columns and "Objectif_LT" not in df.columns:
        df.rename(columns={"LT": "Objectif_LT"}, inplace=True)

    devise_cible = st.session_state.get("devise_cible", "EUR")

    # Gérer la récupération des taux de change uniquement si la devise cible change
    if "last_devise_cible" not in st.session_state:
        st.session_state.last_devise_cible = devise_cible
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)
    elif st.session_state.last_devise_cible != devise_cible:
        st.session_state.last_devise_cible = devise_cible
        st.session_state.fx_rates = fetch_fx_rates(devise_cible)

    fx_rates = st.session_state.get("fx_rates", {})

    # Nettoyage et conversion des colonnes numériques
    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = (
                df[col].astype(str)
                      .str.replace(" ", "", regex=False)
                      .str.replace(",", ".", regex=False)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    # Catégorie (gestion de la 6ème colonne si elle existe)
    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Traitement des tickers Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if ticker_col:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        @st.cache_data(ttl=900) # Cache les données Yahoo pour 15 minutes
        def fetch_yahoo_data(t):
            t = str(t).strip().upper()
            if t in st.session_state.ticker_names_cache:
                cached = st.session_state.ticker_names_cache[t]
                if isinstance(cached, dict) and "shortName" in cached:
                    return cached
                else: # Si le cache contient une entrée invalide, la supprimer
                    del st.session_state.ticker_names_cache[t]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"} # Ajout d'un User-Agent
                r = requests.get(url, headers=headers, timeout=5)
                r.raise_for_status()
                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                name = meta.get("shortName", f"https://finance.yahoo.com/quote/{t}")
                current_price = meta.get("regularMarketPrice", None)
                fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
                result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
                st.session_state.ticker_names_cache[t] = result
                time.sleep(0.5) # Pause pour éviter le blocage de l'API
                return result
            except requests.exceptions.RequestException as req_e:
                st.warning(f"Erreur réseau ou timeout pour le ticker {t}: {req_e}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}
            except Exception as e:
                st.warning(f"Erreur lors de la récupération des données pour le ticker {t}: {e}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"])
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"])
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"])

    # Calcul des valeurs basées sur les prix Yahoo
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    # Traitement de l'objectif long terme
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
    total_valeur_lt = df["Valeur_LT"].sum()

    # Fonction de formatage pour l'affichage (utilisée dans le HTML)
    def format_fr(x, dec):
        if pd.isnull(x): return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    # Appliquer le formatage aux colonnes pertinentes
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
    ]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Conversion des valeurs à la devise cible
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise): return 0
        if devise.upper() == devise_cible.upper(): return val # Comparer en majuscules
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)

    # Calcul des totaux convertis
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Sélection et renommage des colonnes pour l'affichage
    cols = [
        ticker_col,
        "shortName",
        "Catégorie",
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "Valeur_Actuelle_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Objectif_LT_fmt",
        "Valeur_LT_fmt",
        "Devise"
    ]
    labels = [
        "Ticker",
        "Nom",
        "Catégorie",
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Valeur Actuelle",
        "Haut 52 Semaines",
        "Valeur H52",
        "Objectif LT",
        "Valeur LT",
        "Devise"
    ]

    # Filtrer les colonnes qui n'existent pas dans df (par exemple si ticker_col est None)
    cols_to_use = [col for col in cols if col in df.columns]
    labels_to_use = [labels[i] for i, col in enumerate(cols) if col in df.columns]

    df_disp = df[cols_to_use].copy()
    df_disp.columns = labels_to_use

    # --- Génération du HTML avec CSS et JavaScript pour le tri ---
    html_code = f"""
    <style>
    .table-container {{ max-height: 500px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; }}
    .portfolio-table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: auto; /* Permet aux colonnes de s'adapter à leur contenu */
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        min-width: max-content; /* Assure que la table ne se réduit pas trop */
    }}
    .portfolio-table th {{
        background: #363636;
        color: white;
        padding: 8px 12px; /* Augmenter le padding pour plus d'espace */
        text-align: center;
        border: 1px solid #444; /* Bordure légèrement plus foncée */
        position: sticky;
        top: 0;
        z-index: 2;
        font-size: 13px; /* Taille de police légèrement plus grande */
        cursor: pointer;
        white-space: nowrap; /* Empêche le texte de s'enrouler dans l'en-tête */
    }}
    .portfolio-table td {{
        padding: 7px 12px;
        text-align: right;
        border: 1px solid #e0e0e0; /* Bordure plus douce */
        font-size: 12px;
        white-space: nowrap; /* Empêche le texte de s'enrouler dans les cellules */
    }}
    /* Alignement spécifique pour les premières colonnes */
    .portfolio-table td:nth-child(1), /* Ticker */
    .portfolio-table td:nth-child(2), /* Nom */
    .portfolio-table td:nth-child(3) {{ /* Catégorie */
        text-align: left;
    }}
    .portfolio-table tr:nth-child(even) {{ background: #f8f8f8; }} /* Lignes paires légèrement différentes */
    .portfolio-table tr:hover {{ background: #e6f7ff; }} /* Effet de survol */

    .total-row td {{
        background: #6c757d; /* Gris foncé pour le total */
        color: white;
        font-weight: bold;
        padding: 10px 12px;
        border-top: 2px solid #5a6268; /* Bordure supérieure plus épaisse */
        position: sticky; /* Rendre le total sticky en bas */
        bottom: 0;
        z-index: 1;
    }}
    </style>
    <div class="table-container">
        <table class="portfolio-table">
            <thead>
                <tr>"""
    for i, label in enumerate(labels_to_use): # Utiliser labels_to_use
        html_code += f'<th onclick="sortTable({i})">{html.escape(label)}</th>'
    html_code += """
                </tr>
            </thead>
            <tbody>"""

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in labels_to_use: # Utiliser labels_to_use
            val = row[lbl]
            val_str = str(val) if pd.notnull(val) else ""
            html_code += f"<td>{html.escape(val_str)}</td>"
        html_code += "</tr>"

    html_code += f"""
            </tbody>
            <tfoot>
                <tr class="total-row">
                    <td>TOTAL ({devise_cible})</td>"""

    # Remplir les cellules du pied de page. Assurez-vous que les indices correspondent aux labels_to_use
    # Cela demande une cartographie manuelle ou plus dynamique si les colonnes changent souvent
    # Pour l'exemple, nous allons insérer les totaux aux positions connues, et laisser des cellules vides pour les autres
    total_cols_map = {
        "Valeur": format_fr(total_valeur, 2),
        "Valeur Actuelle": format_fr(total_actuelle, 2),
        "Valeur H52": format_fr(total_h52, 2),
        "Valeur LT": format_fr(total_lt, 2)
    }
    
    for label in labels_to_use:
        if label == "TOTAL": # la première cellule est déjà gérée
            continue
        elif label in total_cols_map:
            html_code += f"<td>{total_cols_map[label]}</td>"
        else:
            html_code += "<td></td>" # Cellule vide pour les autres colonnes

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
            var xNum = parseFloat(x.replace(/ /g, "").replace(",", "."));
            var yNum = parseFloat(y.replace(/ /g, "").replace(",", "."));

            if (!isNaN(xNum) && !isNaN(yNum)) {
                return dir === "asc" ? xNum - yNum : yNum - xNum;
            }
            // Sinon, tri alphanumérique
            return dir === "asc" ? x.localeCompare(y) : y.localeCompare(x);
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
    st.title("Gestion de Portefeuille")

    # --- Barre latérale pour l'importation et les options ---
    st.sidebar.header("Options de Portefeuille")

    uploaded_file = st.sidebar.file_uploader("Choisissez un fichier Excel", type=["xlsx"])

    if uploaded_file is not None:
        try:
            # Charger le DataFrame seulement si un nouveau fichier est téléchargé ou si df n'est pas encore défini
            if "df" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
                st.session_state.df = pd.read_excel(uploaded_file)
                st.session_state.uploaded_file_id = uploaded_file.file_id # Stocker l'ID du fichier pour détecter les changements
                st.sidebar.success("Fichier importé avec succès !")
                # Réinitialiser le cache des tickers si un nouveau fichier est chargé
                if "ticker_names_cache" in st.session_state:
                    del st.session_state.ticker_names_cache
        except Exception as e:
            st.error(f"Erreur lors de la lecture du fichier Excel : {e}")
            st.session_state.df = None
    elif "df" not in st.session_state: # Initialiser df si aucun fichier n'est encore chargé
        st.session_state.df = None

    # Sélecteur de devise cible
    devise_options = ["EUR", "USD", "GBP", "CHF", "JPY"]
    current_devise = st.session_state.get("devise_cible", "EUR")
    st.session_state.devise_cible = st.sidebar.selectbox(
        "Convertir toutes les devises en :",
        devise_options,
        index=devise_options.index(current_devise) if current_devise in devise_options else 0,
        key="devise_select"
    )

    # --- Affichage du portefeuille ---
    st.header("Résumé du Portefeuille")

    # Appel de votre fonction qui contient toute la logique et le components.html
    afficher_portefeuille()

    st.markdown("---")
    st.write("Ceci est une application de gestion de portefeuille. Importez un fichier Excel pour commencer.")
