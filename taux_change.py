# app_portefeuille_fx.py

import streamlit as st
import pandas as pd
import yfinance as yf
import datetime
import time # Nécessaire pour time.sleep
import html
import streamlit.components.v1 as components

# --- Configuration de la page Streamlit ---
st.set_page_config(layout="wide", page_title="Mon Portefeuille FX")
st.title("💱 Taux de Change du Portefeuille")

# --- Fonctions utilitaires ---

@st.cache_data(ttl=60*15) # Cache les données pendant 15 minutes
def get_yfinance_ticker_info(ticker_symbol):
    """
    Récupère des informations de base pour un ticker yfinance.
    Retourne un objet ticker ou None en cas d'erreur.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Tente de récupérer une donnée simple pour valider le ticker
        _ = ticker.info.get('regularMarketPrice')
        return ticker
    except Exception as e:
        st.warning(f"Impossible de récupérer les informations pour le ticker {ticker_symbol} : {e}")
        return None

def obtenir_taux_yfinance(devise_source, devise_cible):
    """
    Récupère le taux de change entre deux devises en utilisant yfinance.
    """
    if devise_source.upper() == devise_cible.upper():
        return 1.0

    # Construire le symbole de la paire de devises pour Yahoo Finance
    ticker_symbol = f"{devise_source.upper()}{devise_cible.upper()}=X"
    
    # Utiliser la fonction get_yfinance_ticker_info qui est mise en cache
    ticker = get_yfinance_ticker_info(ticker_symbol)

    if ticker:
        try:
            # yfinance.Ticker().info retourne un dictionnaire avec diverses informations
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
        st.warning(f"Aucune donnée yfinance disponible pour {ticker_symbol}.")
        return None

def actualiser_taux_change(devise_cible, devises_uniques):
    """
    Actualise les taux de change pour une devise cible donnée,
    en utilisant les devises uniques du portefeuille.
    """
    taux_dict = {}
    for d in devises_uniques:
        if d.upper() != devise_cible.upper(): # Pas besoin de convertir si c'est la même devise
            taux = obtenir_taux_yfinance(d, devise_cible)
            if taux is not None:
                taux_dict[d] = taux
            else:
                # Si le taux n'est pas disponible, on peut choisir de ne pas l'inclure
                # ou de mettre une valeur par défaut comme None/0. Pour l'affichage, None est mieux.
                taux_dict[d] = None 
        else:
            taux_dict[d] = 1.0 # Le taux de la devise cible vers elle-même est 1
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

    # Création du DataFrame pour l'affichage
    df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise source", f"Taux vers {devise_cible}"])
    df_fx = df_fx.sort_values(by="Devise source")

    # Génération du HTML avec CSS
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


# --- Logique d'initialisation et d'exécution principale ---

if __name__ == "__main__":
    
    # Initialisation de l'état de session si non existant
    if "df" not in st.session_state:
        st.session_state.df = None
    if "devise_cible" not in st.session_state:
        st.session_state.devise_cible = "EUR"
    if "fx_rates" not in st.session_state:
        st.session_state.fx_rates = {}
    if "last_update_time" not in st.session_state:
        st.session_state.last_update_time = datetime.datetime.min # Temps très ancien pour forcer l'update initial

    # --- Barre latérale pour l'importation et les options ---
    st.sidebar.header("Options d'importation et de devise")

    uploaded_file = st.sidebar.file_uploader("📥 Importez votre fichier Excel", type=["xlsx"])

    # Logique de chargement du fichier Excel
    if uploaded_file is not None:
        try:
            # Charger le DataFrame seulement si un nouveau fichier est téléchargé
            if "uploaded_file_id" not in st.session_state or st.session_state.uploaded_file_id != uploaded_file.file_id:
                st.session_state.df = pd.read_excel(uploaded_file)
                st.session_state.uploaded_file_id = uploaded_file.file_id
                st.sidebar.success("Fichier importé avec succès !")
                # Forcer une actualisation des taux après un nouvel import de fichier
                st.session_state.last_update_time = datetime.datetime.min
        except Exception as e:
            st.error(f"❌ Erreur lors de la lecture du fichier Excel : {e}")
            st.session_state.df = None
    elif st.session_state.df is None: # Message si aucun fichier n'est chargé au démarrage
        st.info("Veuillez importer un fichier Excel pour commencer.")

    # Sélecteur de devise cible
    devise_options = ["EUR", "USD", "GBP", "CHF", "JPY"]
    st.session_state.devise_cible = st.sidebar.selectbox(
        "💱 Convertir toutes les valeurs en :",
        devise_options,
        index=devise_options.index(st.session_state.devise_cible) if st.session_state.devise_cible in devise_options else 0,
        key="devise_select"
    )

    # Conteneur pour l'affichage dynamique des taux de change
    # Ceci est essentiel pour l'actualisation automatique
    placeholder_taux = st.empty()

    # Logique d'actualisation des taux de change (manuelle ou automatique)
    if st.button("Actualiser les taux (manuel)"):
        with st.spinner("Mise à jour manuelle des taux de change..."):
            devise_cible = st.session_state.devise_cible
            devises_uniques = []
            if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
            st.session_state.fx_rates = actualiser_taux_change(devise_cible, devises_uniques)
            st.session_state.last_update_time = datetime.datetime.now() # Met à jour le temps de la dernière actualisation
            st.success(f"Taux de change actualisés pour {devise_cible} (manuel).")
            # Forcer un re-run pour afficher les données actualisées
            st.rerun()

    # Boucle d'actualisation automatique
    while True:
        current_time = datetime.datetime.now()
        # Actualisation toutes les 60 secondes OU si c'est la première exécution (min time)
        # OU si un nouveau fichier a été chargé (last_update_time réinitialisé)
        if (current_time - st.session_state.last_update_time).total_seconds() >= 60 or \
           st.session_state.last_update_time == datetime.datetime.min:
            
            with placeholder_taux.container(): # Met le spinner dans le placeholder
                with st.spinner("Mise à jour des taux de change automatique..."):
                    devise_cible = st.session_state.devise_cible
                    devises_uniques = []
                    if st.session_state.df is not None and "Devise" in st.session_state.df.columns:
                        devises_uniques = sorted(set(st.session_state.df["Devise"].dropna().unique()))
                    
                    st.session_state.fx_rates = actualiser_taux_change(devise_cible, devises_uniques)
                    st.session_state.last_update_time = datetime.datetime.now() # Met à jour le temps de la dernière actualisation
                    st.success(f"Taux de change actualisés pour {devise_cible} (automatique).")

            # Affiche le tableau des taux de change avec les données actualisées
            with placeholder_taux.container(): # Met le tableau dans le placeholder
                afficher_tableau_taux_change(st.session_state.devise_cible, st.session_state.fx_rates)
            
            # Attente avant la prochaine vérification (pour éviter de consommer trop de CPU)
            time.sleep(1) # Attendre 1 seconde avant de revérifier, le re-run se fera quand même toutes les 60s
        else:
            # Si pas d'actualisation nécessaire, afficher les données actuelles
            with placeholder_taux.container():
                afficher_tableau_taux_change(st.session_state.devise_cible, st.session_state.fx_rates)
            
            # Calculer le temps restant avant la prochaine actualisation pour ne pas bloquer
            time_to_sleep = 60 - (current_time - st.session_state.last_update_time).total_seconds()
            if time_to_sleep > 0:
                time.sleep(time_to_sleep) # Attend le temps restant avant la prochaine actualisation de 60s
            else:
                time.sleep(1) # Attendre juste un peu pour éviter une boucle trop rapide
