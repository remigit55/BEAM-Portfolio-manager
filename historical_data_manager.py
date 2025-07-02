import pandas as pd
from datetime import datetime, date
from sqlalchemy import create_engine, Column, Integer, String, Date, Float
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os

# Configuration de la base de données SQLite
DATABASE_URL = "sqlite:///portfolio.db" # Même fichier que portfolio_journal
Engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=Engine)
Base = declarative_base()

# Définition du modèle de données pour l'historique des totaux du portefeuille
class PortfolioDailyTotal(Base):
    __tablename__ = 'portfolio_daily_totals'
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    acquisition_value = Column(Float)
    current_value = Column(Float)
    h52_value = Column(Float)
    lt_value = Column(Float)
    currency = Column(String)

    def __repr__(self):
        return f"<PortfolioDailyTotal(date='{self.date}', current_value='{self.current_value}')>"

# Assure-toi que les tables sont créées (à appeler une seule fois)
def initialize_historical_data_db():
    Base.metadata.create_all(Engine)

# Appelle l'initialisation de la base de données
initialize_historical_data_db()

def save_daily_totals(date_obj, acquisition_value, current_value, h52_value, lt_value, currency):
    """
    Sauvegarde les totaux quotidiens du portefeuille dans la base de données SQLite.
    Met à jour l'enregistrement s'il existe déjà pour la date donnée, sinon le crée.
    """
    session = Session()
    try:
        # Vérifier si un enregistrement pour cette date existe déjà
        existing_total = session.query(PortfolioDailyTotal).filter_by(date=date_obj).first()

        if existing_total:
            # Mettre à jour l'enregistrement existant
            existing_total.acquisition_value = acquisition_value
            existing_total.current_value = current_value
            existing_total.h52_value = h52_value
            existing_total.lt_value = lt_value
            existing_total.currency = currency
            print(f"DEBUG: Totaux du {date_obj} mis à jour.")
        else:
            # Créer un nouvel enregistrement
            new_total = PortfolioDailyTotal(
                date=date_obj,
                acquisition_value=acquisition_value,
                current_value=current_value,
                h52_value=h52_value,
                lt_value=lt_value,
                currency=currency
            )
            session.add(new_total)
            print(f"DEBUG: Nouveaux totaux du {date_obj} créés.")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"ERREUR lors de la sauvegarde des totaux quotidiens: {e}")
    finally:
        session.close()


def load_historical_data():
    """
    Charge l'historique des totaux du portefeuille depuis la base de données SQLite.
    Retourne un DataFrame Pandas. Retourne un DataFrame vide si aucune donnée.
    """
    session = Session()
    try:
        all_totals = session.query(PortfolioDailyTotal).order_by(PortfolioDailyTotal.date).all()

        if not all_totals:
            return pd.DataFrame() # Retourne un DataFrame vide si pas de données

        data = []
        for total_obj in all_totals:
            data.append({
                "Date": total_obj.date,
                "Valeur Acquisition": total_obj.acquisition_value,
                "Valeur Actuelle": total_obj.current_value,
                "Valeur H52": total_obj.h52_value,
                "Valeur LT": total_obj.lt_value,
                "Devise": total_obj.currency
            })

        df_history = pd.DataFrame(data)
        df_history["Date"] = pd.to_datetime(df_history["Date"]) # S'assurer que la colonne est au bon format datetime
        print(f"DEBUG: {len(df_history)} enregistrements historiques chargés depuis la base de données.")
        return df_history
    except Exception as e:
        print(f"ERREUR lors du chargement des données historiques: {e}")
        return pd.DataFrame()
    finally:
        session.close()
