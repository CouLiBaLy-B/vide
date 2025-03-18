# agents/trader_agent.py
from agents.base_agent import BaseAgent
import json
import time
import pandas as pd
import numpy as np
from utils.config import Config
from data.market_data import MarketData
import logging

class TraderAgent(BaseAgent):
    """
    Agent trader qui exécute les transactions basées sur les allocations
    décidées par l'agent gestionnaire
    """
    
    def __init__(self):
        super().__init__("TraderAgent")
        self.current_portfolio = {}  # Holdings actuels {symbol: quantité}
        self.cash = 1000000.0  # Solde en espèces
        self.target_allocation = {}  # Allocation cible {symbol: poids}
        self.trading_mode = Config.TRADING_HORIZON  # SHORT_TERM ou LONG_TERM
        self.last_prices = {}  # Derniers prix connus {symbol: prix}
        self.orders_queue = []  # File d'attente des ordres

    def init_agent_structure(self):
        """Initialise les structures de l'agent trader"""
        # Exchange pour recevoir les allocations du gestionnaire
        self.rabbitmq.declare_exchange('portfolio_allocations', 'fanout')
        
        # Queue pour recevoir les allocations
        self.rabbitmq.declare_queue('trader_allocations_queue')
        self.rabbitmq.bind_queue(
            'trader_allocations_queue',
            'portfolio_allocations',
            ''  # Fanout exchange n'utilise pas de routing key
        )
        
        # Exchange pour publier les transactions
        self.rabbitmq.declare_exchange('transactions', 'fanout')
        
        # Charger l'état actuel du portefeuille
        self._load_current_portfolio()
        
        # Récupérer les prix actuels du marché
        self._update_market_prices()

    def _load_current_portfolio(self):
        """Charge l'état actuel du portefeuille depuis la base de données"""
        # Récupérer le solde en espèces
        query = """
            SELECT cash_balance 
            FROM performance_metrics 
            ORDER BY timestamp DESC 
            LIMIT 1
        """
        cash_result = self.db.fetch_one(query)
        if cash_result:
            self.cash = cash_result['cash_balance']
        
        # Récupérer les positions actuelles (reconstruites à partir des transactions)
        query = """
            SELECT symbol, 
                   SUM(CASE WHEN transaction_type = 'BUY' THEN quantity 
                            WHEN transaction_type = 'SELL' THEN -quantity
                            ELSE 0 END) as net_quantity
            FROM transactions
            GROUP BY symbol
            HAVING SUM(CASE WHEN transaction_type = 'BUY' THEN quantity 
                            WHEN transaction_type = 'SELL' THEN -quantity
                            ELSE 0 END) > 0
        """
        positions = self.db.fetch_all(query)
        
        self.current_portfolio = {
            pos['symbol']: pos['net_quantity'] 
            for pos in positions if pos['net_quantity'] > 0
        }
        
        self.logger.info(f"Portefeuille chargé: {self.current_portfolio}")
        self.logger.info(f"Solde en espèces: {self.cash}")

    def _update_market_prices(self):
        """Met à jour les prix actuels du marché"""
        symbols = list(set(
            list(self.current_portfolio.keys()) + 
            list(self.target_allocation.keys())
        ))
        
        if not symbols:
            return
        
        market_data = MarketData.get_historical_data(symbols, period='1d', interval='1d')
        
        for symbol, data in market_data.items():
            if not data.empty:
                self.last_prices[symbol] = data['Close'].iloc[-1]
        
        self.logger.debug(f"Prix du marché mis à jour: {self.last_prices}")

    def process_allocation(self, ch, method, properties, body):
        """Traite les messages d'allocation du gestionnaire"""
        try:
            allocation = json.loads(body)
            
            self.logger.info(f"Nouvelle allocation reçue: {allocation}")
            
            # Mettre à jour l'allocation cible
            self.target_allocation = allocation.get('portfolio', {})
            
            # Mettre à jour le solde en espèces si fourni
            if 'cash' in allocation:
                self.cash = allocation['cash']
            
            # Mettre à jour les prix du marché
            self._update_market_prices()
            
            # Calculer et exécuter les transactions nécessaires
            self._generate_orders()
            
            # Accuser réception du message
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de l'allocation: {e}")
            # Rejeter le message en cas d'erreur
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _generate_orders(self):
        """Génère les ordres nécessaires pour atteindre l'allocation cible"""
        self.logger.info("Génération des ordres de trading...")
        
        # Calculer la valeur totale du portefeuille (cash + positions)
        portfolio_value = self.cash
        for symbol, quantity in self.current_portfolio.items():
            if symbol in self.last_prices:
                portfolio_value += quantity * self.last_prices[symbol]
        
        # Calculer le nombre d'actions cible pour chaque symbole
        target_positions = {}
        for symbol, weight in self.target_allocation.items():
            if symbol in self.last_prices and self.last_prices[symbol] > 0:
                target_value = portfolio_value * weight
                target_quantity = int(target_value / self.last_prices[symbol])
                target_positions[symbol] = target_quantity
        
        # Générer les ordres (achats et ventes)
        self.orders_queue = []
        
        # 1. Vendre les positions qui ne sont plus dans l'allocation cible
        for symbol, quantity in self.current_portfolio.items():
            if symbol not in target_positions and symbol in self.last_prices:
                self.orders_queue.append({
                    'symbol': symbol,
                    'type': 'SELL',
                    'quantity': quantity,
                    'price': self.last_prices[symbol]
                })
        
        # 2. Ajuster les positions existantes
        for symbol, target_quantity in target_positions.items():
            current_quantity = self.current_portfolio.get(symbol, 0)
            
            if target_quantity > current_quantity:
                # Acheter plus
                self.orders_queue.append({
                    'symbol': symbol,
                    'type': 'BUY',
                    'quantity': target_quantity - current_quantity,
                    'price': self.last_prices[symbol]
                })
            elif target_quantity < current_quantity:
                # Vendre une partie
                self.orders_queue.append({
                    'symbol': symbol,
                    'type': 'SELL',
                    'quantity': current_quantity - target_quantity,
                    'price': self.last_prices[symbol]
                })
        
        self.logger.info(f"Ordres générés: {self.orders_queue}")

    def _execute_orders(self):
        """Exécute les ordres en attente"""
        if not self.orders_queue:
            return
        
        self.logger.info("Exécution des ordres...")
        
        # Traiter tous les ordres de vente d'abord pour libérer du capital
        sell_orders = [order for order in self.orders_queue if order['type'] == 'SELL']
        for order in sell_orders:
            self._execute_transaction(order)
            self.orders_queue.remove(order)
        
        # Puis traiter les ordres d'achat
        buy_orders = list(self.orders_queue)  # Copy the list as we'll modify it
        for order in buy_orders:
            if order['type'] == 'BUY':
                self._execute_transaction(order)
                self.orders_queue.remove(order)
        
        # Mettre à jour les métriques de performance
        self._update_performance_metrics()

    def _execute_transaction(self, order):
        """Exécute une transaction individuelle"""
        symbol = order['symbol']
        order_type = order['type']
        quantity = order['quantity']
        price = order['price']
        total_value = quantity * price
        
        # Validation de la transaction
        if order_type == 'BUY' and total_value > self.cash:
            # Ajuster la quantité si pas assez de cash
            adjusted_quantity = int(self.cash / price)
            if adjusted_quantity <= 0:
                self.logger.warning(f"Transaction annulée: pas assez de cash pour acheter {symbol}")
                return
            
            quantity = adjusted_quantity
            total_value = quantity * price
            self.logger.warning(f"Quantité d'achat ajustée pour {symbol}: {quantity} (manque de cash)")
        
        # Exécuter la transaction
        if order_type == 'BUY':
            self.cash -= total_value
            self.current_portfolio[symbol] = self.current_portfolio.get(symbol, 0) + quantity
        else:  # SELL
            self.cash += total_value
            self.current_portfolio[symbol] = self.current_portfolio.get(symbol, 0) - quantity
            
            # Supprimer les positions vides
            if self.current_portfolio[symbol] <= 0:
                del self.current_portfolio[symbol]
        
        # Enregistrer la transaction dans la base de données
        query = """
            INSERT INTO transactions 
            (symbol, transaction_type, price, quantity, total_value) 
            VALUES (%s, %s, %s, %s, %s)
        """
        self.db.execute(query, (symbol, order_type, price, quantity, total_value))
        
        # Publier la transaction sur RabbitMQ
        transaction_message = {
            'symbol': symbol,
            'type': order_type,
            'quantity': quantity,
            'price': price,
            'total_value': total_value,
            'timestamp': time.time()
        }
        
        self.rabbitmq.publish(
            'transactions',
            '',  # Fanout exchange
            transaction_message
        )
        
        self.logger.info(f"Transaction exécutée: {order_type} {quantity} {symbol} à {price}$")

    def _update_performance_metrics(self):
        """Met à jour les métriques de performance du portefeuille"""
        # Calculer la valeur totale du portefeuille
        portfolio_value = self.cash
        for symbol, quantity in self.current_portfolio.items():
            if symbol in self.last_prices:
                portfolio_value += quantity * self.last_prices[symbol]
        
        # Récupérer la valeur précédente pour calculer le rendement quotidien
        query = """
            SELECT portfolio_value 
            FROM performance_metrics 
            ORDER BY date DESC 
            LIMIT 1
        """
        prev_value = self.db.fetch_one(query)
        
        daily_return = None
        if prev_value:
            daily_return = (portfolio_value / prev_value['portfolio_value']) - 1
        
        # Calculer le Sharpe ratio (simplifié)
        sharpe_ratio = None
        # Le calcul complet nécessiterait des données historiques plus étendues
        
        # Calculer le drawdown maximum (simplifié)
        max_drawdown = None
        # Le calcul complet nécessiterait des données historiques plus étendues
        
        # Enregistrer les métriques de performance
        query = """
            INSERT INTO performance_metrics 
            (date, portfolio_value, cash_balance, daily_return, sharpe_ratio, max_drawdown) 
            VALUES (CURRENT_DATE, %s, %s, %s, %s, %s)
        """
        self.db.execute(query, (
            portfolio_value,
            self.cash,
            daily_return,
            sharpe_ratio,
            max_drawdown
        ))
        
        self.logger.info(f"Métriques de performance mises à jour: valeur={portfolio_value}, cash={self.cash}")

    def process(self):
        """Processus principal de l'agent trader"""
        try:
            # Exécuter les ordres en attente
            if self.orders_queue:
                self._execute_orders()
            
            # Consommer les messages d'allocation
            # Mode non-bloquant avec un délai
            self.rabbitmq.channel.basic_consume(
                queue='trader_allocations_queue',
                on_message_callback=self.process_allocation,
                auto_ack=False
            )
            
            # Traiter les messages pendant un court délai
            self.rabbitmq.connection.process_data_events(time_limit=1)
            
            # Mettre à jour périodiquement les prix du marché
            if time.time() % 300 < 1:  # Environ toutes les 5 minutes
                self._update_market_prices()
            
            # Pause pour éviter de surcharger le CPU
            time.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Erreur dans le processus principal: {e}")
            time.sleep(5)  # Attendre avant de réessayer

if __name__ == "__main__":
    agent = TraderAgent()
    agent.run()
