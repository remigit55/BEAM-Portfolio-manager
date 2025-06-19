import streamlit as st
import pandas as pd
import requests
import time
import html
# components.html ne sera plus utilisé pour le tableau principal, donc nous pouvons le commenter si nous voulons
# import streamlit.components.v1 as components 
import yfinance as yf

def safe_escape(text):
    """Escape HTML characters safely."""
    # Cette fonction pourrait ne plus être strictement nécessaire si nous n'utilisons plus components.html
    # mais elle ne fait pas de mal de la garder si d'autres parties du code l'utilisent.
    if hasattr(html, 'escape'):
        return html.escape(str(text))
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

@st.cache_data(ttl=3600)
def fetch_fx_rates(base="EUR"):
    try:
        url = f"https://api.exchangerate.host/latest?base={base}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.get("rates", {})
        return data
    except Exception as e:
        st.error(f"Erreur lors de la récupération des taux de change : {e}")
        return {}

@st.cache_data(ttl=900)
def fetch_yahoo_data(t):
    t = str(t).strip().upper()
    if not t: return {"shortName": "", "currentPrice": None, "fiftyTwoWeekHigh": None}

    if "ticker_names_cache" not in st.session_state:
        st.session_state.ticker_names_cache = {}

    if t in st.session_state.ticker_names_cache:
        cached = st.session_state.ticker_names_cache[t]
        if isinstance(cached, dict) and "shortName" in cached:
            return cached
        else:
            del st.session_state.ticker_names_cache[t]
    
    try:
        ticker_obj = yf.Ticker(t)
        info = ticker_obj.info
        
        name = info.get("shortName", f"https://finance.yahoo.com/quote/{t}")
        current_price = info.get("regularMarketPrice", None)
        fifty_two_week_high = info.get("fiftyTwoWeekHigh", None)
        result = {"shortName": name, "currentPrice": current_price, "fiftyTwoWeekHigh": fifty_two_week_high}
        st.session_state.ticker_names_cache[t] = result
        time.sleep(0.05)
        return result
    except Exception as e:
        return {"shortName": f"https://finance.yahoo.com/quote/{t}", "currentPrice": None, "fiftyTwoWeekHigh": None}

@st.cache_data(ttl=3600)
def fetch_momentum_data(ticker, period="5y", interval="1wk"):
    try:
        data = yf.download(ticker, period=period, interval=interval, auto_adjust=True, progress=False)
        if data.empty:
            return {
                "Momentum (%)": None, "Z-Score": None, "Signal": "", "Action": "", "Justification": ""
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
        z = latest.get('Z_Momentum')
        m = latest.get('Momentum', 0) * 100

        if pd.isna(z):
            return {
                "Momentum (%)": None, "Z-Score": None, "Signal": "", "Action": "", "Justification": ""
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
        else:
            signal = "🧊 Survendu"
            action = "Acheter / Renforcer (si signal technique)"
            reason = "Purge excessive, possible bas de cycle"

        return {
            "Momentum (%)": round(m, 2), "Z-Score": round(z, 2), "Signal": signal, "Action": action, "Justification": reason
        }
    except Exception as e:
        return {
            "Momentum (%)": None, "Z-Score": None, "Signal": "", "Action": "", "Justification": ""
        }

def afficher_portefeuille():
    if "df" not in st.session_state or st.session_state.df is None:
        st.warning("Aucune donnée de portefeuille n’a encore été importée.")
        return

    df = st.session_state.df.copy()

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

    for col in ["Quantité", "Acquisition"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if all(c in df.columns for c in ["Quantité", "Acquisition"]):
        df["Valeur"] = df["Quantité"] * df["Acquisition"]

    if len(df.columns) > 5:
        df["Catégorie"] = df.iloc[:, 5].astype(str).fillna("")
    else:
        df["Catégorie"] = ""

    ticker_col = "Ticker" if "Ticker" in df.columns else "Tickers" if "Tickers" in df.columns else None
    
    if ticker_col and not df[ticker_col].dropna().empty:
        unique_tickers = df[ticker_col].dropna().astype(str).str.strip().str.upper().unique()
        
        yahoo_results = {t: fetch_yahoo_data(t) for t in unique_tickers}
        momentum_results = {t: fetch_momentum_data(t) for t in unique_tickers}
        
        df["shortName"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("shortName"))
        df["currentPrice"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("currentPrice"))
        df["fiftyTwoWeekHigh"] = df[ticker_col].apply(lambda x: yahoo_results.get(str(x).strip().upper(), {}).get("fiftyTwoWeekHigh"))
        
        df["Momentum (%)"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Momentum (%)"))
        df["Z-Score"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Z-Score"))
        df["Signal"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Signal"))
        df["Action"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Action"))
        df["Justification"] = df[ticker_col].apply(lambda x: momentum_results.get(str(x).strip().upper(), {}).get("Justification"))
    else:
        df["shortName"] = pd.NA
        df["currentPrice"] = pd.NA
        df["fiftyTwoWeekHigh"] = pd.NA
        df["Momentum (%)"] = pd.NA
        df["Z-Score"] = pd.NA
        df["Signal"] = ""
        df["Action"] = ""
        df["Justification"] = ""

    if all(c in df.columns for c in ["Quantité", "fiftyTwoWeekHigh"]):
        df["Valeur_H52"] = df["Quantité"] * df["fiftyTwoWeekHigh"]
    else:
        df["Valeur_H52"] = pd.NA
    
    if all(c in df.columns for c in ["Quantité", "currentPrice"]):
        df["Valeur_Actuelle"] = df["Quantité"] * df["currentPrice"]
    else:
        df["Valeur_Actuelle"] = pd.NA

    if "Objectif_LT" not in df.columns:
        df["Objectif_LT"] = pd.NA
    else:
        df["Objectif_LT"] = df["Objectif_LT"].astype(str).str.replace(" ", "", regex=False).str.replace(",", ".", regex=False)
        df["Objectif_LT"] = pd.to_numeric(df["Objectif_LT"], errors="coerce")
    df["Valeur_LT"] = df["Quantité"] * df["Objectif_LT"]

    def format_fr(x, dec):
        if pd.isnull(x) or x is None: return ""
        s = f"{x:,.{dec}f}"
        return s.replace(",", " ").replace(".", ",")

    # Maintenant, nous allons créer un dictionnaire de formatage pour st.dataframe / st.data_editor
    # plutôt que de créer des colonnes _fmt.
    column_config = {}
    
    # Définition des colonnes et de leurs labels d'affichage pour st.data_editor
    # L'ordre ici sera l'ordre d'affichage.
    display_columns = []

    # Mapping entre les colonnes internes (df.columns) et les labels d'affichage souhaités
    column_mapping = {
        ticker_col: "Ticker",
        "shortName": "Nom",
        "Catégorie": "Catégorie",
        "Devise": "Devise",
        "Quantité": "Quantité",
        "Acquisition": "Prix d'Acquisition",
        "Valeur": "Valeur",
        "currentPrice": "Prix Actuel",
        "Valeur_Actuelle": "Valeur Actuelle",
        "fiftyTwoWeekHigh": "Haut 52 Semaines",
        "Valeur_H52": "Valeur H52",
        "Objectif_LT": "Objectif LT",
        "Valeur_LT": "Valeur LT",
        "Momentum (%)": "Momentum (%)",
        "Z-Score": "Z-Score",
        "Signal": "Signal",
        "Action": "Action",
        "Justification": "Justification"
    }

    # Ajoutez les colonnes qui existent réellement dans df et configurez leur affichage
    for col_internal, col_display_label in column_mapping.items():
        if col_internal and col_internal in df.columns: # Vérifier que la colonne existe
            display_columns.append(col_internal) # Ajouter la colonne interne pour la sélection finale
            
            # Configuration de l'affichage dans st.data_editor
            if col_internal in ["Quantité"]:
                column_config[col_internal] = st.column_config.NumberColumn(
                    label=col_display_label, format="%d"
                )
            elif col_internal in ["Acquisition", "currentPrice", "fiftyTwoWeekHigh", "Objectif_LT"]:
                 column_config[col_internal] = st.column_config.NumberColumn(
                    label=col_display_label, format="%.4f"
                )
            elif col_internal in ["Valeur", "Valeur_Actuelle", "Valeur_H52", "Valeur_LT"]:
                 column_config[col_internal] = st.column_config.NumberColumn(
                    label=col_display_label, format="%.2f"
                )
            elif col_internal in ["Momentum (%)", "Z-Score"]:
                column_config[col_internal] = st.column_config.NumberColumn(
                    label=col_display_label, format="%.2f"
                )
            else: # Pour les colonnes de texte
                column_config[col_internal] = st.column_config.TextColumn(label=col_display_label)
        elif col_internal in ["shortName", "Signal", "Action", "Justification", "Devise"] and col_internal in df.columns:
            # Cas spécifiques pour les colonnes ajoutées par l'API qui sont de type texte
            display_columns.append(col_internal)
            column_config[col_internal] = st.column_config.TextColumn(label=col_display_label)


    # Filtrer le DataFrame pour ne garder que les colonnes à afficher
    df_display = df[display_columns].copy()

    # Calcul des totaux après toutes les conversions
    total_valeur = df["Valeur_conv"].sum()
    total_actuelle = df["Valeur_Actuelle_conv"].sum()
    total_h52 = df["Valeur_H52_conv"].sum()
    total_lt = df["Valeur_LT_conv"].sum()

    st.subheader("Vue d'ensemble du Portefeuille")

    # Afficher le DataFrame avec st.data_editor pour profiter des fonctionnalités natives
    # La largeur automatique devrait gérer le défilement horizontal si nécessaire.
    st.data_editor(
        df_display,
        column_config=column_config,
        hide_index=True,
        use_container_width=True, # Utilise toute la largeur disponible, ce qui aide au scroll horizontal
        num_rows="dynamic", # Permet d'ajouter/supprimer des lignes si vous le souhaitez (peut être "fixed" si non)
        key="editable_portfolio_data" # Clé unique pour le data_editor
    )

    st.markdown(f"""
    ---
    **Totaux du Portefeuille ({devise_cible}) :**
    * **Valeur d'Acquisition :** {format_fr(total_valeur, 2)} {devise_cible}
    * **Valeur Actuelle :** {format_fr(total_actuelle, 2)} {devise_cible}
    * **Valeur au Haut de 52 Semaines :** {format_fr(total_h52, 2)} {devise_cible}
    * **Valeur Objectif Long Terme :** {format_fr(total_lt, 2)} {devise_cible}
    """)

def main():
    st.set_page_config(layout="wide", page_title="Mon Portefeuille")
    st.title("Gestion de Portefeuille d'Investissement")

    with st.sidebar:
        st.header("Importation de Données")
        uploaded_file = st.file_uploader("Choisissez un fichier CSV", type=["csv"])
        if uploaded_file is not None:
            try:
                df_uploaded = pd.read_csv(uploaded_file)
                st.session_state.df = df_uploaded
                st.success("Fichier importé avec succès !")
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
            st.rerun()

    afficher_portefeuille()

if __name__ == "__main__":
    main()
