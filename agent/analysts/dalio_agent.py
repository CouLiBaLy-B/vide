# agents/analysts/dalio_agent.py
import sys
import os
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta

# Ajout du dossier parent au chemin pour importer les modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agents.base_agent import BaseAgent
from data.market_data import MarketData
from data.sentiment_data import SentimentData
from utils.config import Config
import logging

class DalioAnalyst(BaseAgent):
    """
    Agent analyste inspiré de la philosophie d'investissement de Ray Dalio
    
    Ray Dalio est connu pour son approche macro-économique et son modèle "All Weather".
    Cet agent analyse les tendances macro-économiques, les cycles de marché,
    et combine ces analyses avec des données fondamentales pour prendre des décisions.
    """
    
    def __init__(self):
        super().__init__("dalio_analyst")
        self.sentiment_data = SentimentData()
        self.exchange_name = "analysts_exchange"
        self.routing_key = "dalio_signals"
        self.queue_name = "dalio_queue"
        self.last_analysis_time = datetime.now() - timedelta(hours=24)  # Pour forcer une analyse au démarrage
        self.analysis_interval = timedelta(hours=4)  # Analyse toutes les 4 heures
        self.macro_data = {}
        self.logger.info("Agent Dalio initialisé")
    
    def init_agent_structure(self):
        """Initialisation des structures RabbitMQ pour l'agent Dalio"""
        try:
            # Déclarer l'exchange pour les analystes
            self.rabbitmq.declare_exchange(self.exchange_name)
            
            # Déclarer la queue spécifique pour l'agent Dalio
            self.rabbitmq.declare_queue(self.queue_name)
            
            # Lier la queue à l'exchange
            self.rabbitmq.bind_queue(self.queue_name, self.exchange_name, self.routing_key)
            
            self.logger.info("Structure RabbitMQ initialisée pour l'agent Dalio")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation des structures RabbitMQ: {e}")
            raise
    
    def process(self):
        """Traitement principal de l'agent Dalio"""
        current_time = datetime.now()
        
        # Vérifier si c'est le moment d'effectuer une nouvelle analyse
        if (current_time - self.last_analysis_time) >= self.analysis_interval:
            self.logger.info("Début d'une nouvelle analyse Dalio")
            
            try:
                # 1. Récupérer les données macro-économiques
                self.update_macro_data()
                
                # 2. Analyser chaque symbole
                self.analyze_symbols()
                
                # 3. Mettre à jour la dernière heure d'analyse
                self.last_analysis_time = current_time
                
            except Exception as e:
                self.logger.error(f"Erreur pendant l'analyse Dalio: {e}")
        
        # Pause pour éviter une utilisation excessive du CPU
        time.sleep(1)
    
    def update_macro_data(self):
        """
        Récupère et met à jour les données macro-économiques
        
        Cette fonction simule l'obtention de données macro telles que l'inflation,
        les taux d'intérêt, la croissance du PIB, etc.
        """
        try:
            self.logger.info("Mise à jour des données macro-économiques")
            
            # Dans une version réelle, on récupérerait ces données via des APIs financières
            # Ici, nous simulons les données
            self.macro_data = {
                'inflation_rate': 2.8,            # Taux d'inflation actuel (%)
                'interest_rate': 3.5,             # Taux d'intérêt de référence (%)
                'gdp_growth': 2.1,                # Croissance du PIB (%)
                'unemployment_rate': 4.2,         # Taux de chômage (%)
                'consumer_sentiment': 72.8,       # Indice de confiance des consommateurs
                'manufacturing_pmi': 53.2,        # Indice des directeurs d'achats manufacturier
                'market_volatility': 18.5,        # Indice de volatilité (VIX)
                'yield_curve': -0.15,             # Pente de la courbe des taux (10 ans - 2 ans)
                'dollar_index': 96.8,             # Indice du dollar
                'corporate_credit_spread': 2.35,  # Écart de crédit corporatif
                'economic_cycle_phase': 'late_expansion'  # Phase du cycle économique
            }
            
            self.logger.info("Données macro-économiques mises à jour")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour des données macro: {e}")
            raise
    
    def analyze_symbols(self):
        """Analyser tous les symboles selon l'approche de Ray Dalio"""
        symbols = Config.TRADING_SYMBOLS
        
        for symbol in symbols:
            try:
                # Récupérer les données fondamentales
                fundamental_data = MarketData.get_fundamental_data(symbol)
                
                # Récupérer les données historiques (1 an)
                historical_data = MarketData.get_historical_data(symbol, period='1y')
                
                if not fundamental_data or not historical_data or symbol not in historical_data:
                    self.logger.warning(f"Données insuffisantes pour {symbol}, analyse ignorée")
                    continue
                
                # Récupérer les données de sentiment
                sentiment_data = self.sentiment_data.get_symbol_sentiment(symbol)
                
                # Effectuer l'analyse Dalio
                signal, confidence, rationale = self.dalio_analysis(
                    symbol, 
                    historical_data[symbol], 
                    fundamental_data, 
                    sentiment_data
                )
                
                # Publier le signal dans RabbitMQ
                self.publish_signal(symbol, signal, confidence, rationale)
                
                # Enregistrer la recommandation dans la base de données
                self.save_recommendation(symbol, signal, confidence, rationale)
                
                self.logger.info(f"Analyse Dalio complétée pour {symbol}: {signal} (confiance: {confidence:.2f})")
                
            except Exception as e:
                self.logger.error(f"Erreur lors de l'analyse de {symbol}: {e}")
    
    def dalio_analysis(self, symbol, historical_data, fundamental_data, sentiment_data):
        """
        Effectue une analyse selon les principes de Ray Dalio
        
        Args:
            symbol (str): Symbole boursier
            historical_data (DataFrame): Données historiques du prix
            fundamental_data (dict): Données fondamentales
            sentiment_data (dict): Données de sentiment
        
        Returns:
            tuple: (signal, confidence, rationale)
        """
        self.logger.info(f"Analyse Dalio en cours pour {symbol}")
        
        signals = []
        confidences = []
        reasons = []
        
        # 1. Analyse macro-économique (poids: 40%)
        macro_signal, macro_confidence, macro_reason = self.analyze_macro_environment(symbol, historical_data)
        signals.append(macro_signal)
        confidences.append(0.4 * macro_confidence)
        reasons.append(macro_reason)
        
        # 2. Analyse fondamentale (poids: 30%)
        fundamental_signal, fundamental_confidence, fundamental_reason = self.analyze_fundamentals(symbol, fundamental_data)
        signals.append(fundamental_signal)
        confidences.append(0.3 * fundamental_confidence)
        reasons.append(fundamental_reason)
        
        # 3. Analyse de risque et de diversification (poids: 20%)
        risk_signal, risk_confidence, risk_reason = self.analyze_risk(symbol, historical_data)
        signals.append(risk_signal)
        confidences.append(0.2 * risk_confidence)
        reasons.append(risk_reason)
        
        # 4. Analyse du sentiment (poids: 10%)
        sentiment_signal, sentiment_confidence, sentiment_reason = self.analyze_sentiment(symbol, sentiment_data)
        signals.append(sentiment_signal)
        confidences.append(0.1 * sentiment_confidence)
        reasons.append(sentiment_reason)
        
        # Calculer le signal final et la confiance
        final_confidence = sum(confidences)
        
        # Déterminer le signal final
        buy_weight = sum(conf for sig, conf in zip(signals, confidences) if sig == 'BUY')
        sell_weight = sum(conf for sig, conf in zip(signals, confidences) if sig == 'SELL')
        hold_weight = sum(conf for sig, conf in zip(signals, confidences) if sig == 'HOLD')
        
        if buy_weight > sell_weight and buy_weight > hold_weight:
            final_signal = 'BUY'
        elif sell_weight > buy_weight and sell_weight > hold_weight:
            final_signal = 'SELL'
        else:
            final_signal = 'HOLD'
        
        # Construire l'explication
        rationale = f"Analyse Dalio pour {symbol}:\n"
        rationale += f"1. Macro-économie ({macro_signal}, {macro_confidence:.2f}): {macro_reason}\n"
        rationale += f"2. Fondamentaux ({fundamental_signal}, {fundamental_confidence:.2f}): {fundamental_reason}\n"
        rationale += f"3. Risque ({risk_signal}, {risk_confidence:.2f}): {risk_reason}\n"
        rationale += f"4. Sentiment ({sentiment_signal}, {sentiment_confidence:.2f}): {sentiment_reason}\n"
        
        return final_signal, final_confidence, rationale
    
    def analyze_macro_environment(self, symbol, historical_data):
        """
        Analyse l'environnement macro-économique selon les principes de Dalio
        """
        # Vérifier si nous avons des données macro
        if not self.macro_data:
            return 'HOLD', 0.5, "Données macro-économiques insuffisantes"
        
        reasons = []
        score = 0.0
        
        # Analyser l'environnement de taux d'intérêt
        if self.macro_data['interest_rate'] > 4.0:
            score -= 0.2
            reasons.append("Taux d'intérêt élevés défavorables pour les actions")
        elif self.macro_data['interest_rate'] < 2.0:
            score += 0.1
            reasons.append("Taux d'intérêt bas favorables pour les actions")
        
        # Analyser la croissance économique
        if self.macro_data['gdp_growth'] > 3.0:
            score += 0.2
            reasons.append("Forte croissance du PIB favorable")
        elif self.macro_data['gdp_growth'] < 1.0:
            score -= 0.15
            reasons.append("Faible croissance du PIB défavorable")
        
        # Analyser l'inflation
        if self.macro_data['inflation_rate'] > 4.0:
            score -= 0.15
            reasons.append("Inflation élevée défavorable")
        elif self.macro_data['inflation_rate'] < 1.0:
            score -= 0.1
            reasons.append("Risque déflationniste présent")
        
        # Analyser la courbe des taux
        if self.macro_data['yield_curve'] < -0.1:
            score -= 0.3
            reasons.append("Courbe des taux inversée - signal récessionniste")
        
        # Analyser la volatilité du marché
        if self.macro_data['market_volatility'] > 25:
            score -= 0.1
            reasons.append("Volatilité élevée du marché")
        
        # Analyser le cycle économique
        cycle_phase = self.macro_data['economic_cycle_phase']
        if cycle_phase == 'early_expansion':
            score += 0.3
            reasons.append("Phase de début d'expansion favorable pour les actions")
        elif cycle_phase == 'late_expansion':
            score += 0.1
            reasons.append("Phase de fin d'expansion - soyez sélectif")
        elif cycle_phase == 'early_contraction':
            score -= 0.3
            reasons.append("Début de contraction - prudence requise")
        elif cycle_phase == 'late_contraction':
            score += 0.2
            reasons.append("Fin de contraction - opportunités d'achat potentielles")
        
        # Normaliser le score entre -1 et 1
        normalized_score = max(min(score, 1.0), -1.0)
        
        # Déterminer le signal et la confiance
        if normalized_score > 0.3:
            signal = 'BUY'
            confidence = 0.5 + normalized_score / 2  # entre 0.65 et 1.0
        elif normalized_score < -0.3:
            signal = 'SELL'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.65 et 1.0
        else:
            signal = 'HOLD'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.5 et 0.65
        
        reason = "; ".join(reasons)
        return signal, confidence, reason
    
    def analyze_fundamentals(self, symbol, fundamental_data):
        """
        Analyse les données fondamentales selon l'approche de Dalio
        """
        if not fundamental_data or 'ratios' not in fundamental_data:
            return 'HOLD', 0.5, "Données fondamentales insuffisantes"
        
        ratios = fundamental_data.get('ratios', {})
        info = fundamental_data.get('info', {})
        
        score = 0.0
        reasons = []
        
        # Analyser le ROE (Return on Equity)
        roe = ratios.get('ROE')
        if roe is not None:
            if roe > 0.15:  # 15%
                score += 0.15
                reasons.append(f"ROE élevé ({roe:.1%})")
            elif roe < 0.05:  # 5%
                score -= 0.1
                reasons.append(f"ROE faible ({roe:.1%})")
        
        # Analyser le ratio d'endettement
        debt_ratio = ratios.get('debt_to_equity')
        if debt_ratio is not None:
            if debt_ratio > 1.0:
                score -= 0.15
                reasons.append(f"Dette élevée ({debt_ratio:.2f})")
            elif debt_ratio < 0.3:
                score += 0.1
                reasons.append(f"Dette faible ({debt_ratio:.2f})")
        
        # Analyser la croissance des bénéfices
        growth_5y = ratios.get('earnings_growth_5y')
        if growth_5y is not None:
            if growth_5y > 10:  # 10%
                score += 0.15
                reasons.append(f"Forte croissance des bénéfices ({growth_5y:.1f}%)")
            elif growth_5y < 0:
                score -= 0.2
                reasons.append(f"Décroissance des bénéfices ({growth_5y:.1f}%)")
        
        # Analyser les multiples de valorisation
        pe_ratio = ratios.get('P/E')
        if pe_ratio is not None:
            if pe_ratio > 30:
                score -= 0.15
                reasons.append(f"P/E élevé ({pe_ratio:.1f})")
            elif pe_ratio < 15:
                score += 0.1
                reasons.append(f"P/E attractif ({pe_ratio:.1f})")
        
        pb_ratio = ratios.get('P/B')
        if pb_ratio is not None:
            if pb_ratio > 3:
                score -= 0.1
                reasons.append(f"P/B élevé ({pb_ratio:.1f})")
            elif pb_ratio < 1.5:
                score += 0.1
                reasons.append(f"P/B attractif ({pb_ratio:.1f})")
        
        # Vérifier les flux de trésorerie
        if info.get('freeCashflow', 0) > 0:
            score += 0.1
            reasons.append("Flux de trésorerie libre positif")
        else:
            score -= 0.15
            reasons.append("Flux de trésorerie libre négatif")
        
        # Normaliser le score entre -1 et 1
        normalized_score = max(min(score, 1.0), -1.0)
        
        # Déterminer le signal et la confiance
        if normalized_score > 0.3:
            signal = 'BUY'
            confidence = 0.5 + normalized_score / 2  # entre 0.65 et 1.0
        elif normalized_score < -0.3:
            signal = 'SELL'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.65 et 1.0
        else:
            signal = 'HOLD'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.5 et 0.65
        
        reason = "; ".join(reasons)
        return signal, confidence, reason
    
    def analyze_risk(self, symbol, historical_data):
        """
        Analyse le risque du titre selon les principes de diversification de Dalio
        """
        if historical_data.empty:
            return 'HOLD', 0.5, "Données historiques insuffisantes pour l'analyse de risque"
        
        score = 0.0
        reasons = []
        
        # Calculer la volatilité (écart-type des rendements quotidiens)
        if 'Close' in historical_data.columns:
            daily_returns = historical_data['Close'].pct_change().dropna()
            
            # Volatilité annualisée
            volatility = daily_returns.std() * np.sqrt(252) * 100  # En pourcentage
            
            if volatility > 30:
                score -= 0.2
                reasons.append(f"Volatilité très élevée ({volatility:.1f}%)")
            elif volatility > 20:
                score -= 0.1
                reasons.append(f"Volatilité élevée ({volatility:.1f}%)")
            elif volatility < 10:
                score += 0.1
                reasons.append(f"Volatilité faible ({volatility:.1f}%)")
            
            # Drawdown maximal sur la période
            cumulative_returns = (1 + daily_returns).cumprod()
            rolling_max = cumulative_returns.cummax()
            drawdowns = (cumulative_returns / rolling_max - 1) * 100  # En pourcentage
            max_drawdown = abs(drawdowns.min())
            
            if max_drawdown > 30:
                score -= 0.2
                reasons.append(f"Drawdown maximal important ({max_drawdown:.1f}%)")
            elif max_drawdown < 10:
                score += 0.1
                reasons.append(f"Drawdown maximal limité ({max_drawdown:.1f}%)")
            
            # Ratio de Sharpe (avec taux sans risque à 2%)
            risk_free_rate = 0.02
            avg_annual_return = daily_returns.mean() * 252
            sharpe_ratio = (avg_annual_return - risk_free_rate) / (daily_returns.std() * np.sqrt(252))
            
            if sharpe_ratio > 1.0:
                score += 0.2
                reasons.append(f"Bon ratio de Sharpe ({sharpe_ratio:.2f})")
            elif sharpe_ratio < 0:
                score -= 0.2
                reasons.append(f"Mauvais ratio de Sharpe ({sharpe_ratio:.2f})")
        
        # Corrélation avec le cycle économique (simulation)
        # Dans un système réel, on calculerait la corrélation avec des indices ou d'autres actifs
        cycle_phase = self.macro_data.get('economic_cycle_phase', '')
        
        if cycle_phase == 'early_expansion' and 'technology' in symbol.lower():
            score += 0.15
            reasons.append("Technologie bien positionnée en début de cycle")
        elif cycle_phase == 'late_expansion' and any(x in symbol.lower() for x in ['staple', 'consumer', 'util']):
            score += 0.1
            reasons.append("Défensif bien positionné en fin de cycle")
        
        # Normaliser le score entre -1 et 1
        normalized_score = max(min(score, 1.0), -1.0)
        
        # Déterminer le signal et la confiance
        if normalized_score > 0.3:
            signal = 'BUY'
            confidence = 0.5 + normalized_score / 2  # entre 0.65 et 1.0
        elif normalized_score < -0.3:
            signal = 'SELL'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.65 et 1.0
        else:
            signal = 'HOLD'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.5 et 0.65
        
        reason = "; ".join(reasons)
        return signal, confidence, reason
    
    def analyze_sentiment(self, symbol, sentiment_data):
        """
        Analyse les données de sentiment selon l'approche de Dalio
        
        Dalio prend en compte le sentiment du marché, mais l'utilise principalement
        comme contrarian indicator lorsqu'il est extrême.
        """
        if not sentiment_data:
            return 'HOLD', 0.5, "Données de sentiment insuffisantes"
        
        score = 0.0
        reasons = []
        
        # Extraire les métriques de sentiment
        overall_sentiment = sentiment_data.get('overall_sentiment', 0)
        sentiment_volume = sentiment_data.get('volume', 0)
        sentiment_change = sentiment_data.get('change', 0)
        
        # Approche contrarian pour sentiment extrême
        if overall_sentiment > 0.8 and sentiment_volume > 1000:
            score -= 0.2
            reasons.append("Optimisme excessif, signal contrarian de vente")
        elif overall_sentiment < -0.8 and sentiment_volume > 1000:
            score += 0.2
            reasons.append("Pessimisme excessif, signal contrarian d'achat")
        
        # Tendance du sentiment
        if sentiment_change > 0.2:
            score += 0.1
            reasons.append("Amélioration significative du sentiment")
        elif sentiment_change < -0.2:
            score -= 0.1
            reasons.append("Détérioration significative du sentiment")
        
        # Normaliser le score entre -1 et 1
        normalized_score = max(min(score, 1.0), -1.0)
        
        # Déterminer le signal et la confiance
        if normalized_score > 0.3:
            signal = 'BUY'
            confidence = 0.5 + normalized_score / 2  # entre 0.65 et 1.0
        elif normalized_score < -0.3:
            signal = 'SELL'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.65 et 1.0
        else:
            signal = 'HOLD'
            confidence = 0.5 + abs(normalized_score) / 2  # entre 0.5 et 0.65
        
        reason = "; ".join(reasons)
        return signal, confidence, reason
    
    def publish_signal(self, symbol, signal, confidence, rationale):
        """Publier un signal d'investissement dans RabbitMQ"""
        message = {
            'analyst': 'dalio',
            'symbol': symbol,
            'signal': signal,
            'confidence': confidence,
            'rationale': rationale,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            self.rabbitmq.publish(self.exchange_name, self.routing_key, message)
            self.logger.debug(f"Signal publié pour {symbol}: {signal}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la publication du signal pour {symbol}: {e}")
    
    def save_recommendation(self, symbol, signal, confidence, rationale):
        """Enregistrer la recommandation dans la base de données"""
        try:
            query = """
                INSERT INTO analyst_recommendations 
                (analyst_name, symbol, signal, confidence, rationale) 
                VALUES (%s, %s, %s, %s, %s)
            """
            params = ('dalio', symbol, signal, confidence, rationale)
            
            self.db.execute(query, params)
            self.logger.debug(f"Recommandation enregistrée pour {symbol}")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement de la recommandation pour {symbol}: {e}")


if __name__ == "__main__":
    # Créer et exécuter l'agent
    dalio_agent = DalioAnalyst()
    dalio_agent.run()