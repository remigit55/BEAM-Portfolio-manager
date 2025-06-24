import streamlit as st
import pandas as pd
import datetime
import pytz # Make sure this is imported
import html
import streamlit.components.v1 as components
from data_fetcher import fetch_fx_rates

def format_fr(value, decimals):
    """
    Formate un nombre en chaîne de caractères avec la virgule comme séparateur décimal
    et l'espace comme séparateur de milliers (format français).
    """
    if pd.isna(value):
        return ""
    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(",", " ").replace(".", ",")

def afficher_tableau_taux_change(devise_cible, fx_rates):
    """
    Génère et affiche le tableau HTML stylisé des taux de change.
    Args:
        devise_cible (str): The target currency (e.g., "EUR").
        fx_rates (dict): Dictionary of currency codes to exchange rates.
    """
    if not fx_rates or not isinstance(fx_rates, dict):
        st.info("Aucun taux de change valide disponible. Veuillez vérifier les données ou actualiser les taux.")
        return

    df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise source", f"Taux vers {devise_cible}"])
    df_fx = df_fx.sort_values(by="Devise source")

    st.markdown("#### Taux de Change Actuels")
    st.info("Les taux sont automatiquement mis à jour à chaque chargement de fichier ou toutes les 60 secondes, ou lors d'un changement de devise cible.")

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
    components.html(html_code, height=400, scrolling=True)

    # --- Start of Timezone Adjustment for FX rates ---
    last_fx_update_time = st.session_state.get("last_update_time_fx")

    if last_fx_update_time and last_fx_update_time != datetime.datetime.min:
        try:
            # Ensure last_fx_update_time is timezone-aware
            if last_fx_update_time.tzinfo is None:
                # Assume UTC if datetime object is naive
                utc_aware_time = last_fx_update_time.replace(tzinfo=datetime.timezone.utc)
            else:
                utc_aware_time = last_fx_update_time

            paris_tz = pytz.timezone('Europe/Paris')
            local_time = utc_aware_time.astimezone(paris_tz)
            formatted_time = local_time.strftime("%d/%m/%Y à %H:%M:%S")
            st.markdown(f"_Dernière mise à jour des taux de change : **{formatted_time}**_")
        except pytz.UnknownTimeZoneError:
            st.warning("Erreur de fuseau horaire 'Europe/Paris'. Affichage de l'heure UTC.")
            st.markdown(f"_Dernière mise à jour des taux de change : **{last_fx_update_time.strftime('%d/%m/%Y à %H:%M:%S')} UTC**_")
        except Exception as e:
            # Catch any other potential errors during time formatting
            st.warning(f"Erreur lors du formatage de l'heure de mise à jour des taux de change : {e}")
            st.markdown(f"_Dernière mise à jour des taux de change (format brut) : **{last_fx_update_time.strftime('%d/%m/%Y à %H:%M:%S')}**_")
    else:
        st.info("_Les taux de change n'ont pas encore été mis à jour._")
    # --- End of Timezone Adjustment for FX rates ---

    # The line below was removed as the timestamp display is now handled above this HTML block
    # st.markdown(f"_Dernière mise à jour : {datetime.datetime.now().strftime('%H:%M:%S')}_")
