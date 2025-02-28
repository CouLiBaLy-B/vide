# utils/config.py
import os
from dotenv import load_dotenv

# Charger les variables d'environnement du fichier .env
load_dotenv()

class Config:
    # Configuration générale
    TRADING_HORIZON = os.getenv('TRADING_HORIZON', 'LONG_TERM')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_DRAWDOWN_THRESHOLD = float(os.getenv('MAX_DRAWDOWN_THRESHOLD', '10'))
    
    # Configuration RabbitMQ
    RABBITMQ_HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    RABBITMQ_PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
    RABBITMQ_USER = os.getenv('RABBITMQ_USER', 'guest')
    RABBITMQ_PASS = os.getenv('RABBITMQ_PASS', 'guest')
    RABBITMQ_VHOST = os.getenv('RABBITMQ_VHOST', '/')
    
    # Configuration PostgreSQL
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
    POSTGRES_PASS = os.getenv('POSTGRES_PASS', 'postgres')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'trading_db')
    
    # Configuration API X (Twitter)
    X_API_KEY = os.getenv('X_API_KEY', '')
    X_API_SECRET = os.getenv('X_API_SECRET', '')
    X_ACCESS_TOKEN = os.getenv('X_ACCESS_TOKEN', '')
    X_ACCESS_SECRET = os.getenv('X_ACCESS_SECRET', '')
    
    # Paramètres agents
    TRADING_SYMBOLS = os.getenv('TRADING_SYMBOLS', 'AAPL,MSFT,GOOGL').split(',')
