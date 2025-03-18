# agents/risk_agent.py
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.config import Config
from utils.messaging import RabbitMQ
from utils.database import PostgresDB
from agents.base_agent import BaseAgent
import logging

class RiskAgent(BaseAgent):
    """
    Agent responsable de la surveillance des risques et de l'intervention
    pour protéger le portefeuille en cas de conditions défavorables
    """
    
    def __init__(self):
        super().__init__("risk_agent")
        self.last_check_time = datetime.now()
        self.check_interval = 60  # Vérifier toutes les 60 secondes
        self.emergency_mode = False
        
        # Liste pour stocker l'historique des valeurs du portefeuille
        self.portfolio_history = []
        
        # Seuils de risque
        self.max_drawdown_threshold = Config.MAX_DRAWDOWN_THRESHOLD  # en pourcentage
    
    def init_agent_structure(self):
        """Initialiser les structures spécifiques de l'agent"""
        # Déclarer les exchanges et queues pour RabbitMQ
        self.rabbitmq.declare_exchange('trading_risk', 'topic')
        self.rabbitmq.declare_queue('risk_alerts')
        self.rabbitmq.bind_queue('risk_alerts', 'trading_risk', 'risk.alert.#')
        
        # Déclarer la queue pour les interventions d'urgence
        self.rabbitmq.declare_queue('emergency_actions')
        self.rabbitmq.bind_queue('emergency_actions', 'trading_risk', 'risk.emergency')
        
        # Récupérer l'historique du portefeuille depuis la base de données
        self._load_portfolio_history()
    
    def process(self):
        """Processus principal de l'agent de risque"""
        current_time = datetime.now()
        
        # Vérifier les risques périodiquement
        if (current_time - self.last_check_time).total_seconds() >= self.check_interval:
            self.last_check_time = current_time
            
            # Récupérer les dernières données de portefeuille
            self._update_portfolio_value()
            
            # Calculer les métriques de risque
            risk_metrics = self._calculate_risk_metrics()
            
            # Enregistrer les métriques
            self._save_risk_metrics(risk_metrics)
            
            # Vérifier si des interventions sont nécessaires
            self._check_risk_thresholds(risk_metrics)
            
            # Envoyer un rapport de risque périodique
            self._send_risk_report(risk_metrics)
        
        # Vérifier s'il y a des alertes de risque à traiter
        # TODO: Implémenter la consommation des alertes
        
        # Pause courte pour éviter de surcharger le CPU
        time.sleep(0.1)
    
    def _load_portfolio_history(self):
        """Charger l'historique des valeurs du portefeuille depuis la base de données"""
        try:
            # Récupérer les 90 derniers jours de données
            query = """
                SELECT date, portfolio_value
                FROM performance_metrics
                ORDER BY date DESC
                LIMIT 90
            """
            results = self.db.fetch_all(query)
            
            if results:
                # Convertir en liste de tuples (date, valeur)
                self.portfolio_history = [(row['date'], row['portfolio_value']) for row in results]
                
                # Trier par date croissante
                self.portfolio_history.sort(key=lambda x: x[0])
                
                self.logger.info(f"Historique du portefeuille chargé: {len(self.portfolio_history)} jours")
            else:
                self.logger.warning("Aucun historique de portefeuille trouvé dans la base de données")
        
        except Exception as e:
            self.logger.error(f"Erreur lors du chargement de l'historique du portefeuille: {e}")
    
    def _update_portfolio_value(self):
        """Mettre à jour la valeur actuelle du portefeuille"""
        try:
            # Récupérer la dernière valeur du portefeuille
            query = """
                SELECT date, portfolio_value
                FROM performance_metrics
                ORDER BY date DESC
                LIMIT 1
            """
            result = self.db.fetch_one(query)
            
            if result:
                today = datetime.now().date()
                
                # Ajouter à l'historique si c'est une nouvelle journée
                if result['date'] < today:
                    self.portfolio_history.append((today, result['portfolio_value']))
                    
                    # Limiter l'historique à 90 jours
                    if len(self.portfolio_history) > 90:
                        self.portfolio_history = self.portfolio_history[-90:]
                
                self.logger.debug(f"Valeur du portefeuille mise à jour: {result['portfolio_value']}")
            else:
                self.logger.warning("Aucune valeur de portefeuille trouvée")
        
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour de la valeur du portefeuille: {e}")
    
    def _calculate_risk_metrics(self):
        """
        Calculer les métriques de risque du portefeuille
        
        Returns:
            dict: Métriques de risque calculées
        """
        risk_metrics = {
            'timestamp': datetime.now(),
            'max_drawdown': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'var_95': 0.0,  # Value at Risk à 95%
            'var_99': 0.0,  # Value at Risk à 99%
            'risk_level': 'NORMAL'  # NORMAL, ELEVATED, HIGH, CRITICAL
        }
        
        # Vérifier si nous avons suffisamment de données
        if len(self.portfolio_history) < 2:
            self.logger.warning("Pas assez de données pour calculer les métriques de risque")
            return risk_metrics
        
        try:
            # Extraire les valeurs du portefeuille
            values = [value for _, value in self.portfolio_history]
            
            # Calculer le drawdown maximal
            peak = values[0]
            max_drawdown = 0.0
            
            for value in values:
                if value > peak:
                    peak = value
                
                drawdown = (peak - value) / peak * 100.0
                max_drawdown = max(max_drawdown, drawdown)
            
            risk_metrics['max_drawdown'] = max_drawdown
            
            # Calculer les rendements quotidiens
            returns = []
            for i in range(1, len(values)):
                daily_return = (values[i] - values[i-1]) / values[i-1]
                returns.append(daily_return)
            
            if len(returns) > 0:
                # Calculer la volatilité (écart-type des rendements)
                volatility = np.std(returns) * np.sqrt(252)  # Annualisé (252 jours de trading)
                risk_metrics['volatility'] = volatility
                
                # Calculer le ratio de Sharpe (en supposant un taux sans risque de 0.02 annualisé)
                avg_return = np.mean(returns) * 252  # Rendement moyen annualisé
                risk_free_rate = 0.02
                sharpe_ratio = (avg_return - risk_free_rate) / volatility if volatility > 0 else 0
                risk_metrics['sharpe_ratio'] = sharpe_ratio
                
                # Calculer la Value at Risk (VaR)
                returns.sort()
                var_95_index = int(len(returns) * 0.05)
                var_99_index = int(len(returns) * 0.01)
                
                risk_metrics['var_95'] = abs(returns[var_95_index]) * 100 if var_95_index < len(returns) else 0
                risk_metrics['var_99'] = abs(returns[var_99_index]) * 100 if var_99_index < len(returns) else 0
            
            # Déterminer le niveau de risque
            if max_drawdown >= self.max_drawdown_threshold * 1.5:
                risk_metrics['risk_level'] = 'CRITICAL'
            elif max_drawdown >= self.max_drawdown_threshold:
                risk_metrics['risk_level'] = 'HIGH'
            elif max_drawdown >= self.max_drawdown_threshold * 0.7:
                risk_metrics['risk_level'] = 'ELEVATED'
            else:
                risk_metrics['risk_level'] = 'NORMAL'
            
            self.logger.info(f"Métriques de risque calculées: Drawdown={max_drawdown:.2f}%, Niveau={risk_metrics['risk_level']}")
            
            return risk_metrics
        
        except Exception as e:
            self.logger.error(f"Erreur lors du calcul des métriques de risque: {e}")
            return risk_metrics
    
    def _save_risk_metrics(self, risk_metrics):
        """
        Enregistrer les métriques de risque dans la base de données
        
        Args:
            risk_metrics (dict): Métriques de risque calculées
        """
        try:
            # Mise à jour de la table performance_metrics
            query = """
                UPDATE performance_metrics
                SET max_drawdown = %s, sharpe_ratio = %s
                WHERE date = %s
            """
            
            today = datetime.now().date()
            params = (
                risk_metrics['max_drawdown'],
                risk_metrics['sharpe_ratio'],
                today
            )
            
            self.db.execute(query, params)
            self.logger.debug("Métriques de risque enregistrées dans la base de données")
        
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement des métriques de risque: {e}")
    
    def _check_risk_thresholds(self, risk_metrics):
        """
        Vérifier si les seuils de risque sont dépassés et intervenir si nécessaire
        
        Args:
            risk_metrics (dict): Métriques de risque calculées
        """
        # Vérifier le drawdown maximal
        if risk_metrics['max_drawdown'] >= self.max_drawdown_threshold:
            if not self.emergency_mode:
                self.logger.warning(f"ALERTE: Drawdown maximal ({risk_metrics['max_drawdown']:.2f}%) dépasse le seuil ({self.max_drawdown_threshold}%)")
                
                # Activer le mode d'urgence
                self.emergency_mode = True
                
                # Envoyer une alerte d'urgence
                emergency_message = {
                    'type': 'EMERGENCY',
                    'reason': f"MAX_DRAWDOWN_EXCEEDED: {risk_metrics['max_drawdown']:.2f}%",
                    'action': 'REDUCE_EXPOSURE',
                    'reduction_target': 50,  # Réduire l'exposition de 50%
                    'timestamp': datetime.now().isoformat()
                }
                
                self.rabbitmq.publish(
                    'trading_risk',
                    'risk.emergency',
                    emergency_message
                )
                
                self.logger.warning("Action d'urgence déclenchée: REDUCE_EXPOSURE par 50%")
        
        # Réactiver le mode normal si le risque est redescendu
        elif self.emergency_mode and risk_metrics['max_drawdown'] < self.max_drawdown_threshold * 0.7:
            self.emergency_mode = False
            
            # Envoyer un message de retour à la normale
            recovery_message = {
                'type': 'RECOVERY',
                'reason': f"RISK_LEVEL_NORMALIZED: {risk_metrics['max_drawdown']:.2f}%",
                'action': 'RESUME_NORMAL',
                'timestamp': datetime.now().isoformat()
            }
            
            self.rabbitmq.publish(
                'trading_risk',
                'risk.recovery',
                recovery_message
            )
            
            self.logger.info("Retour au mode normal de trading")
    
    def _send_risk_report(self, risk_metrics):
        """
        Envoyer un rapport périodique sur les métriques de risque
        
        Args:
            risk_metrics (dict): Métriques de risque calculées
        """
        report = {
            'type': 'RISK_REPORT',
            'timestamp': datetime.now().isoformat(),
            'metrics': {
                'max_drawdown': f"{risk_metrics['max_drawdown']:.2f}%",
                'volatility': f"{risk_metrics['volatility']:.4f}",
                'sharpe_ratio': f"{risk_metrics['sharpe_ratio']:.2f}",
                'var_95': f"{risk_metrics['var_95']:.2f}%",
                'var_99': f"{risk_metrics['var_99']:.2f}%"
            },
            'risk_level': risk_metrics['risk_level'],
            'emergency_mode': self.emergency_mode
        }
        
        self.rabbitmq.publish(
            'trading_risk',
            'risk.report',
            report
        )
        
        self.logger.debug("Rapport de risque envoyé")


if __name__ == "__main__":
    risk_agent = RiskAgent()
    risk_agent.run()