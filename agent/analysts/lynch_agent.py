# agents/analysts/lynch_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from data.sentiment_data import SentimentData
from utils.config import Config
import logging
import json
import time
import numpy as np

class LynchAgent(BaseAgent):
    """
    Agent analyste inspiré de la philosophie d'investissement de Peter Lynch.
    Caractéristiques:
    - Croissance des bénéfices sur 3 ans > 15%
    - Flux de trésorerie positif
    - Achats par les initiés détectés
    - Intègre les données de sentiment de X pour évaluer la perception publique
    """
    
    def __init__(self):
        super().__init__("LynchAgent")
        self.market_data = MarketData()
        self.sentiment_data = SentimentData()
        self.symbols = Config.TRADING_SYMBOLS
        self.exchange_name = "analyst_signals"
        self.routing_key = "lynch.signals"
    
    def init_agent_structure(self):
        """Initialiser les structures nécessaires pour l'agent"""
        # Déclarer l'exchange pour les signaux d'analyse
        self.rabbitmq.declare_exchange(self.exchange_name)
        
        # Créer une table pour les résultats d'analyse si nécessaire
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS lynch_analysis (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                earnings_growth_3y FLOAT,
                cash_flow FLOAT,
                insider_buying BOOLEAN,
                sentiment_score FLOAT,
                signal VARCHAR(10) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def check_insider_buying(self, symbol):
        """
        Vérifier les achats récents par les initiés.
        Dans un système réel, cette fonction interrogerait une API comme SEC EDGAR
        """
        # Simulation pour l'exemple - à remplacer par une vraie source de données
        # Ici, nous simulons des achats par les initiés pour 30% des symboles de manière aléatoire
        if not hasattr(self, 'insider_cache'):
            self.insider_cache = {}
            
        if symbol not in self.insider_cache or np.random.random() < 0.1:  # Mettre à jour aléatoirement
            # Probabilité de 30% d'avoir des achats par les initiés
            self.insider_cache[symbol] = np.random.random() < 0.3
            
        return self.insider_cache[symbol]
    
    def analyze_symbol(self, symbol):
        """Analyser un symbole selon les critères de Peter Lynch"""
        try:
            # Récupérer les données fondamentales
            fundamental_data = self.market_data.get_fundamental_data(symbol)
            
            if not fundamental_data:
                self.logger.warning(f"Pas de données fondamentales pour {symbol}")
                return None
            
            info = fundamental_data.get('info', {})
            ratios = fundamental_data.get('ratios', {})
            financials = fundamental_data.get('financials', {})
            
            # Extraire les métriques nécessaires
            # 1. Croissance des bénéfices sur 3 ans
            earnings_growth_3y = ratios.get('earnings_growth_3y', 0)
            
            # 2. Flux de trésorerie
            cash_flow = 0
            if 'cash_flow' in financials and financials['cash_flow'] is not None:
                try:
                    # Tenter d'extraire le flux de trésorerie d'exploitation le plus récent
                    if 'Operating Cash Flow' in financials['cash_flow'].index:
                        cash_flow = financials['cash_flow'].loc['Operating Cash Flow'].iloc[0]
                except (IndexError, KeyError) as e:
                    self.logger.warning(f"Erreur lors de l'extraction du flux de trésorerie pour {symbol}: {e}")
            
            # 3. Achats par les initiés
            insider_buying = self.check_insider_buying(symbol)
            
            # 4. Sentiment du marché
            company_name = info.get('shortName', symbol)
            sentiment_score = self.sentiment_data.get_sentiment_score(company_name)
            
            # Appliquer les critères de Lynch
            # 1. Croissance des bénéfices sur 3 ans > 15%
            growth_check = earnings_growth_3y > 15
            
            # 2. Flux de trésorerie positif
            cash_flow_check = cash_flow > 0
            
            # 3. Achats par les initiés
            insider_check = insider_buying
            
            # 4. Sentiment positif
            sentiment_check = sentiment_score > 0.2
            
            # Déterminer le signal
            # Lynch accorde une importance particulière à la croissance
            base_score = 0
            
            if growth_check:
                base_score += 2  # La croissance est très importante pour Lynch
            
            if cash_flow_check:
                base_score += 1
            
            if insider_check:
                base_score += 1.5  # Lynch valorisait beaucoup les achats par les initiés
            
            if sentiment_check:
                base_score += 0.5
            
            max_score = 5  # Score maximal possible
            
            if base_score >= 3.5:
                signal = "BUY"
            elif base_score >= 2:
                signal = "HOLD"
            else:
                signal = "SELL"
            
            # Enregistrer l'analyse
            self.db.execute(
                """
                INSERT INTO lynch_analysis 
                (symbol, earnings_growth_3y, cash_flow, insider_buying, sentiment_score, signal)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (symbol, earnings_growth_3y, cash_flow, insider_buying, sentiment_score, signal)
            )
            
            # Créer le message d'analyse
            analysis = {
                "analyst": "LynchAgent",
                "symbol": symbol,
                "signal": signal,
                "confidence": base_score / max_score,
                "metrics": {
                    "earnings_growth_3y": earnings_growth_3y,
                    "cash_flow": cash_flow,
                    "insider_buying": insider_buying,
                    "sentiment_score": sentiment_score
                },
                "rationale": f"Score: {base_score}/{max_score} (Croissance 3 ans: {'✓' if growth_check else '✗'}, "
                             f"Flux de trésorerie: {'✓' if cash_flow_check else '✗'}, "
                             f"Achats par initiés: {'✓' if insider_check else '✗'}, "
                             f"Sentiment: {'✓' if sentiment_check else '✗'})"
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {symbol}: {e}")
            return None
    
    def process(self):
        """Processus principal de l'agent"""
        # Lynch était plus actif - analyser plus fréquemment même en horizon long terme
        
        # Analyser chaque symbole
        for symbol in self.symbols:
            try:
                self.logger.info(f"Analyse de {symbol}...")
                analysis = self.analyze_symbol(symbol)
                
                if analysis:
                    # Publier l'analyse sur RabbitMQ
                    self.rabbitmq.publish(
                        self.exchange_name,
                        self.routing_key,
                        json.dumps(analysis)
                    )
                    
                    # Enregistrer la recommandation dans la base de données
                    self.db.execute(
                        """
                        INSERT INTO analyst_recommendations 
                        (analyst_name, symbol, signal, confidence, rationale)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (
                            "LynchAgent",
                            symbol,
                            analysis['signal'],
                            analysis['confidence'],
                            analysis['rationale']
                        )
                    )
                    
                    self.logger.info(f"Signal publié pour {symbol}: {analysis['signal']}")
            
            except Exception as e:
                self.logger.error(f"Erreur lors du traitement de {symbol}: {e}")
        
        # Attendre avant la prochaine analyse
        # Lynch était plus actif, donc analyse plus fréquente
        wait_time = 43200 if Config.TRADING_HORIZON == 'LONG_TERM' else 1800  # 12h ou 30min
        self.logger.info(f"Analyse terminée. Prochaine analyse dans {wait_time / 3600:.1f} heures")
        time.sleep(wait_time)


if __name__ == "__main__":
    agent = LynchAgent()
    agent.run()