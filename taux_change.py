# taux_change.py

import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import html
import streamlit.components.v1 as components # Toujours nécessaire pour components.html

# --- Fonctions utilitaires ---

# CHANGEMENT ICI : Utilisation de st.cache_resource au lieu de st.cache_data
@st.cache_resource(ttl=60*15) # Cache la ressource (l'objet Ticker) pendant 15 minutes
def get_yfinance_ticker_info(ticker_symbol):
    """
    Récupère des informations de base pour un ticker yfinance.
    Retourne un objet ticker ou None en cas d'erreur.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Tente de récupérer une donnée simple pour valider le ticker
        # On peut appeler .info.get() pour s'assurer que l'objet est bien initialisé
        _ = ticker.info.get('regularMarketPrice') 
        return ticker
    except Exception as e:
        # st.warning(f"Impossible de récupérer les informations pour le ticker {ticker_symbol} : {e}")
        return None

def obtenir_taux_yfinance(devise_source, devise_cible):
    """
    Récupère le taux de change entre deux devises en utilisant yfinance.
    """
    if devise_source.upper() == devise_cible.upper():
        return 1.0

    ticker_symbol = f"{devise_source.upper()}{devise_cible.upper()}=X"
    ticker = get_yfinance_ticker_info(ticker_symbol)

    if ticker:
        try:
            taux = ticker.info.get("regularMarketPrice")
            if taux is not None:
                return float(taux)
            else:
                st.warning(f"Taux 'regularMarketPrice' non trouvé pour {ticker_symbol}.")
                return None
        except Exception as e:
            st.warning(f"Erreur lors de l'extraction du taux pour {ticker_symbol} depuis info : {e}")
            return None
    else:
        # st.warning(f"Aucune donnée yfinance disponible pour {ticker_symbol}.")
        return None

def actualiser_taux_change(devise_cible, devises_uniques):
    """
    Actualise les taux de change pour une devise cible donnée,
    en utilisant les devises uniques du portefeuille.
    """
    taux_dict = {}
    for d in devises_uniques:
        if d.upper() != devise_cible.upper():
            taux = obtenir_taux_yfinance(d, devise_cible)
            if taux is not None:
                taux_dict[d] = taux
            else:
                taux_dict[d] = None 
        else:
            taux_dict[d] = 1.0
    return taux_dict

def format_fr(x, dec):
    """
    Formate un nombre en chaîne de caractères avec la virgule comme séparateur décimal
    et l'espace comme séparateur de milliers (format français).
    """
    if pd.isnull(x):
        return ""
    s = f"{x:,.{dec}f}"
    return s.replace(",", " ").replace(".", ",")

# --- Fonction d'affichage du tableau des taux de change ---

def afficher_tableau_taux_change(devise_cible, fx_rates):
    """
    Génère et affiche le tableau HTML stylisé des taux de change.
    """
    if not fx_rates:
        st.info("Aucun taux de change valide récupéré ou aucune devise unique dans le portefeuille.")
        return

    df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise source", f"Taux vers {devise_cible}"])
    df_fx = df_fx.sort_values(by="Devise source")

    html_code = f"""
    <style>
      .table-container {{ max-height: 300px; overflow-y: auto; border: 1px solid #ddd; border-radius: 5px; }}
      .fx-table {{ width: 100%; border-collapse: collapse; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
      .fx-table th {{
        background: #363636; color: white; padding: 6px; text-align: center; border: none;
        position: sticky; top: 0; z-index: 2; font-size: 12px;
      }}
      .fx-table td {{
        padding: 6px; text-align: right; border: none; font-size: 11px;
      }}
      .fx-table td:first-child {{ text-align: left; }}
      .fx-table tr:nth-child(even) {{ background: #f8f8f8; }}
      .fx-table tr:hover {{ background: #e6f7ff; }}
    </style>
    <div class="table-container">
      <table class="fx-table">
        <thead><tr><th>Devise source</th><th>Taux vers {html.escape(devise_cible)}</th></tr></thead>
        <tbody>
    """
    for _, row in df_fx.iterrows():
        taux_str = format_fr(row[f"Taux vers {devise_cible}"], 6) if pd.notnull(row[f"Taux vers {devise_cible}"]) else "N/A"
        html_code += f"<tr><td>{html.escape(str(row['Devise source']))}</td><td>{taux_str}</td></tr>"
    html_code += """
        </tbody>
      </table>
    </div>
    """
    components.html(html_code, height=250, scrolling=True)
    st.markdown(f"_Dernière mise à jour : {datetime.datetime.now().strftime('%H:%M:%S')}_")
