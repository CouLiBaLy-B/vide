
# utils/logging_utils.py
import logging
import os
from datetime import datetime
from utils.config import Config

def setup_logger(agent_name):
    """
    Configure et retourne un logger pour un agent spécifique
    """
    # Créer le répertoire de logs s'il n'existe pas
    os.makedirs('logs', exist_ok=True)
    
    # Configuration du logger
    logger = logging.getLogger(agent_name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # Format de log avec horodatage, nom de l'agent et niveau
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Handler pour la console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_format)
    logger.addHandler(console_handler)
    
    # Handler pour le fichier
    today = datetime.now().strftime('%Y-%m-%d')
    file_handler = logging.FileHandler(f'logs/{agent_name}_{today}.log')
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    
    return logger
