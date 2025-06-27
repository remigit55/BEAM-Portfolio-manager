# period_selector_component.py

import streamlit.components.v1 as components
import os

# Définir si nous sommes en mode développement (pour React dev server) ou en production (pour le build)
_RELEASE = True # Mettez à False si vous développez le composant React localement

if _RELEASE:
    # En production, le composant est chargé depuis le dossier 'build'
    _component_func = components.declare_component(
        "period_selector",
        path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "build")
    )
else:
    # En développement, le composant est chargé depuis le serveur de développement React
    _component_func = components.declare_component(
        "period_selector",
        url="http://localhost:3001", # Port par défaut du serveur de développement React
    )

def period_selector(period_options, selected_period, key=None):
    """
    Composant Streamlit personnalisé pour afficher les options de période sous forme de texte cliquable.

    Args:
        period_options (dict): Un dictionnaire mappant les étiquettes de période (ex: "1W")
                               aux valeurs de timedelta correspondantes.
        selected_period (str): L'étiquette de la période actuellement sélectionnée.
        key (str, optional): Une clé unique pour ce composant, nécessaire pour Streamlit.
    Returns:
        str: L'étiquette de la période nouvellement sélectionnée par l'utilisateur.
    """
    # Passe les étiquettes des périodes et l'étiquette sélectionnée au composant frontend
    component_value = _component_func(
        period_labels=list(period_options.keys()),
        selected_label=selected_period,
        key=key,
        default=selected_period # Valeur par défaut si aucune interaction n'a eu lieu
    )
    return component_value

