import pandas as pd
from datetime import datetime, date
from sqlalchemy import create_engine, Column, Integer, String, Date, Text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import json
import os

# Configuration de la base de données SQLite
DATABASE_URL = "sqlite:///portfolio.db"
Engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=Engine)
Base = declarative_base()

# Définition du modèle de données pour les snapshots du portefeuille
class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshots'
    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_date = Column(Date, unique=True, nullable=False) # Date du snapshot
    target_currency = Column(String) # Devise cible pour ce snapshot
    portfolio_data_json = Column(Text) # Stockage du DataFrame sous forme de JSON

    def __repr__(self):
        return f"<PortfolioSnapshot(date='{self.snapshot_date}', currency='{self.target_currency}')>"

# Assure-toi que les tables sont créées (à appeler une seule fois au démarrage de l'app ou lors de l'initialisation)
def initialize_portfolio_journal_db():
    Base.metadata.create_all(Engine)

# Appelle l'initialisation de la base de données
initialize_portfolio_journal_db()

def save_portfolio_snapshot(snapshot_date, df_portfolio_state, target_currency):
    """
    Sauvegarde un snapshot complet de l'état du portefeuille pour une date donnée dans la base de données SQLite.
    Le DataFrame est converti en JSON pour le stockage.
    """
    if df_portfolio_state is None or df_portfolio_state.empty:
        print(f"DEBUG: df_portfolio_state est vide ou None pour la date {snapshot_date}. Rien à sauvegarder.")
        return

    cols_to_save = [
        "Ticker", "Quantité", "Acquisition", "Devise", "Catégorie", "Objectif_LT"
    ]
    df_save = df_portfolio_state.copy()
    existing_cols = [col for col in cols_to_save if col in df_save.columns]
    df_save = df_save[existing_cols]

    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
        if col in df_save.columns:
            df_save[col] = pd.to_numeric(df_save[col], errors='coerce')
            df_save[col] = df_save[col].fillna(0)

    portfolio_data_json = df_save.to_json(orient="records")

    session = Session()
    try:
        # Vérifier si un snapshot pour cette date existe déjà
        existing_snapshot = session.query(PortfolioSnapshot).filter_by(snapshot_date=snapshot_date).first()

        if existing_snapshot:
            # Mettre à jour l'enregistrement existant
            existing_snapshot.target_currency = target_currency
            existing_snapshot.portfolio_data_json = portfolio_data_json
            print(f"DEBUG: Snapshot du {snapshot_date} mis à jour.")
        else:
            # Créer un nouvel enregistrement
            new_snapshot = PortfolioSnapshot(
                snapshot_date=snapshot_date,
                target_currency=target_currency,
                portfolio_data_json=portfolio_data_json
            )
            session.add(new_snapshot)
            print(f"DEBUG: Nouveau snapshot du {snapshot_date} créé.")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"ERREUR lors de la sauvegarde du snapshot: {e}")
    finally:
        session.close()

def load_portfolio_journal():
    """
    Charge le journal historique du portefeuille depuis la base de données SQLite.
    Retourne une liste de dictionnaires, chaque dict contenant 'date', 'target_currency' et 'portfolio_data'.
    'portfolio_data' est un DataFrame Pandas.
    """
    session = Session()
    try:
        all_snapshots = session.query(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_date).all()

        loaded_data = []
        for snapshot_obj in all_snapshots:
            portfolio_df = pd.DataFrame()
            if snapshot_obj.portfolio_data_json:
                try:
                    portfolio_df = pd.DataFrame(json.loads(snapshot_obj.portfolio_data_json))
                    # Reconverting types might be necessary if JSON serialization changed them
                    for col in ["Quantité", "Acquisition", "Objectif_LT"]:
                        if col in portfolio_df.columns:
                            portfolio_df[col] = pd.to_numeric(portfolio_df[col], errors='coerce')
                except json.JSONDecodeError as e:
                    print(f"WARNING: Erreur de décodage JSON pour le snapshot du {snapshot_obj.snapshot_date}: {e}")
                    portfolio_df = pd.DataFrame() # Retourne un DataFrame vide en cas d'erreur

            loaded_data.append({
                "date": snapshot_obj.snapshot_date,
                "target_currency": snapshot_obj.target_currency,
                "portfolio_data": portfolio_df
            })
        print(f"DEBUG: {len(loaded_data)} snapshots chargés depuis la base de données.")
        return loaded_data
    except Exception as e:
        print(f"ERREUR lors du chargement du journal: {e}")
        return []
    finally:
        session.close()
