# agents/analysts/buffet_agent.py
from agents.base_agent import BaseAgent
from data.market_data import MarketData
from utils.config import Config
import logging
import json
import time

class BuffetAgent(BaseAgent):
    """
    Agent analyste inspiré de la philosophie d'investissement de Warren Buffet.
    Caractéristiques:
    - ROE > 10%
    - Ratio dette/équité < 0.5
    - Croissance des bénéfices sur 5 ans > 5%
    - P/E < moyenne sectorielle
    - P/B < 1.5
    - Ignore les données de sentiment de X
    """
    
    def __init__(self):
        super().__init__("BuffetAgent")
        self.market_data = MarketData()
        self.symbols = Config.TRADING_SYMBOLS
        self.exchange_name = "analyst_signals"
        self.routing_key = "buffet.signals"
        self.sector_pe_ratios = {}  # Pour stocker les P/E moyens par secteur
    
    def init_agent_structure(self):
        """Initialiser les structures nécessaires pour l'agent"""
        # Déclarer l'exchange pour les signaux d'analyse
        self.rabbitmq.declare_exchange(self.exchange_name)
        
        # Mettre à jour les ratios P/E moyens par secteur
        self.update_sector_pe_ratios()
        
        # Créer une table pour les résultats d'analyse si nécessaire
        self.db.execute('''
            CREATE TABLE IF NOT EXISTS buffet_analysis (
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(10) NOT NULL,
                roe FLOAT,
                debt_to_equity FLOAT,
                earnings_growth_5y FLOAT,
                pe_ratio FLOAT,
                sector_avg_pe FLOAT,
                pb_ratio FLOAT,
                signal VARCHAR(10) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
    
    def update_sector_pe_ratios(self):
        """Calculer et mettre à jour les ratios P/E moyens par secteur"""
        try:
            sectors = {}
            
            # Collecte des ratios P/E pour chaque symbole par secteur
            for symbol in self.symbols:
                try:
                    fundamental_data = self.market_data.get_fundamental_data(symbol)
                    if fundamental_data and 'info' in fundamental_data:
                        info = fundamental_data['info']
                        if 'sector' in info and 'trailingPE' in info:
                            sector = info['sector']
                            pe = info['trailingPE']
                            
                            if sector not in sectors:
                                sectors[sector] = []
                            
                            # Ajouter seulement les P/E valides et raisonnables
                            if pe and pe > 0 and pe < 500:  # Filtrer les valeurs aberrantes
                                sectors[sector].append(pe)
                except Exception as e:
                    self.logger.warning(f"Erreur lors du traitement de {symbol}: {e}")
            
            # Calculer les moyennes par secteur
            for sector, pe_values in sectors.items():
                if pe_values:
                    self.sector_pe_ratios[sector] = sum(pe_values) / len(pe_values)
                    self.logger.info(f"P/E moyen pour le secteur {sector}: {self.sector_pe_ratios[sector]:.2f}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour des ratios P/E sectoriels: {e}")
    
    def analyze_symbol(self, symbol):
        """Analyser un symbole selon les critères de Warren Buffet"""
        try:
            # Récupérer les données fondamentales
            fundamental_data = self.market_data.get_fundamental_data(symbol)
            
            if not fundamental_data:
                self.logger.warning(f"Pas de données fondamentales pour {symbol}")
                return None
            
            info = fundamental_data.get('info', {})
            ratios = fundamental_data.get('ratios', {})
            
            # Extraire les métriques nécessaires
            roe = ratios.get('ROE', 0) * 100 if 'ROE' in ratios else info.get('returnOnEquity', 0) * 100
            debt_to_equity = ratios.get('debt_to_equity', 0) if 'debt_to_equity' in ratios else info.get('debtToEquity', 0) / 100
            earnings_growth_5y = ratios.get('earnings_growth_5y', 0)
            pe_ratio = ratios.get('P/E', 0) if 'P/E' in ratios else info.get('trailingPE', 0)
            pb_ratio = ratios.get('P/B', 0) if 'P/B' in ratios else info.get('priceToBook', 0)
            
            # Obtenir le P/E moyen du secteur
            sector = info.get('sector', '')
            sector_avg_pe = self.sector_pe_ratios.get(sector, 0)
            
            # Appliquer les critères de Buffet
            # 1. ROE > 10%
            roe_check = roe > 10
            
            # 2. Ratio dette/équité < 0.5
            debt_check = debt_to_equity < 0.5
            
            # 3. Croissance des bénéfices sur 5 ans > 5%
            growth_check = earnings_growth_5y > 5
            
            # 4. P/E < moyenne sectorielle
            pe_check = sector_avg_pe > 0 and pe_ratio < sector_avg_pe
            
            # 5. P/B < 1.5
            pb_check = pb_ratio < 1.5
            
            # Déterminer le signal
            checks_passed = sum([roe_check, debt_check, growth_check, pe_check, pb_check])
            
            if checks_passed >= 4:
                signal = "BUY"
            elif checks_passed >= 2:
                signal = "HOLD"
            else:
                signal = "SELL"
            
            # Enregistrer l'analyse
            self.db.execute(
                """
                INSERT INTO buffet_analysis 
                (symbol, roe, debt_to_equity, earnings_growth_5y, pe_ratio, sector_avg_pe, pb_ratio, signal)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (symbol, roe, debt_to_equity, earnings_growth_5y, pe_ratio, sector_avg_pe, pb_ratio, signal)
            )
            
            # Créer le message d'analyse
            analysis = {
                "analyst": "BuffetAgent",
                "symbol": symbol,
                "signal": signal,
                "confidence": checks_passed / 5.0,  # Confiance basée sur le nombre de critères satisfaits
                "metrics": {
                    "roe": roe,
                    "debt_to_equity": debt_to_equity,
                    "earnings_growth_5y": earnings_growth_5y,
                    "pe_ratio": pe_ratio,
                    "sector_avg_pe": sector_avg_pe,
                    "pb_ratio": pb_ratio
                },
                "rationale": f"Critères passés: {checks_passed}/5 (ROE: {'✓' if roe_check else '✗'}, "
                             f"Dette/Équité: {'✓' if debt_check else '✗'}, "
                             f"Croissance 5 ans: {'✓' if growth_check else '✗'}, "
                             f"P/E: {'✓' if pe_check else '✗'}, "
                             f"P/B: {'✓' if pb_check else '✗'})"
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse de {symbol}: {e}")
            return None
    
    def process(self):
        """Processus principal de l'agent"""
        # Si c'est un horizon long terme, analyser moins fréquemment
        if Config.TRADING_HORIZON == 'LONG_TERM':
            self.logger.info("Mise à jour des ratios P/E sectoriels")
            self.update_sector_pe_ratios()
        
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
                            "BuffetAgent",
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
        wait_time = 86400 if Config.TRADING_HORIZON == 'LONG_TERM' else 3600  # 24h ou 1h
        self.logger.info(f"Analyse terminée. Prochaine analyse dans {wait_time / 3600:.1f} heures")
        time.sleep(wait_time)


if __name__ == "__main__":
    agent = BuffetAgent()
    agent.run()