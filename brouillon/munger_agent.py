# agents/analysts/buffet_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from utils.config import Config
import time
import logging

class BuffetAgent(BaseAgent):
    """Agent analyste inspiré par la philosophie d'investissement de Warren Buffet"""
    
    def __init__(self):
        super().__init__("buffet_agent")
        self.symbols = Config.TRADING_SYMBOLS
        self.exchange_name = "analyst_signals"
        self.queue_name = "buffet_signals"
        self.routing_key = "buffet"
        
    def init_agent_structure(self):
        """Initialiser les structures de messagerie"""
        # Déclarer l'exchange pour les signaux d'analystes
        self.rabbitmq.declare_exchange(self.exchange_name)
        
        # Déclarer la queue pour cet analyste
        self.rabbitmq.declare_queue(self.queue_name)
        
        # Lier la queue à l'exchange
        self.rabbitmq.bind_queue(
            self.queue_name, 
            self.exchange_name,
            self.routing_key
        )
    
    def process(self):
        """Analyser les symboles et générer des signaux"""
        self.logger.info("Début de l'analyse des symboles")
        
        for symbol in self.symbols:
            signal = self.analyze_symbol(symbol)
            
            if signal:
                # Publier le signal
                self.rabbitmq.publish(
                    self.exchange_name,
                    self.routing_key,
                    signal
                )
                
                # Enregistrer le signal dans la BDD
                self.db.execute(
                    """
                    INSERT INTO analyst_recommendations 
                    (analyst_name, symbol, signal, confidence, rationale)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    ("Warren Buffet", signal["symbol"], signal["signal"], 
                     signal["confidence"], signal["rationale"])
                )
        
        # Attendre avant la prochaine analyse
        wait_time = 3600  # 1 heure entre chaque analyse
        self.logger.info(f"Analyse terminée, attente de {wait_time} secondes")
        time.sleep(wait_time)
    
    def analyze_symbol(self, symbol):
        """
        Analyser un symbole selon les critères de Warren Buffet
        
        Critères:
        - ROE > 10%
        - Ratio dette/équité < 0.5
        - Croissance des bénéfices sur 5 ans > 5%
        - P/E < moyenne sectorielle
        - P/B < 1.5
        """
        try:
            # Récupérer les données fondamentales
            fundamental_data = MarketData.get_fundamental_data(symbol)
            
            if not fundamental_data or "ratios" not in fundamental_data:
                self.logger.warning(f"Données insuffisantes pour {symbol}")
                return None
            
            ratios = fundamental_data["ratios"]
            info = fundamental_data["info"]
            
            # Vérifier les critères
            criteria_met = []
            criteria_failed = []
            
            # ROE > 10%
            if "ROE" in ratios and ratios["ROE"] > 0.10:
                criteria_met.append(f"ROE de {ratios['ROE']:.1%} > 10%")
            else:
                criteria_failed.append(f"ROE insuffisant: {ratios.get('ROE', 'N/A')}")
            
            # Ratio dette/équité < 0.5
            if "debt_to_equity" in ratios and ratios["debt_to_equity"] < 0.5:
                criteria_met.append(f"Ratio dette/équité de {ratios['debt_to_equity']:.2f} < 0.5")
            else:
                criteria_failed.append(f"Dette trop élevée: {ratios.get('debt_to_equity', 'N/A')}")
            
            # Croissance des bénéfices sur 5 ans > 5%
            if "earnings_growth_5y" in ratios and ratios["earnings_growth_5y"] > 5:
                criteria_met.append(f"Croissance des bénéfices sur 5 ans de {ratios['earnings_growth_5y']:.1f}% > 5%")
            else:
                criteria_failed.append(f"Croissance insuffisante: {ratios.get('earnings_growth_5y', 'N/A')}%")
            
            # P/E < moyenne sectorielle (on utilise 15 comme proxy si la moyenne sectorielle n'est pas disponible)
            sector_pe = 15  # Valeur par défaut
            if "P/E" in ratios and ratios["P/E"] < sector_pe:
                criteria_met.append(f"P/E de {ratios['P/E']:.2f} < {sector_pe}")
            else:
                criteria_failed.append(f"P/E trop élevé: {ratios.get('P/E', 'N/A')}")
            
            # P/B < 1.5
            if "P/B" in ratios and ratios["P/B"] < 1.5:
                criteria_met.append(f"P/B de {ratios['P/B']:.2f} < 1.5")
            else:
                criteria_failed.append(f"P/B trop élevé: {ratios.get('P/B', 'N/A')}")
            
            # Déterminer le signal en fonction du nombre de critères remplis
            total_criteria = len(criteria_met) + len(criteria_failed)
            ratio_met = len(criteria_met) / total_criteria if total_criteria > 0 else 0
            
            signal = None
            if ratio_met >= 0.8:  # ≥ 80% des critères remplis
                signal = "BUY"
                confidence = ratio_met
            elif ratio_met >= 0.6:  # ≥ 60% des critères remplis
                signal = "HOLD"
                confidence = ratio_met
            else:
                signal = "SELL"
                confidence = 1 - ratio_met
            
            # Préparer le message
            rationale = f"Critères satisfaits: {', '.join(criteria_met)}. " \
                       f"Critères non satisfaits: {', '.join(criteria_failed)}."
            
            self.logger.info(f"Signal pour {symbol}: {signal} (confiance: {confidence:.2f})")
            
            return {
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "rationale": rationale,
                "metrics": ratios,
                "analyst": "Warren Buffet"
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {symbol}: {e}")
            return None

if __name__ == "__main__":
    agent = BuffetAgent()
    agent.run()


# agents/analysts/munger_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from data.sentiment_data import SentimentData
from utils.config import Config
import time
import logging

class MungerAgent(BaseAgent):
    """Agent analyste inspiré par la philosophie d'investissement de Charlie Munger"""
    
    def __init__(self):
        super().__init__("munger_agent")
        self.symbols = Config.TRADING_SYMBOLS
        self.exchange_name = "analyst_signals"
        self.queue_name = "munger_signals"
        self.routing_key = "munger"
        self.sentiment_analyzer = SentimentData()
        
    def init_agent_structure(self):
        """Initialiser les structures de messagerie"""
        # Déclarer l'exchange pour les signaux d'analystes
        self.rabbitmq.declare_exchange(self.exchange_name)
        
        # Déclarer la queue pour cet analyste
        self.rabbitmq.declare_queue(self.queue_name)
        
        # Lier la queue à l'exchange
        self.rabbitmq.bind_queue(
            self.queue_name, 
            self.exchange_name,
            self.routing_key
        )
    
    def process(self):
        """Analyser les symboles et générer des signaux"""
        self.logger.info("Début de l'analyse des symboles")
        
        for symbol in self.symbols:
            signal = self.analyze_symbol(symbol)
            
            if signal:
                # Publier le signal
                self.rabbitmq.publish(
                    self.exchange_name,
                    self.routing_key,
                    signal
                )
                
                # Enregistrer le signal dans la BDD
                self.db.execute(
                    """
                    INSERT INTO analyst_recommendations 
                    (analyst_name, symbol, signal, confidence, rationale)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    ("Charlie Munger", signal["symbol"], signal["signal"], 
                     signal["confidence"], signal["rationale"])
                )
        
        # Attendre avant la prochaine analyse
        wait_time = 3600  # 1 heure entre chaque analyse
        self.logger.info(f"Analyse terminée, attente de {wait_time} secondes")
        time.sleep(wait_time)
    
    def analyze_symbol(self, symbol):
        """
        Analyser un symbole selon les critères de Charlie Munger
        
        Critères:
        - ROE > 15%
        - Ratio dette/équité < 0.3
        - Croissance des bénéfices sur 10 ans > 7%
        - P/E < 80% de la moyenne sectorielle
        - P/B < 1.0
        """
        try:
            # Récupérer les données fondamentales
            fundamental_data = MarketData.get_fundamental_data(symbol)
            
            if not fundamental_data or "ratios" not in fundamental_data:
                self.logger.warning(f"Données insuffisantes pour {symbol}")
                return None
            
            ratios = fundamental_data["ratios"]
            info = fundamental_data["info"]
            
            # Récupérer le sentiment
            sentiment = self.sentiment_analyzer.get_sentiment(symbol)
            
            # Vérifier les critères
            criteria_met = []
            criteria_failed = []
            
            # ROE > 15%
            if "ROE" in ratios and ratios["ROE"] > 0.15:
                criteria_met.append(f"ROE de {ratios['ROE']:.1%} > 15%")
            else:
                criteria_failed.append(f"ROE insuffisant: {ratios.get('ROE', 'N/A')}")
            
            # Ratio dette/équité < 0.3
            if "debt_to_equity" in ratios and ratios["debt_to_equity"] < 0.3:
                criteria_met.append(f"Ratio dette/équité de {ratios['debt_to_equity']:.2f} < 0.3")
            else:
                criteria_failed.append(f"Dette trop élevée: {ratios.get('debt_to_equity', 'N/A')}")
            
            # Croissance des bénéfices sur 10 ans > 7% (on utilise 5 ans si 10 ans n'est pas disponible)
            if "earnings_growth_5y" in ratios and ratios["earnings_growth_5y"] > 7:
                criteria_met.append(f"Croissance des bénéfices sur 5 ans de {ratios['earnings_growth_5y']:.1f}% > 7%")
            else:
                criteria_failed.append(f"Croissance insuffisante: {ratios.get('earnings_growth_5y', 'N/A')}%")
            
            # P/E < 80% de la moyenne sectorielle (on utilise 12 comme proxy)
            sector_pe = 15 * 0.8  # 80% de la moyenne du marché (proxy)
            if "P/E" in ratios and ratios["P/E"] < sector_pe:
                criteria_met.append(f"P/E de {ratios['P/E']:.2f} < {sector_pe:.2f}")
            else:
                criteria_failed.append(f"P/E trop élevé: {ratios.get('P/E', 'N/A')}")
            
            # P/B < 1.0
            if "P/B" in ratios and ratios["P/B"] < 1.0:
                criteria_met.append(f"P/B de {ratios['P/B']:.2f} < 1.0")
            else:
                criteria_failed.append(f"P/B trop élevé: {ratios.get('P/B', 'N/A')}")
            
            # Analyser le sentiment
            sentiment_factor = 0
            if sentiment and sentiment["tweet_count"] > 10:
                if sentiment["compound"] > 0.2:
                    criteria_met.append(f"Sentiment positif: {sentiment['compound']:.2f}")
                    sentiment_factor = 0.1
                elif sentiment["compound"] < -0.2:
                    criteria_failed.append(f"Sentiment négatif: {sentiment['compound']:.2f}")
                    sentiment_factor = -0.1
            
            # Déterminer le signal en fonction du nombre de critères remplis
            total_criteria = len(criteria_met) + len(criteria_failed)
            ratio_met = len(criteria_met) / total_criteria if total_criteria > 0 else 0
            
            # Ajuster avec le sentiment
            ratio_met += sentiment_factor
            ratio_met = max(0, min(1, ratio_met))  # Garantir que le ratio reste entre 0 et 1
            
            signal = None
            if ratio_met >= 0.85:  # ≥ 85% des critères remplis
                signal = "BUY"
                confidence = ratio_met
            elif ratio_met >= 0.65:  # ≥ 65% des critères remplis
                signal = "HOLD"
                confidence = ratio_met
            else:
                signal = "SELL"
                confidence = 1 - ratio_met
            
            # Préparer le message
            rationale = f"Critères satisfaits: {', '.join(criteria_met)}. " \
                       f"Critères non satisfaits: {', '.join(criteria_failed)}."
            
            self.logger.info(f"Signal pour {symbol}: {signal} (confiance: {confidence:.2f})")
            
            return {
                "symbol": symbol,
                "signal": signal,
                "confidence": confidence,
                "rationale": rationale,
                "metrics": ratios,
                "sentiment": sentiment["compound"] if sentiment else 0,
                "analyst": "Charlie Munger"
            }
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {symbol}: {e}")
            return None

if __name__ == "__main__":
    agent = MungerAgent()
    agent.run()