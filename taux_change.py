import streamlit as st
import pandas as pd
import datetime
import pytz
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
    Affiche les taux de change dans un tableau standard Streamlit (st.dataframe).
    """
    # st.header("Taux de Change Actuels")
    # st.info("Les taux sont automatiquement mis à jour à chaque chargement de fichier ou toutes les 60 secondes, ou lors d'un changement de devise cible.")

    if st.button("Actualiser les taux", key="manual_fx_refresh_btn_in_tab"):
        with st.spinner("Mise à jour manuelle des devises..."):
            try:
                st.session_state.fx_rates = fetch_fx_rates(devise_cible)
                st.session_state.last_update_time_fx = datetime.datetime.now(datetime.timezone.utc)
                st.session_state.last_devise_cible_for_currency_update = devise_cible
                st.success(f"Taux de change actualisés pour {devise_cible}.")
            except Exception as e:
                st.error(f"Erreur lors de la mise à jour manuelle des taux de change : {e}")
            st.rerun()

    if not fx_rates or not isinstance(fx_rates, dict):
        st.info("Aucun taux de change valide disponible. Veuillez vérifier les données ou actualiser les taux.")
        return

    df_fx = pd.DataFrame(list(fx_rates.items()), columns=["Devise source", f"Taux vers {devise_cible}"])
    df_fx = df_fx.sort_values(by="Devise source")

    st.dataframe(df_fx, use_container_width=True)

    last_fx_update_time = st.session_state.get("last_update_time_fx")
    if last_fx_update_time and last_fx_update_time != datetime.datetime.min:
        try:
            if last_fx_update_time.tzinfo is None:
                utc_aware_time = last_fx_update_time.replace(tzinfo=datetime.timezone.utc)
            else:
                utc_aware_time = last_fx_update_time

            paris_tz = pytz.timezone('Europe/Paris')
            local_time = utc_aware_time.astimezone(paris_tz)
            formatted_time = local_time.strftime("%d/%m/%Y à %H:%M:%S")
            st.markdown(f"_Dernière mise à jour des taux de change : **{formatted_time}**_")
        except Exception as e:
            st.warning(f"Erreur lors de l'affichage de la dernière mise à jour : {e}")
            st.markdown(f"_Dernière mise à jour (UTC) : **{last_fx_update_time.strftime('%d/%m/%Y à %H:%M:%S')}**_")
    else:
        st.info("_Les taux de change n'ont pas encore été mis à jour._")
