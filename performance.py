# performance.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import builtins # IMPORTANT : Explicitement importer builtins pour gérer les problèmes potentiels avec str()

# Importez uniquement ce qui est nécessaire pour cette version simplifiée
from historical_data_fetcher import fetch_stock_history 
from utils import format_fr # Gardez utils pour le formatage, assurez-vous qu'il ne contient pas 'str =' ou 'def str('

def display_performance_history():
    """
    Affiche la performance historique des prix d'un ticker sélectionné.
    Ceci est une version simplifiée pour le débogage et l'isolation.
    """
