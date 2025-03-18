# agents/manager_agent.py
from agents.base_agent import BaseAgent
import pandas as pd
import numpy as np
from utils.config import Config
import json
import time
import logging

class ManagerAgent(BaseAgent):
    """
    Agent gestionnaire qui collecte les signaux des analystes,
    les pondère et optimise l'allocation du capital
    """
    
    def __init__(self):
        super().__init__("ManagerAgent")
        self.analyst_weights = {}
        self.portfolio = {}
        self.cash = 1000000.0  # Capital initial (1 million)
        self.last_allocation_time = 0
        self.allocation_interval = 3600  # Intervalle de réallocation (1 heure)

    def init_agent_structure(self):
        """Initialise les structures de l'agent gestionnaire"""
        # Déclarer l'exchange pour recevoir les recommandations
        self.rabbitmq.declare_exchange('analyst_recommendations', 'direct')
        
        # Déclarer et lier la queue pour recevoir toutes les recommandations
        self.rabbitmq.declare_queue('manager_recommendations_queue')
        self.rabbitmq.bind_queue(
            'manager_recommendations_queue', 
            'analyst_recommendations', 
            'recommendation'
        )
        
        # Déclarer l'exchange pour envoyer les allocations
        self.rabbitmq.declare_exchange('portfolio_allocations', 'fanout')
        
        # Initialiser les poids des analystes
        self._init_analyst_weights()
        
        # Vérifier si des allocations existent déjà (reprise après arrêt)
        self._load_current_portfolio()

    def _init_analyst_weights(self):
        """Initialise les poids des analystes basés sur les performances historiques"""
        # Récupérer les performances des analystes depuis la base de données
        query = """
            SELECT analyst_name, accuracy_rate 
            FROM analyst_performance 
            ORDER BY timestamp DESC
        """
        performances = self.db.fetch_all(query)
        
        # Si aucune performance n'est encore enregistrée, utiliser des poids égaux
        if not performances:
            self.analyst_weights = {
                'BuffetAgent': 0.2,
                'MungerAgent': 0.2,
                'LynchAgent': 0.2,
                'GrahamAgent': 0.2,
                'DalioAgent': 0.2
            }
            return
        
        # Créer un dictionnaire des dernières performances par analyste
        latest_performances = {}
        for perf in performances:
            analyst = perf['analyst_name']
            if analyst not in latest_performances:
                latest_performances[analyst] = perf['accuracy_rate']
        
        # Calculer les poids normalisés basés sur les performances
        total_accuracy = sum(latest_performances.values())
        
        if total_accuracy > 0:
            self.analyst_weights = {
                analyst: acc / total_accuracy 
                for analyst, acc in latest_performances.items()
            }
        else:
            # Fallback si toutes les performances sont nulles
            self.analyst_weights = {
                analyst: 1.0 / len(latest_performances) 
                for analyst in latest_performances.keys()
            }
        
        self.logger.info(f"Poids des analystes initialisés: {self.analyst_weights}")

    def _load_current_portfolio(self):
        """Charge l'état actuel du portefeuille depuis la base de données"""
        # Récupérer les dernières allocations
        query = """
            SELECT symbol, weight 
            FROM portfolio_allocations 
            WHERE timestamp = (SELECT MAX(timestamp) FROM portfolio_allocations)
        """
        allocations = self.db.fetch_all(query)
        
        if allocations:
            self.portfolio = {alloc['symbol']: alloc['weight'] for alloc in allocations}
            self.logger.info(f"Portefeuille chargé: {self.portfolio}")
            
            # Mise à jour du capital disponible
            query = """
                SELECT cash_balance 
                FROM performance_metrics 
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            cash_result = self.db.fetch_one(query)
            if cash_result:
                self.cash = cash_result['cash_balance']
                self.logger.info(f"Solde en espèces chargé: {self.cash}")

    def process_recommendation(self, ch, method, properties, body):
        """Traite les recommandations des analystes"""
        try:
            recommendation = json.loads(body)
            
            self.logger.info(f"Recommandation reçue: {recommendation}")
            
            # Stocker la recommandation dans la base de données
            query = """
                INSERT INTO analyst_recommendations 
                (analyst_name, symbol, signal, confidence, rationale) 
                VALUES (%s, %s, %s, %s, %s)
            """
            self.db.execute(query, (
                recommendation['analyst_name'],
                recommendation['symbol'],
                recommendation['signal'],
                recommendation['confidence'],
                recommendation['rationale']
            ))
            
            # Accuser réception du message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
            # Vérifier si c'est le moment de recalculer l'allocation
            current_time = time.time()
            if current_time - self.last_allocation_time >= self.allocation_interval:
                self._calculate_portfolio_allocation()
                self.last_allocation_time = current_time
                
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de la recommandation: {e}")
            # En cas d'erreur, rejeter le message pour qu'il reste dans la queue
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _calculate_portfolio_allocation(self):
        """Calcule l'allocation optimale du portefeuille basée sur les recommandations pondérées"""
        self.logger.info("Calcul de l'allocation du portefeuille...")
        
        # Récupérer les recommandations récentes (dernières 24h)
        query = """
            SELECT analyst_name, symbol, signal, confidence
            FROM analyst_recommendations
            WHERE timestamp >= NOW() - INTERVAL '24 hours'
        """
        recommendations = self.db.fetch_all(query)
        
        if not recommendations:
            self.logger.warning("Aucune recommandation récente pour calculer l'allocation")
            return
        
        # Agréger les recommandations par symbole
        symbols_scores = {}
        
        for rec in recommendations:
            symbol = rec['symbol']
            analyst = rec['analyst_name']
            signal = rec['signal']
            confidence = rec['confidence'] or 1.0
            
            # Convertir le signal en score numérique
            if signal == 'BUY':
                score = 1.0
            elif signal == 'SELL':
                score = -1.0
            else:  # HOLD
                score = 0.0
                
            # Appliquer le poids de l'analyste
            analyst_weight = self.analyst_weights.get(analyst, 0.1)
            weighted_score = score * confidence * analyst_weight
            
            if symbol not in symbols_scores:
                symbols_scores[symbol] = {'total_score': 0, 'count': 0}
            
            symbols_scores[symbol]['total_score'] += weighted_score
            symbols_scores[symbol]['count'] += 1
        
        # Calculer le score moyen pour chaque symbole
        for symbol in symbols_scores:
            symbols_scores[symbol]['avg_score'] = (
                symbols_scores[symbol]['total_score'] / symbols_scores[symbol]['count']
            )
        
        # Définir les allocations basées sur les scores
        allocations = {}
        total_positive_score = 0
        
        # Calculer le score positif total (pour les positions longues uniquement)
        for symbol, data in symbols_scores.items():
            avg_score = data['avg_score']
            if avg_score > 0:
                total_positive_score += avg_score
        
        # Si aucun score positif, conserver des liquidités
        if total_positive_score == 0:
            self.logger.info("Aucun signal d'achat positif, conservation des liquidités")
            self.portfolio = {}
            return
        
        # Calculer les poids du portefeuille basés sur les scores positifs
        for symbol, data in symbols_scores.items():
            avg_score = data['avg_score']
            
            # N'allouer du capital qu'aux signaux positifs
            if avg_score > 0:
                weight = avg_score / total_positive_score
                allocations[symbol] = weight
                
        # Mettre à jour le portefeuille
        self.portfolio = allocations
        
        # Enregistrer l'allocation dans la base de données
        for symbol, weight in self.portfolio.items():
            query = """
                INSERT INTO portfolio_allocations (symbol, weight)
                VALUES (%s, %s)
            """
            self.db.execute(query, (symbol, weight))
        
        # Publier l'allocation sur RabbitMQ
        allocation_message = {
            'portfolio': self.portfolio,
            'cash': self.cash,
            'timestamp': time.time()
        }
        
        self.rabbitmq.publish(
            'portfolio_allocations',
            '',  # Fanout exchange n'utilise pas de routing key
            allocation_message
        )
        
        self.logger.info(f"Nouvelle allocation calculée et publiée: {self.portfolio}")

    def process(self):
        """Processus principal de l'agent gestionnaire"""
        try:
            # Consommer les recommandations des analystes
            self.rabbitmq.consume('manager_recommendations_queue', self.process_recommendation)
            
        except Exception as e:
            self.logger.error(f"Erreur dans le processus principal: {e}")
            time.sleep(5)  # Attendre un peu avant de réessayer

if __name__ == "__main__":
    agent = ManagerAgent()
    agent.run()
