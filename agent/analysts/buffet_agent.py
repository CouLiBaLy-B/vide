# agents/analysts/buffet_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from utils.config import Config
import pandas as pd
import json
import time

class BuffetAgent(BaseAgent):
    """
    Agent inspiré de la philosophie d'investissement de Warren Buffet.
    
    Métriques clés:
    - ROE > 10%
    - Ratio dette/équité < 0.5
    - Croissance des bénéfices sur 5 ans > 5%
    - P/E < moyenne sectorielle
    - P/B < 1.5
    """
    
    def __init__(self):
        super().__init__("buffet_agent")
        self.market_data = MarketData()
        # Intervalle en secondes entre les analyses (4h pour le long terme, 5m pour le court terme)
        self.analysis_interval = 14400 if Config.TRADING_HORIZON == 'LONG_TERM' else 300
        self.last_analysis_time = 0
    
    def init_agent_structure(self):
        """Initialiser les queues et échanges RabbitMQ"""
        # Exchange pour les signaux d'analyse
        self.rabbitmq.declare_exchange('analyst_signals', 'direct')
        
        # Queue pour les signaux
        self.rabbitmq.declare_queue('buffet_signals')
        
        # Lier la queue à l'exchange
        self.rabbitmq.bind_queue('buffet_signals', 'analyst_signals', 'buffet')
        
        self.logger.info("Structures RabbitMQ initialisées")
    
    def process(self):
        """Traitement principal: analyse des actions et génération de signaux"""
        current_time = time.time()
        
        # Vérifier si c'est le moment d'effectuer une nouvelle analyse
        if current_time - self.last_analysis_time >= self.analysis_interval:
            self.logger.info("Début de l'analyse des actions")
            self.analyze_stocks()
            self.last_analysis_time = current_time
        
        # Pause pour éviter de surcharger le CPU
        time.sleep(1)
    
    def analyze_stocks(self):
        """Analyser les actions selon les critères de Buffet"""
        symbols = Config.TRADING_SYMBOLS
        
        for symbol in symbols:
            # Récupérer les données fondamentales
            data = self.market_data.get_fundamental_data(symbol)
            
            if not data:
                self.logger.warning(f"Pas de données disponibles pour {symbol}")
                continue
            
            # Analyser selon les critères de Buffet
            signal = self.generate_signal(symbol, data)
            
            # Enregistrer la recommandation dans la base de données
            self.save_recommendation(symbol, signal)
            
            # Publier le signal
            self.publish_signal(symbol, signal)
    
    def generate_signal(self, symbol, data):
        """
        Générer un signal d'achat/vente/conservation selon les critères de Buffet
        
        Args:
            symbol (str): Symbole de l'action
            data (dict): Données fondamentales
        
        Returns:
            dict: Signal avec justification
        """
        ratios = data.get('ratios', {})
        info = data.get('info', {})
        
        # Critères de Buffet
        roe = ratios.get('ROE', 0)
        debt_to_equity = ratios.get('debt_to_equity', float('inf'))
        earnings_growth_5y = ratios.get('earnings_growth_5y', 0)
        pe_ratio = ratios.get('P/E', float('inf'))
        pb_ratio = ratios.get('P/B', float('inf'))
        
        # Obtenir la moyenne sectorielle du P/E (simulation)
        sector = info.get('sector', '')
        sector_pe = self.get_sector_pe(sector)
        
        # Évaluer les critères
        criteria_met = {
            'ROE > 10%': roe > 0.10,
            'Ratio dette/équité < 0.5': debt_to_equity < 0.5,
            'Croissance des bénéfices sur 5 ans > 5%': earnings_growth_5y > 5.0,
            f'P/E < moyenne sectorielle ({sector_pe})': pe_ratio < sector_pe,
            'P/B < 1.5': pb_ratio < 1.5
        }
        
        # Compter le nombre de critères satisfaits
        criteria_count = sum(criteria_met.values())
        
        # Déterminer le signal
        signal = 'HOLD'
        confidence = 0.5
        
        if criteria_count >= 4:
            signal = 'BUY'
            confidence = min(0.9, 0.5 + 0.1 * criteria_count)
        elif criteria_count <= 1:
            signal = 'SELL'
            confidence = min(0.9, 0.5 + 0.1 * (5 - criteria_count))
        
        return {
            'signal': signal,
            'confidence': confidence,
            'criteria': criteria_met,
            'rationale': f"L'analyse a satisfait {criteria_count}/5 critères de Buffet"
        }
    
    def get_sector_pe(self, sector):
        """
        Obtenir le P/E moyen du secteur (simulé)
        
        Args:
            sector (str): Secteur d'activité
        
        Returns:
            float: P/E moyen du secteur
        """
        # Valeurs simulées de P/E par secteur
        sector_pe_map = {
            'Technology': 25.0,
            'Healthcare': 20.0,
            'Consumer Cyclical': 22.0,
            'Financial Services': 15.0,
            'Communication Services': 18.0,
            'Industrials': 19.0,
            'Consumer Defensive': 21.0,
            'Energy': 14.0,
            'Utilities': 16.0,
            'Real Estate': 17.0,
            'Basic Materials': 13.0
        }
        
        return sector_pe_map.get(sector, 20.0)  # Valeur par défaut
    
    def save_recommendation(self, symbol, signal_data):
        """
        Enregistrer la recommandation dans la base de données
        
        Args:
            symbol (str): Symbole de l'action
            signal_data (dict): Données du signal
        """
        query = """
        INSERT INTO analyst_recommendations
        (analyst_name, symbol, signal, confidence, rationale)
        VALUES (%s, %s, %s, %s, %s)
        """
        
        params = (
            'Warren Buffet',
            symbol,
            signal_data['signal'],
            signal_data['confidence'],
            signal_data['rationale']
        )
        
        success = self.db.execute(query, params)
        
        if success:
            self.logger.info(f"Recommandation enregistrée pour {symbol}: {signal_data['signal']}")
        else:
            self.logger.error(f"Échec de l'enregistrement de la recommandation pour {symbol}")
    
    def publish_signal(self, symbol, signal_data):
        """
        Publier le signal dans RabbitMQ
        
        Args:
            symbol (str): Symbole de l'action
            signal_data (dict): Données du signal
        """
        message = {
            'analyst': 'Warren Buffet',
            'symbol': symbol,
            'signal': signal_data['signal'],
            'confidence': signal_data['confidence'],
            'criteria': signal_data['criteria'],
            'rationale': signal_data['rationale'],
            'timestamp': time.time()
        }
        
        self.rabbitmq.publish('analyst_signals', 'buffet', json.dumps(message))
        self.logger.info(f"Signal publié pour {symbol}: {signal_data['signal']}")


if __name__ == "__main__":
    agent = BuffetAgent()
    agent.run()