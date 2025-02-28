
# agents/base_agent.py
import time
import signal
import sys
from utils.config import Config
from utils.messaging import RabbitMQ
from utils.database import PostgresDB
from utils.logging_utils import setup_logger

class BaseAgent:
    """Classe de base pour tous les agents du système de trading"""
    
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.logger = setup_logger(agent_name)
        self.rabbitmq = RabbitMQ()
        self.db = PostgresDB()
        self.running = True
        
        # Configuration des gestionnaires de signaux pour arrêt gracieux
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info(f"Agent {agent_name} initialisé")
    
    def signal_handler(self, sig, frame):
        """Gérer les signaux pour arrêter proprement l'agent"""
        self.logger.info(f"Signal {sig} reçu, arrêt en cours...")
        self.running = False
        self.cleanup()
        sys.exit(0)
    
    def setup(self):
        """Configuration initiale de l'agent"""
        try:
            # Connexion à RabbitMQ
            self.rabbitmq.connect()
            
            # Connexion à PostgreSQL
            self.db.connect()
            
            # Initialiser les structures nécessaires
            self.init_agent_structure()
            
            self.logger.info(f"Configuration de l'agent {self.agent_name} terminée")
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la configuration: {e}")
            return False
    
    def init_agent_structure(self):
        """Initialiser les structures spécifiques de l'agent (à surcharger)"""
        pass
    
    def process(self):
        """Traitement principal de l'agent (à surcharger)"""
        self.logger.warning("Méthode process() non implémentée")
    
    def run(self):
        """Exécuter l'agent"""
        if not self.setup():
            self.logger.error("Échec de la configuration, arrêt de l'agent")
            return
        
        self.logger.info(f"Agent {self.agent_name} démarré")
        
        try:
            while self.running:
                self.process()
                
                # Éviter de surcharger le CPU
                time.sleep(0.1)
                
        except Exception as e:
            self.logger.error(f"Erreur pendant l'exécution: {e}")
        
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Nettoyer les ressources avant l'arrêt"""
        self.logger.info("Nettoyage des ressources...")
        self.rabbitmq.close()
        self.db.close()
        self.logger.info(f"Agent {self.agent_name} arrêté proprement")
