import streamlit as st
import pandas as pd
import requests
import time

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

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

    # Récupération de shortName, Current Price et 52 Week High via Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if ticker_col:
        # Réinitialiser le cache pour éviter les anciennes valeurs non-dictionnaires
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        def fetch_yahoo_data(t):
            t = str(t).strip().upper()
            # Vérifier le cache et valider que l'entrée est un dictionnaire
            if t in st.session_state.ticker_names_cache:
                cached = st.session_state.ticker_names_cache[t]
                if isinstance(cached, dict) and "shortName" in cached:
                    return cached
                else:
                    # Supprimer les entrées de cache invalides
                    del st.session_state.ticker_names_cache[t]

            # Ignorer les tickers invalides
            if not t or not t.replace(".", "").isalnum():
                print(f"Ticker invalide ignoré : {t}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}
        
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                }
                r = requests.get(url, headers=headers, timeout=5)
                r.raise_for_status()

                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                name = meta.get("shortName", "")
                current_price = meta.get("regularMarketPrice", None)
                fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
                
                if not name:
                    name = f"https://finance.yahoo.com/quote/{t}"
                
                result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
                st.session_state.ticker_names_cache[t] = result
                time.sleep(0.5)  # Délai pour éviter le rate limiting
                return result
            except Exception as e:
                print(f"Erreur pour {t}: {e}")
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

        # Appliquer fetch_yahoo_data et extraire les colonnes
        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        # Vérifier que chaque élément est un dictionnaire avant d'extraire
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"] if isinstance(x, dict) else f"https://finance.yahoo.com/quote/{t}")
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"] if isinstance(x, dict) else None)
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"] if isinstance(x, dict) else None)

    # Calcul des nouvelles colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

    # Formatage : français + création des colonnes *_fmt
    def format_fr(x, dec):
        if pd.isnull(x): return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    for col, dec in [
        ("Quantité", 0),
        ("Acquisition", 4),
        ("Valeur", 2),
        ("currentPrice", 2),
        ("fiftyTwoWeekHigh", 2),
        ("Valeur_H52", 2),
        ("Valeur_Actuelle", 2)
    ]:
        if col in df.columns:
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Préparer colonnes pour affichage
    cols = [
        ticker_col,
        "shortName",
        "Quantité_fmt",
        "Acquisition_fmt",
        "Valeur_fmt",
        "currentPrice_fmt",
        "fiftyTwoWeekHigh_fmt",
        "Valeur_H52_fmt",
        "Valeur_Actuelle_fmt",
        "Devise"
    ]
    labels = [
        "Ticker",
        "Nom",
        "Quantité",
        "Prix d'Acquisition",
        "Valeur",
        "Prix Actuel",
        "Haut 52 Semaines",
        "Valeur H52",
        "Valeur Actuelle",
        "Devise"
    ]
    df_disp = df[cols].copy()
    df_disp.columns = labels

    total_str = format_fr(df["Valeur"].sum() if "Valeur" in df.columns else 0, 2)

    # Construction HTML
    html = f"""
    <style>
      .table-container {{ max-height:400px; overflow-y:auto; }}
      .portfolio-table {{ width:100%; border-collapse:collapse; }}
      .portfolio-table th {{
        background:#363636; color:white; padding:6px; text-align:center; border:none;
        position:sticky; top:0; z-index:2;
        font-family:"Aptos narrow",Helvetica; font-size:12px;
      }}
      .portfolio-table td {{
        padding:6px; text-align:right; border:none;
        font-family:"Aptos narrow",Helvetica; font-size:11px;
      }}
      .portfolio-table td:first-child {{ text-align:left; }}
      .portfolio-table td:nth-child(2) {{ text-align:left; }} /* Alignement à gauche pour la colonne Nom */
      .portfolio-table tr:nth-child(even) {{ background:#efefef; }}
      .total-row td {{
        background:#A49B6D; color:white; font-weight:bold;
      }}
    </style>
    <div class="table-container">
      <table class="portfolio-table">
        <thead><tr>{''.join(f'<th>{lbl}</th>' for lbl in labels)}</tr></thead><tbody>
    """

    for _, row in df_disp.iterrows():
        html += "<tr>"
        for lbl in labels:
            html += f"<td>{row[lbl] or ''}</td>"
        html += "</tr>"

    # Ligne TOTAL
    html += "<tr class='total-row'><td>TOTAL</td>"
    html += "<td></td><td></td><td>"  # Pour Nom, Quantité, Prix d'Acquisition
    html += f"<td>{total_str}</td></td><td>"  # Valeur
    html += "<td></td><td></td><td></td><td></td><td></td></tr>"  # Pour Prix Actuel, Haut 52 Semaines, Valeur H52, Valeur Actuelle, Devise
    html += "</tbody></table></div>"

    st.markdown(html, unsafe_allow_html=True)
