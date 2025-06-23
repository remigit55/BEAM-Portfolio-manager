# taux_change.py

import streamlit as st
import pandas as pd
import datetime
import html
import streamlit.components.v1 as components # Toujours nécessaire pour components.html
import requests # Ajout de l'import pour les requêtes HTTP
import json     # Ajout de l'import pour traiter le JSON
import numpy as np # Pour np.nan et np.isnan


# --- Fonctions utilitaires (celles qui étaient là, mais plus utilisées pour les taux) ---
# L'ancienne fonction obtenir_taux_yfinance est remplacée par l'appel direct à exchangerate.host
# Je laisse get_yfinance_ticker_info au cas où elle serait utilisée ailleurs, mais elle n'est plus pertinente ici.
# @st.cache_resource(ttl=60*15) # Cache la ressource (l'objet Ticker) pendant 15 minutes
# def get_yfinance_ticker_info(ticker_symbol):
#     """
#     Récupère des informations de base pour un ticker yfinance.
#     Retourne un objet ticker ou None en cas d'erreur.
#     """
#     try:
#         ticker = yf.Ticker(ticker_symbol)
#         # Tente de récupérer une donnée simple pour valider le ticker
#         # On peut appeler .info.get() pour s'assurer que l'objet est bien initialisé
#         _ = ticker.info.get('regularMarketPrice')
#         return ticker
#     except Exception as e:
#         # st.warning(f"Impossible de récupérer les informations pour le ticker {ticker_symbol} : {e}")
#         return None

# # Cette fonction n'est plus utilisée, remplacée par l'implémentation directe dans actualiser_taux_change
# def obtenir_taux_yfinance(devise_source, devise_cible):
#     """
#     Récupère le taux de change entre deux devises en utilisant yfinance.
#     """
#     if devise_source.upper() == devise_cible.upper():
#         return 1.0

#     ticker_symbol = f"{devise_source.upper()}{devise_cible.upper()}=X"
#     ticker = get_yfinance_ticker_info(ticker_symbol)

#     if ticker:
#         try:
#             # On télécharge les données sur une courte période pour obtenir le prix actuel
#             data = ticker.history(period="1d") # Utilise history au lieu de download pour des raisons de performance et de cache
#             if not data.empty and 'Close' in data.columns and not data['Close'].empty:
#                 return data['Close'].iloc[-1]
#             else:
#                 # Si pas de données directes, essayer la paire inverse et inverser le taux
#                 inverse_ticker_symbol = f"{devise_cible.upper()}{devise_source.upper()}=X"
#                 inverse_ticker = get_yfinance_ticker_info(inverse_ticker_symbol)
#                 if inverse_ticker:
#                     inverse_data = inverse_ticker.history(period="1d")
#                     if not inverse_data.empty and 'Close' in inverse_data.columns and not inverse_data['Close'].empty:
#                         inverse_rate = inverse_data['Close'].iloc[-1]
#                         if inverse_rate != 0:
#                             return 1.0 / inverse_rate
#         except Exception as e:
#             st.warning(f"Impossible de récupérer le taux pour {ticker_symbol} ou son inverse : {e}")
#     return np.nan # Retourne NaN si le taux n'est pas trouvé


# Utilisation de st.cache_data pour les taux de change (valable 1 minute)
@st.cache_data(ttl=60)
def actualiser_taux_change(devise_cible="EUR", devises_uniques=None):
    """
    Récupère les taux de change actuels par rapport à une devise cible en utilisant exchangerate.host.
    """
    st.info(f"Actualisation des taux de change avec exchangerate.host. Devise cible: {devise_cible}")
    taux_actuels = {}

    # Assurez-vous que la devise cible est en majuscules
    devise_cible = devise_cible.strip().upper()

    # Si devises_uniques n'est pas fourni, utilisez la liste par défaut.
    if devises_uniques is None:
        devises_a_traiter = ["USD", "EUR", "GBP", "CAD", "JPY", "CHF"]
    else:
        # Nettoyer et mettre en majuscules toutes les devises, et s'assurer que la devise cible est incluse
        devises_a_traiter = list(set([c.strip().upper() for c in devises_uniques] + [devise_cible]))
    
    # Le taux de la devise cible par rapport à elle-même est 1.0
    taux_actuels[f"{devise_cible}/{devise_cible}"] = 1.0
    # Ajouter la devise cible seule pour compatibilité avec d'autres fonctions si nécessaire
    taux_actuels[devise_cible] = 1.0


    # Construire la liste des symboles pour l'API
    symbols_str = ",".join([c for c in devises_a_traiter if c != devise_cible])
    
    if not symbols_str: # S'il n'y a que la devise cible
        st.info("Aucune devise unique à convertir autre que la devise cible.")
        return taux_actuels

    # URL de l'API exchangerate.host pour les taux "latest"
    # On utilise la devise cible comme base pour obtenir les taux directement BASE/SYMBOL (TARGET/SOURCE)
    api_url = f"https://api.exchangerate.host/latest?base={devise_cible}&symbols={symbols_str}"
    
    try:
        st.info(f"Requête API pour actualisation des taux: {api_url}")
        response = requests.get(api_url, timeout=5)
        response.raise_for_status() # Lève une exception pour les codes d'erreur HTTP (4xx ou 5xx)
        data = response.json()

        if data.get("success"):
            api_rates = data.get("rates", {})
            st.success(f"Réponse API reçue (succès) pour l'actualisation des taux: {api_rates}")

            for source_currency in devises_a_traiter:
                source_currency = source_currency.strip().upper()
                if source_currency == devise_cible:
                    continue

                # Le taux de l'API est BASE/SYMBOL, soit TARGET/SOURCE.
                # Nous voulons SOURCE/TARGET. Donc il faut 1 / (TARGET/SOURCE).
                # Exemple : base=EUR, symbol=USD. api_rates['USD'] = 1.08 (1 EUR = 1.08 USD)
                # On veut USD/EUR, ce qui signifie 1 USD = ? EUR.
                # Donc 1 USD = 1/1.08 EUR = 0.9259 EUR.
                
                if source_currency in api_rates and pd.notna(api_rates[source_currency]) and api_rates[source_currency] != 0:
                    taux = 1 / api_rates[source_currency]
                    taux_actuels[f"{source_currency}/{devise_cible}"] = taux
                    st.success(f"✔️ Taux {source_currency}/{devise_cible} (via {devise_cible}/{source_currency} inversé) : {taux:.4f}")
                else:
                    st.warning(f"Taux de {source_currency} par rapport à {devise_cible} non trouvé ou invalide dans la réponse API. Taux pour {source_currency}/{devise_cible} sera N/A.")
                    taux_actuels[f"{source_currency}/{devise_cible}"] = np.nan # Si non trouvé, NaN

        else:
            st.error(f"❌ La réponse de l'API exchangerate.host indique un échec lors de l'actualisation des taux: {data.get('error', 'Pas de message d\'erreur détaillé.')}")
            for source_currency in devises_a_traiter:
                if source_currency != devise_cible:
                    taux_actuels[f"{source_currency}/{devise_cible}"] = np.nan

    except requests.exceptions.RequestException as e:
        st.error(f"❌ Erreur de requête HTTP lors de l'actualisation des taux de change : {e}")
        for source_currency in devises_a_traiter:
            if source_currency != devise_cible:
                taux_actuels[f"{source_currency}/{devise_cible}"] = np.nan
    except json.JSONDecodeError as e:
        st.error(f"❌ Erreur de décodage JSON de la réponse API lors de l'actualisation des taux : {e}")
        for source_currency in devises_a_traiter:
            if source_currency != devise_cible:
                taux_actuels[f"{source_currency}/{devise_cible}"] = np.nan
    except Exception as e:
        st.error(f"❌ Une erreur inattendue est survenue lors de l'actualisation des taux de change : {e}")
        for source_currency in devises_a_traiter:
            if source_currency != devise_cible:
                taux_actuels[f"{source_currency}/{devise_cible}"] = np.nan

    st.info("Fin de l'actualisation des taux de change.")
    return taux_actuels

# Importez la fonction format_fr de utils.py
try:
    from utils import format_fr
except ImportError:
    st.error("Erreur: Impossible d'importer la fonction format_fr de utils.py. Veuillez vous assurer que utils.py existe et contient cette fonction.")
    # Fallback pour éviter une erreur si utils.py n'est pas accessible ou si format_fr est manquant
    def format_fr(value, decimals=2):
        if pd.isna(value):
            return "N/A"
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def afficher_tableau_taux_change(devise_cible, fx_rates):
    """
    Affiche un tableau des taux de change actuels dans un style plus compact.
    """
    st.subheader(f"Taux de Change Actuels (Base : {devise_cible})")
    
    if not fx_rates:
        st.info("Aucun taux de change disponible pour l'affichage.")
        return

    # Préparer les données pour le DataFrame
    data_for_df = []
    # Sortir les clés pour s'assurer que la devise cible est en premier, puis trier le reste
    sorted_keys = sorted([k for k in fx_rates.keys() if k.split('/')[0] != devise_cible])
    
    # Ajouter la devise cible en premier si elle existe sous la forme "EUR/EUR" ou "EUR"
    if f"{devise_cible}/{devise_cible}" in fx_rates:
        data_for_df.append({"Devise source": devise_cible, f"Taux vers {devise_cible}": fx_rates[f"{devise_cible}/{devise_cible}"]})
    elif devise_cible in fx_rates: # Fallback si seulement la devise est la clé
        data_for_df.append({"Devise source": devise_cible, f"Taux vers {devise_cible}": fx_rates[devise_cible]})


    for key in sorted_keys:
        source_currency = key.split('/')[0] # Extraire la devise source de la clé "SOURCE/CIBLE"
        # S'assurer que ce n'est pas la devise cible elle-même
        if source_currency == devise_cible:
            continue
        data_for_df.append({
            "Devise source": source_currency,
            f"Taux vers {devise_cible}": fx_rates[key]
        })

    df_fx = pd.DataFrame(data_for_df, columns=["Devise source", f"Taux vers {devise_cible}"])
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
        taux_str = format_fr(row[f"Taux vers {devise_cible}"], 4) # 4 décimales pour les taux
        html_code += f"""
            <tr>
                <td>{html.escape(row["Devise source"])}</td>
                <td>{taux_str}</td>
            </tr>
        """
    html_code += """
        </tbody>
      </table>
    </div>
    """
    components.html(html_code, height=320)
