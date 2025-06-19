import streamlit as st
import pandas as pd
import requests
import time
import html
import streamlit.components.v1 as components
import yfinance as yf

def safe_escape(text):
    """Escape HTML characters safely."""
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


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

    # Ajout de la colonne Catégorie depuis la colonne F du CSV
    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    # Récupération de shortName, Current Price et 52 Week High via Yahoo Finance
    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    if ticker_col:
        if "ticker_names_cache" not in st.session_state:
            st.session_state.ticker_names_cache = {}

        @st.cache_data(ttl=900)
        def fetch_yahoo_data(t):
            t = str(t).strip().upper()
            if t in st.session_state.ticker_names_cache:
                cached = st.session_state.ticker_names_cache[t]
                if isinstance(cached, dict) and "shortName" in cached:
                    return cached
                else:
                    del st.session_state.ticker_names_cache[t]
            try:
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}"
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(url, headers=headers, timeout=5)
                r.raise_for_status()
                data = r.json()
                meta = data.get("chart", {}).get("result", [{}])[0].get("meta", {})
                name = meta.get("shortName", f"https://finance.yahoo.com/quote/{t}")
                current_price = meta.get("regularMarketPrice", None)
                fifty_two_week_high = meta.get("fiftyTwoWeekHigh", None)
                result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
                st.session_state.ticker_names_cache[t] = result
                time.sleep(0.5)
                return result
            except Exception:
                return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

        yahoo_data = df[ticker_col].apply(fetch_yahoo_data)
        df["shortName"] = yahoo_data.apply(lambda x: x["shortName"])
        df["currentPrice"] = yahoo_data.apply(lambda x: x["currentPrice"])
        df["fiftyTwoWeekHigh"] = yahoo_data.apply(lambda x: x["fiftyTwoWeekHigh"])

    # Calcul des colonnes Valeur H52 et Valeur Actuelle
    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]

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

    # Momentum Analysis
    @st.cache_data(ttl=3600)
    def fetch_momentum_data(ticker, period="5y", interval="1wk"):
        try:
            data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
            if data.empty:
                print(f"Aucune donnée pour {ticker}")
                return {
                    "Last Price": None,
                    "Momentum (%)": None,
                    "Z-Score": None,
                    "Signal": "",
                    "Action": "",
                    "Justification": ""
                }

            if isinstance(data.columns, pd.MultiIndex):
                close = data['Close'][ticker]
            else:
                close = data['Close']

            df_m = pd.DataFrame({'Close': close})
            df_m['MA_39'] = df_m['Close'].rolling(window=39).mean()
            df_m['Momentum'] = (df_m['Close'] / df_m['MA_39']) - 1
            df_m['Z_Momentum'] = (df_m['Momentum'] - df_m['Momentum'].rolling(10).mean()) / df_m['Momentum'].rolling(10).std()

            latest = df_m.iloc[-1]
            z = latest['Z_Momentum']
            m = latest['Momentum'] * 100

            if pd.isna(z):
                return {
                    "Last Price": round(latest['Close'], 2) if not pd.isna(latest['Close']) else None,
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
                "Last Price": round(latest['Close'], 2),
                "Momentum (%)": round(m, 2),
                "Z-Score": round(z, 2),
                "Signal": signal,
                "Action": action,
                "Justification": reason
            }
        except Exception as e:
            print(f"Erreur avec {ticker}: {e}")
            return {
                "Last Price": None,
                "Momentum (%)": None,
                "Z-Score": None,
                "Signal": "",
                "Action": "",
                "Justification": ""
            }

    # Apply momentum analysis
    momentum_results = {ticker: fetch_momentum_data(ticker) for ticker in df[ticker_col]}
    momentum_df = pd.DataFrame.from_dict(momentum_results, orient='index').reset_index()
    momentum_df = momentum_df.rename(columns={'index': ticker_col})
    df = df.merge(momentum_df, on=ticker_col, how='left')

    # Formatage
    def format_fr(x, dec):
        if pd.isnull(x): return ""
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
            df[f"{col}_fmt"] = df[col].map(lambda x: format_fr(x, dec))

    # Conversion en devise cible
    def convertir(val, devise):
        if pd.isnull(val) or pd.isnull(devise): return 0
        if devise == devise_cible: return val
        taux = fx_rates.get(devise.upper())
        return val * taux if taux else 0

    df["Valeur_conv"] = df.apply(lambda x: convertir(x["Valeur"], x["Devise"]), axis=1)
    df["Valeur_Actuelle_conv"] = df.apply(lambda x: convertir(x["Valeur_Actuelle"], x["Devise"]), axis=1)
    df["Valeur_H52_conv"] = df.apply(lambda x: convertir(x["Valeur_H52"], x["Devise"]), axis=1)
    df["Valeur_LT_conv"] = df.apply(lambda x: convertir(x["Valeur_LT"], x["Devise"]), axis=1)

    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    # Préparer colonnes pour affichage
    cols = [
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
    labels = [
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

    df_disp = df[cols].copy()
    df_disp.columns = labels

    # Gestion du tri
    if "sort_column" not in st.session_state:
        st.session_state.sort_column = None
    if "sort_direction" not in st.session_state:
        st.session_state.sort_direction = "asc"

    # Appliquer le tri
    if st.session_state.sort_column:
        sort_key = {
            "Quantité": "Quantité",
            "Prix d'Acquisition": "Acquisition",
            "Valeur": "Valeur",
            "Prix Actuel": "currentPrice",
            "Valeur Actuelle": "Valeur_Actuelle",
            "Haut 52 Semaines": "fiftyTwoWeekHigh",
            "Valeur H52": "Valeur_H52",
            "Objectif LT": "Objectif_LT",
            "Valeur LT": "Valeur_LT",
            "Momentum (%)": "Momentum (%)",
            "Z-Score": "Z-Score"
        }.get(st.session_state.sort_column, st.session_state.sort_column)
        if sort_key in df.columns:
            df_disp = df_disp.sort_values(
                by=st.session_state.sort_column,
                ascending=(st.session_state.sort_direction == "asc"),
                key=lambda x: pd.to_numeric(x.str.replace(" ", "").str.replace(",", "."), errors="coerce").fillna(-float('inf')) if x.name in [
                    "Quantité", "Prix d'Acquisition", "Valeur", "Prix Actuel", "Valeur Actuelle",
                    "Haut 52 Semaines", "Valeur H52", "Objectif LT", "Valeur LT", "Last Price",
                    "Momentum (%)", "Z-Score"
                ] else x.str.lower()
            )
        else:
            df_disp = df_disp.sort_values(
                by=st.session_state.sort_column,
                ascending=(st.session_state.sort_direction == "asc"),
                key=lambda x: x.str.lower() if x.name in ["Ticker", "Nom", "Catégorie", "Signal", "Action", "Justification", "Devise"] else x
            )

    total_valeur_str = format_fr(total_valeur, 2)
    total_actuelle_str = format_fr(total_actuelle, 2)
    total_h52_str = format_fr(total_h52, 2)
    total_lt_str = format_fr(total_lt, 2)

    # Boutons de tri en grille
    st.markdown("""
    <style>
      .button-grid {
        display: grid;
        grid-template-columns: 60px 200px 100px 40px 60px 80px 80px 80px 80px 80px 80px 80px 80px 80px 80px 150px 150px 150px;
        gap: 0;
        background: #363636;
        position: sticky;
        top: 0;
        z-index: 3;
      }
      .header-button {
        background: #363636;
        color: white;
        border: none;
        padding: 8px;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-size: 12px;
        cursor: pointer;
        text-align: center;
        box-sizing: border-box;
        width: 100%;
      }
      .header-button:hover {
        background: #4a4a4a;
      }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        cols = st.columns([80, 200, 100, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 80, 150, 150, 150, 60])
        for idx, (col, lbl) in enumerate(zip(cols, labels)):
            with col:
                sort_indicator = ""
                if st.session_state.sort_column == lbl:
                    sort_indicator = " ▲" if st.session_state.sort_direction == "asc" else " ▼"
                if st.button(
                    f"{lbl}{sort_indicator}",
                    key=f"sort_{lbl}_{idx}",
                    help=f"Trier par {lbl}",
                    use_container_width=True
                ):
                    if st.session_state.sort_column == lbl:
                        st.session_state.sort_direction = "desc" if st.session_state.sort_direction == "asc" else "asc"
                    else:
                        st.session_state.sort_column = lbl
                        st.session_state.sort_direction = "asc"

    # Construction HTML pour la table
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
      }}
      .portfolio-table td {{
        padding: 6px;
        text-align: right;
        border: none;
        font-size: 11px;
        white-space: nowrap;
      }}
      .portfolio-table td:nth-child(1), /* Ticker */
      .portfolio-table td:nth-child(2), /* Nom */
      .portfolio-table td:nth-child(3), /* Catégorie */
      .portfolio-table td:nth-child(16), /* Signal */
      .portfolio-table td:nth-child(17), /* Action */
      .portfolio-table td:nth-child(18) {{ /* Justification */
        text-align: left;
        white-space: normal;
      }}
      .portfolio-table th:nth-child(1), .portfolio-table td:nth-child(1) {{ /* Ticker */
        width: 80px;
      }}
      .portfolio-table th:nth-child(2), .portfolio-table td:nth-child(2) {{ /* Nom */
        width: 200px;
      }}
      .portfolio-table th:nth-child(3), .portfolio-table td:nth-child(3) {{ /* Catégorie */
        width: 100px;
      }}
      .portfolio-table th:nth-child(4), .portfolio-table td:nth-child(4), /* Quantité */
      .portfolio-table th:nth-child(5), .portfolio-table td:nth-child(5), /* Prix d'Acquisition */
      .portfolio-table th:nth-child(6), .portfolio-table td:nth-child(6), /* Valeur */
      .portfolio-table th:nth-child(7), .portfolio-table td:nth-child(7), /* Prix Actuel */
      .portfolio-table th:nth-child(8), .portfolio-table td:nth-child(8), /* Valeur Actuelle */
      .portfolio-table th:nth-child(9), .portfolio-table td:nth-child(9), /* Haut 52 Semaines */
      .portfolio-table th:nth-child(10), .portfolio-table td:nth-child(10), /* Valeur H52 */
      .portfolio-table th:nth-child(11), .portfolio-table td:nth-child(11), /* Objectif LT */
      .portfolio-table th:nth-child(12), .portfolio-table td:nth-child(12), /* Valeur LT */
      .portfolio-table th:nth-child(13), .portfolio-table td:nth-child(13), /* Last Price */
      .portfolio-table th:nth-child(14), .portfolio-table td:nth-child(14), /* Momentum (%) */
      .portfolio-table th:nth-child(15), .portfolio-table td:nth-child(15) {{ /* Z-Score */
        width: 80px;
      }}
      .portfolio-table th:nth-child(16), .portfolio-table td:nth-child(16), /* Signal */
      .portfolio-table th:nth-child(17), .portfolio-table td:nth-child(17), /* Action */
      .portfolio-table th:nth-child(18), .portfolio-table td:nth-child(18) {{ /* Justification */
        width: 150px;
      }}
      .portfolio-table th:nth-child(19), .portfolio-table td:nth-child(19) {{ /* Devise */
        width: 60px;
      }}
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

    # Ajouter les en-têtes statiques
    for lbl in labels:
        html_code += f'<th>{safe_escape(lbl)}</th>'

    html_code += """
        </tr></thead>
        <tbody>
    """

    for _, row in df_disp.iterrows():
        html_code += "<tr>"
        for lbl in labels:
            val = row[lbl]
            val_str = safe_escape(str(val)) if pd.notnull(val) else ""
            html_code += f"<td>{val_str}</td>"
        html_code += "</tr>"

    # Ligne TOTAL
    html_code += f"""
        <tr class='total-row'>
          <td>TOTAL ({safe_escape(devise_cible)})</td>
          <td></td><td></td><td></td><td></td>
          <td>{safe_escape(total_valeur_str)}</td>
          <td></td>
          <td>{safe_escape(total_actuelle_str)}</td>
          <td></td>
          <td>{safe_escape(total_h52_str)}</td>
          <td></td>
          <td>{safe_escape(total_lt_str)}</td>
          <td></td><td></td><td></td><td></td><td></td><td></td><td></td>
        </tr>
        </tbody>
      </table>
    </div>
    """

    components.html(html_code, height=600, scrolling=True)
