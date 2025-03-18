# agents/analysts/munger_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from data.sentiment_data import SentimentData
from utils.config import Config
import time
import json

class MungerAgent(BaseAgent):
    """
    Agent inspiré de la philosophie d'investissement de Charlie Munger.
    
    Métriques clés:
    - ROE > 15%
    - Ratio dette/équité < 0.3
    - Croissance des bénéfices sur 10 ans > 7%
    - P/E < 80% de la moyenne sectorielle
    - P/B < 1.0
    """
    
    def __init__(self):
        super().__init__("munger_agent")
        self.market_data = MarketData()
        self.sentiment_data = SentimentData()
        # Intervalle en secondes entre les analyses
        self.analysis_interval = 14400 if Config.TRADING_HORIZON == 'LONG_TERM' else 300
        self.last_analysis_time = 0
    
    def init_agent_structure(self):
        """Initialiser les queues et échanges RabbitMQ"""
        # Exchange pour les signaux d'analyse
        self.rabbitmq.declare_exchange('analyst_signals', 'direct')
        
        # Queue pour les signaux
        self.rabbitmq.declare_queue('munger_signals')
        
        # Lier la queue à l'exchange
        self.rabbitmq.bind_queue('munger_signals', 'analyst_signals', 'munger')
        
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
        """Analyser les actions selon les critères de Munger"""
        symbols = Config.TRADING_SYMBOLS
        
        for symbol in symbols:
            # Récupérer les données fondamentales
            market_data = self.market_data.get_fundamental_data(symbol)
            
            if not market_data:
                self.logger.warning(f"Pas de données disponibles pour {symbol}")
                continue
            
            # Récupérer le sentiment X/Twitter pour des insights qualitatifs
            company_name = market_data.get('info', {}).get('shortName', '')
            sentiment_data = self.sentiment_data.get_company_sentiment(symbol, company_name)
            
            # Analyser selon les critères de Munger
            signal = self.generate_signal(symbol, market_data, sentiment_data)
            
            # Enregistrer la recommandation dans la base de données
            self.save_recommendation(symbol, signal)
            
            # Publier le signal
            self.publish_signal(symbol, signal)
    
    def generate_signal(self, symbol, market_data, sentiment_data):
        """
        Générer un signal d'achat/vente/conservation selon les critères de Munger
        
        Args:
            symbol (str): Symbole de l'action
            market_data (dict): Données fondamentales
            sentiment_data (dict): Données de sentiment
        
        Returns:
            dict: Signal avec justification
        """
        ratios = market_data.get('ratios', {})
        info = market_data.get('info', {})
        
        # Critères de Munger
        roe = ratios.get('ROE', 0)
        debt_to_equity = ratios.get('debt_to_equity', float('inf'))
        earnings_growth_10y = ratios.get('earnings_growth_10y', 0)  
        # Note: dans un système réel, nous aurions besoin de données sur 10 ans
        # À défaut, on utilise la croissance sur 5 ans si disponible
        if earnings_growth_10y == 0:
            earnings_growth_10y = ratios.get('earnings_growth_5y', 0)
        
        pe_ratio = ratios.get('P/E', float('inf'))
        pb_ratio = ratios.get('P/B', float('inf'))
        
        # Obtenir la moyenne sectorielle du P/E (simulation)
        sector = info.get('sector', '')
        sector_pe = self.get_sector_pe(sector)
        sector_pe_threshold = 0.8 * sector_pe  # 80% de la moyenne sectorielle
        
        # Évaluer les critères
        criteria_met = {
            'ROE > 15%': roe > 0.15,
            'Ratio dette/équité < 0.3': debt_to_equity < 0.3,
            'Croissance des bénéfices sur période longue > 7%': earnings_growth_10y > 7.0,
            f'P/E < 80% de la moyenne sectorielle ({sector_pe_threshold:.2f})': pe_ratio < sector_pe_threshold,
            'P/B < 1.0': pb_ratio < 1.0
        }
        
        # Compter le nombre de critères satisfaits
        criteria_count = sum(criteria_met.values())
        
        # Prendre en compte le sentiment
        sentiment_score = sentiment_data.get('sentiment_avg', 0)
        sentiment_positive = sentiment_data.get('positive_ratio', 0)
        
        # Munger utilise le sentiment comme facteur supplémentaire
        sentiment_bonus = 0
        
        if sentiment_score > 0.2 and sentiment_positive > 0.6:
            sentiment_bonus = 0.5  # Bonus partiel si sentiment très positif
        elif sentiment_score > 0.1 and sentiment_positive > 0.5:
            sentiment_bonus = 0.25  # Petit bonus si sentiment modérément positif
        
        # Déterminer le signal
        signal = 'HOLD'
        confidence = 0.5
        
        adjusted_criteria_count = criteria_count + sentiment_bonus
        
        if adjusted_criteria_count >= 4:
            signal = 'BUY'
            confidence = min(0.95, 0.5 + 0.1 * adjusted_criteria_count)
        elif adjusted_criteria_count <= 1.5:
            signal = 'SELL'
            confidence = min(0.9, 0.5 + 0.1 * (5 - adjusted_criteria_count))
        
        # Préparer la justification
        rationale = f"L'analyse a satisfait {criteria_count}/5 critères de Munger."
        if sentiment_bonus > 0:
            rationale += f" Bonus de sentiment positif: +{sentiment_bonus} (Score: {sentiment_score:.2f}, Positif: {sentiment_positive:.2f})"
        
        return {
            'signal': signal,
            'confidence': confidence,
            'criteria': criteria_met,
            'sentiment': {
                'score': sentiment_score,
                'positive_ratio': sentiment_positive
            },
            'rationale': rationale
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
            'Charlie Munger',
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
            'analyst': 'Charlie Munger',
            'symbol': symbol,
            'signal': signal_data['signal'],
            'confidence': signal_data['confidence'],
            'criteria': signal_data['criteria'],
            'sentiment': signal_data['sentiment'],
            'rationale': signal_data['rationale'],
            'timestamp': time.time()
        }
        
        self.rabbitmq.publish('analyst_signals', 'munger', json.dumps(message))
        self.logger.info(f"Signal publié pour {symbol}: {signal_data['signal']}")


if __name__ == "__main__":
    agent = MungerAgent()
    agent.run()