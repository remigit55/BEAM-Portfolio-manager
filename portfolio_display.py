# portfolio_display.py

import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import numpy as np

# Import des fonctions utilitaires
from utils import safe_escape, format_fr

# Import des fonctions de récupération de données.
# Assurez-vous que data_fetcher.py existe et contient ces fonctions.
from data_fetcher import fetch_fx_rates, fetch_yahoo_data, fetch_momentum_data

