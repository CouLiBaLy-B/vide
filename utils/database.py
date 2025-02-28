
# utils/database.py
import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor
from utils.config import Config
import logging

logger = logging.getLogger(__name__)

class PostgresDB:
    """Interface pour la base de données PostgreSQL"""
    
    def __init__(self):
        self.conn = None
        self.cursor = None
        
    def connect(self):
        """Établir une connexion à la base de données"""
        try:
            self.conn = psycopg2.connect(
                host=Config.POSTGRES_HOST,
                port=Config.POSTGRES_PORT,
                database=Config.POSTGRES_DB,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASS
            )
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            logger.info("Connexion établie avec PostgreSQL")
            
        except Exception as e:
            logger.error(f"Erreur de connexion à PostgreSQL: {e}")
            raise
    
    def close(self):
        """Fermer la connexion"""
        if self.conn:
            if self.cursor:
                self.cursor.close()
            self.conn.close()
            logger.info("Connexion PostgreSQL fermée")
    
    def execute(self, query, params=None):
        """Exécuter une requête et valider la transaction"""
        if not self.conn or self.conn.closed:
            self.connect()
        
        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            logger.debug(f"Requête exécutée: {query}")
            return True
        
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Erreur d'exécution de requête: {e}")
            return False
    
    def fetch_one(self, query, params=None):
        """Exécuter une requête et retourner un seul résultat"""
        if not self.conn or self.conn.closed:
            self.connect()
        
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchone()
        
        except Exception as e:
            logger.error(f"Erreur de requête fetch_one: {e}")
            return None
    
    def fetch_all(self, query, params=None):
        """Exécuter une requête et retourner tous les résultats"""
        if not self.conn or self.conn.closed:
            self.connect()
        
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        
        except Exception as e:
            logger.error(f"Erreur de requête fetch_all: {e}")
            return []
    
    def to_dataframe(self, query, params=None):
        """Exécuter une requête et retourner les résultats sous forme de DataFrame"""
        if not self.conn or self.conn.closed:
            self.connect()
        
        try:
            return pd.read_sql_query(query, self.conn, params=params)
        
        except Exception as e:
            logger.error(f"Erreur de conversion en DataFrame: {e}")
            return pd.DataFrame()
    
    def init_tables(self):
        """Initialiser les tables nécessaires si elles n'existent pas"""
        # Table pour les recommandations des analystes
        self.execute('''
            CREATE TABLE IF NOT EXISTS analyst_recommendations (
                id SERIAL PRIMARY KEY,
                analyst_name VARCHAR(50) NOT NULL,
                symbol VARCHAR(10) NOT NULL,
                signal VARCHAR(10) NOT NULL,  -- BUY, SELL, HOLD
                confidence FLOAT,
                rationale TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table pour les décisions du gestionnaire
        self.execute('''
            CREATE TABLE IF NOT EXISTS portfolio_allocations (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                weight FLOAT NOT NULL,
                target_shares INT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table pour les transactions du trader
        self.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                transaction_type VARCHAR(10) NOT NULL,  -- BUY, SELL
                price FLOAT NOT NULL,
                quantity INT NOT NULL,
                total_value FLOAT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table pour les évaluations des performances
        self.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                date DATE NOT NULL,
                portfolio_value FLOAT NOT NULL,
                cash_balance FLOAT NOT NULL,
                daily_return FLOAT,
                sharpe_ratio FLOAT,
                max_drawdown FLOAT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table pour les performances des analystes
        self.execute('''
            CREATE TABLE IF NOT EXISTS analyst_performance (
                id SERIAL PRIMARY KEY,
                analyst_name VARCHAR(50) NOT NULL,
                accuracy_rate FLOAT,
                total_signals INT,
                successful_signals INT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        logger.info("Tables initialisées avec succès")

