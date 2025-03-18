# models/backtesting.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import logging
from utils.config import Config

logger = logging.getLogger(__name__)

class Backtesting:
    """
    Classe pour effectuer des backtests des stratégies de trading
    """
    
    def __init__(self, initial_capital=100000.0):
        """
        Initialiser le backtest avec un capital initial
        
        Args:
            initial_capital (float): Capital initial en euros/dollars
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {symbol: {'quantity': int, 'avg_price': float}}
        self.portfolio_history = []
        self.transactions = []
    
    def reset(self):
        """Réinitialiser le backtest"""
        self.cash = self.initial_capital
        self.positions = {}
        self.portfolio_history = []
        self.transactions = []
    
    def execute_trade(self, symbol, action, quantity, price, timestamp):
        """
        Exécuter une transaction dans le backtest
        
        Args:
            symbol (str): Symbole de l'actif
            action (str): 'BUY' ou 'SELL'
            quantity (int): Nombre d'actions
            price (float): Prix par action
            timestamp: Horodatage de la transaction
        
        Returns:
            bool: True si la transaction est réussie, False sinon
        """
        if action == 'BUY':
            cost = quantity * price
            
            # Vérifier si nous avons assez de cash
            if cost > self.cash:
                logger.warning(f"Transaction échouée - Pas assez de cash pour acheter {quantity} {symbol} à {price}")
                return False
            
            # Mettre à jour le cash
            self.cash -= cost
            
            # Mettre à jour les positions
            if symbol in self.positions:
                # Mettre à jour le prix moyen d'achat
                current_quantity = self.positions[symbol]['quantity']
                current_avg_price = self.positions[symbol]['avg_price']
                
                new_quantity = current_quantity + quantity
                new_avg_price = ((current_quantity * current_avg_price) + (quantity * price)) / new_quantity
                
                self.positions[symbol] = {
                    'quantity': new_quantity,
                    'avg_price': new_avg_price
                }
            else:
                # Nouvelle position
                self.positions[symbol] = {
                    'quantity': quantity,
                    'avg_price': price
                }
                
        elif action == 'SELL':
            # Vérifier si nous avons assez d'actions
            if symbol not in self.positions or self.positions[symbol]['quantity'] < quantity:
                logger.warning(f"Transaction échouée - Pas assez d'actions {symbol} pour vendre")
                return False
            
            # Mettre à jour le cash
            self.cash += quantity * price
            
            # Mettre à jour les positions
            remaining = self.positions[symbol]['quantity'] - quantity
            
            if remaining == 0:
                # Position fermée
                del self.positions[symbol]
            else:
                # Position réduite
                self.positions[symbol]['quantity'] = remaining
                # Remarque: Le prix moyen d'achat reste le même
        
        # Enregistrer la transaction
        self.transactions.append({
            'timestamp': timestamp,
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'price': price,
            'cost': quantity * price,
            'cash_after': self.cash
        })
        
        logger.info(f"Transaction exécutée - {action} {quantity} {symbol} à {price}")
        return True
    
    def update_portfolio_value(self, price_data, timestamp):
        """
        Mettre à jour la valeur du portefeuille à un moment donné
        
        Args:
            price_data (dict): Dictionnaire {symbol: price} avec les prix actuels
            timestamp: Horodatage pour l'historique
        """
        equity = 0.0
        
        # Calculer la valeur des positions
        for symbol, position in self.positions.items():
            if symbol in price_data:
                equity += position['quantity'] * price_data[symbol]
        
        # Calculer la valeur totale du portefeuille
        portfolio_value = self.cash + equity
        
        # Enregistrer dans l'historique
        self.portfolio_history.append({
            'timestamp': timestamp,
            'cash': self.cash,
            'equity': equity,
            'portfolio_value': portfolio_value
        })
    
    def run_backtest(self, historical_data, signals, commission=0.001):
        """
        Exécuter un backtest complet basé sur des données historiques et des signaux
        
        Args:
            historical_data (dict): Dictionnaire {symbol: DataFrame} avec OHLCV data
            signals (list): Liste de signaux de trading
                [{'timestamp': datetime, 'symbol': str, 'action': str, 'quantity': int}, ...]
            commission (float): Frais de commission en pourcentage
            
        Returns:
            DataFrame: Historique du portefeuille
        """
        # Réinitialiser le backtest
        self.reset()
        
        # Trier les signaux par horodatage
        signals = sorted(signals, key=lambda x: x['timestamp'])
        
        # Créer une liste unifiée de tous les horodatages
        all_timestamps = set()
        for symbol, data in historical_data.items():
            all_timestamps.update(data.index)
        
        for signal in signals:
            all_timestamps.add(signal['timestamp'])
        
        all_timestamps = sorted(list(all_timestamps))
        
        # Exécuter le backtest
        for timestamp in all_timestamps:
            # Vérifier s'il y a des signaux à exécuter à ce timestamp
            day_signals = [s for s in signals if s['timestamp'] == timestamp]
            
            # Récupérer les prix de clôture pour ce jour
            prices = {}
            for symbol, data in historical_data.items():
                if timestamp in data.index:
                    prices[symbol] = data.loc[timestamp, 'Close']
            
            # Exécuter les transactions basées sur les signaux
            for signal in day_signals:
                symbol = signal['symbol']
                action = signal['action']
                quantity = signal['quantity']
                
                if symbol in prices:
                    price = prices[symbol]
                    
                    # Ajuster le prix avec les commissions
                    if action == 'BUY':
                        adjusted_price = price * (1 + commission)
                    else:  # SELL
                        adjusted_price = price * (1 - commission)
                    
                    self.execute_trade(symbol, action, quantity, adjusted_price, timestamp)
            
            # Mettre à jour la valeur du portefeuille
            self.update_portfolio_value(prices, timestamp)
        
        # Convertir l'historique du portefeuille en DataFrame
        portfolio_df = pd.DataFrame(self.portfolio_history)
        
        return self.calculate_performance_metrics(portfolio_df)
    
    def calculate_performance_metrics(self, portfolio_df):
        """
        Calculer les métriques de performance à partir de l'historique du portefeuille
        
        Args:
            portfolio_df (DataFrame): Historique du portefeuille
            
        Returns:
            dict: Métriques de performance
        """
        if portfolio_df.empty:
            return {
                'total_return': 0,
                'annualized_return': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'volatility': 0,
                'win_rate': 0
            }
        
        # Calculer les rendements quotidiens
        portfolio_df['daily_return'] = portfolio_df['portfolio_value'].pct_change()
        
        # Calculer les rendements cumulés
        initial_value = portfolio_df['portfolio_value'].iloc[0]
        final_value = portfolio_df['portfolio_value'].iloc[-1]
        
        total_return = (final_value - initial_value) / initial_value
        
        # Calculer le rendement annualisé
        days = (portfolio_df['timestamp'].iloc[-1] - portfolio_df['timestamp'].iloc[0]).days
        years = days / 365
        annualized_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1
        
        # Calculer le ratio de Sharpe (en supposant un taux sans risque de 0%)
        daily_returns = portfolio_df['daily_return'].dropna()
        volatility = daily_returns.std() * np.sqrt(252)  # Annualiser la volatilité
        sharpe_ratio = (annualized_return / volatility) if volatility > 0 else 0
        
        # Calculer le drawdown maximum
        cumulative = (1 + portfolio_df['daily_return'].fillna(0)).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative / running_max) - 1
        max_drawdown = drawdown.min()
        
        # Calculer le taux de réussite des transactions
        profitable_trades = sum(1 for t in self.transactions if t['action'] == 'SELL' and 
                              t['price'] > self.get_avg_buy_price(t['symbol'], t['timestamp']))
        total_sell_trades = sum(1 for t in self.transactions if t['action'] == 'SELL')
        win_rate = profitable_trades / total_sell_trades if total_sell_trades > 0 else 0
        
        return {
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'volatility': volatility,
            'win_rate': win_rate,
            'portfolio_history': portfolio_df,
            'transactions': pd.DataFrame(self.transactions)
        }
    
    def get_avg_buy_price(self, symbol, before_timestamp):
        """
        Obtenir le prix moyen d'achat d'un symbole avant un horodatage donné
        """
        buy_transactions = [t for t in self.transactions 
                           if t['symbol'] == symbol and 
                           t['action'] == 'BUY' and 
                           t['timestamp'] < before_timestamp]
        
        if not buy_transactions:
            return 0
        
        total_quantity = sum(t['quantity'] for t in buy_transactions)
        total_cost = sum(t['cost'] for t in buy_transactions)
        
        return total_cost / total_quantity if total_quantity > 0 else 0
    
    def plot_performance(self, metrics):
        """
        Créer des graphiques pour visualiser les performances
        
        Args:
            metrics (dict): Métriques de performance avec historique du portefeuille
        """
        if 'portfolio_history' not in metrics:
            logger.error("Pas d'historique de portefeuille à afficher")
            return
        
        portfolio_df = metrics['portfolio_history']
        
        # Configurer les sous-graphiques
        fig, axs = plt.subplots(3, 1, figsize=(12, 18), gridspec_kw={'height_ratios': [3, 2, 2]})
        
        # 1. Valeur du portefeuille
        axs[0].plot(portfolio_df['timestamp'], portfolio_df['portfolio_value'], label='Valeur totale')
        axs[0].plot(portfolio_df['timestamp'], portfolio_df['cash'], label='Cash', linestyle='--')
        axs[0].plot(portfolio_df['timestamp'], portfolio_df['equity'], label='Actions', linestyle='-.')
        axs[0].set_title('Évolution de la valeur du portefeuille')
        axs[0].set_ylabel('Valeur ($)')
        axs[0].legend()
        axs[0].grid(True)
        
        # 2. Rendements cumulés
        cumulative_returns = (1 + portfolio_df['daily_return'].fillna(0)).cumprod() - 1
        axs[1].plot(portfolio_df['timestamp'], cumulative_returns * 100)
        axs[1].set_title('Rendements cumulés')
        axs[1].set_ylabel('Rendement (%)')
        axs[1].grid(True)
        
        # 3. Drawdown
        cumulative = (1 + portfolio_df['daily_return'].fillna(0)).cumprod()
        running_max = cumulative.cummax()
        drawdown = ((cumulative / running_max) - 1) * 100  # En pourcentage
        axs[2].fill_between(portfolio_df['timestamp'], drawdown, 0, color='red', alpha=0.3)
        axs[2].set_title('Drawdown')
        axs[2].set_ylabel('Drawdown (%)')
        axs[2].grid(True)
        
        # Informations sur les performances
        textstr = '\n'.join((
            f'Rendement total: {metrics["total_return"]*100:.2f}%',
            f'Rendement annualisé: {metrics["annualized_return"]*100:.2f}%',
            f'Ratio de Sharpe: {metrics["sharpe_ratio"]:.2f}',
            f'Drawdown maximum: {metrics["max_drawdown"]*100:.2f}%',
            f'Volatilité: {metrics["volatility"]*100:.2f}%',
            f'Taux de réussite: {metrics["win_rate"]*100:.2f}%'
        ))
        
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        axs[0].text(0.05, 0.95, textstr, transform=axs[0].transAxes, fontsize=10,
                    verticalalignment='top', bbox=props)
        
        plt.tight_layout()
        plt.savefig('backtest_results.png')
        plt.close()
        
        logger.info("Graphiques de performance générés et sauvegardés dans 'backtest_results.png'")

