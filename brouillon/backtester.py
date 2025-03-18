# backtest.py
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from utils.config import Config
from data.market_data import MarketData
from agents.analysts.buffet_agent import BuffetAnalyst
from agents.analysts.munger_agent import MungerAnalyst
from agents.analysts.lynch_agent import LynchAnalyst
from agents.analysts.graham_agent import GrahamAnalyst
from agents.analysts.dalio_agent import DalioAnalyst
from agents.manager_agent import ManagerAgent
from agents.trader_agent import TraderAgent
from agents.risk_agent import RiskAgent
from utils.logging_utils import setup_logger

class Backtester:
    """Classe pour effectuer des simulations de backtesting du système multi-agent"""
    
    def __init__(self, start_date, end_date, initial_capital=100000.0):
        """
        Initialiser le backtester
        
        Args:
            start_date (str): Date de début au format 'YYYY-MM-DD'
            end_date (str): Date de fin au format 'YYYY-MM-DD'
            initial_capital (float): Capital initial en dollars
        """
        self.logger = setup_logger("Backtester")
        self.logger.info(f"Initialisation du backtesting du {start_date} au {end_date}")
        
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.cash = initial_capital
        self.portfolio = {}  # {symbol: {'shares': quantity, 'cost_basis': prix_moyen}}
        self.portfolio_values = []  # [(date, valeur_totale, cash)]
        self.transactions = []  # [(date, symbol, type, prix, quantité, valeur)]
        
        # Initialiser les agents
        self.analysts = {
            'buffet': BuffetAnalyst(),
            'munger': MungerAnalyst(),
            'lynch': LynchAnalyst(),
            'graham': GrahamAnalyst(),
            'dalio': DalioAnalyst()
        }
        
        self.manager = ManagerAgent()
        self.trader = TraderAgent()
        self.risk_agent = RiskAgent()
        
        # Obtenir les données pour la période de backtesting
        self.symbols = Config.TRADING_SYMBOLS
        self.logger.info(f"Récupération des données historiques pour {len(self.symbols)} symboles")
        self.market_data = MarketData.get_historical_data(
            self.symbols,
            period='max',  # Nous filtrerons par date après
            interval='1d'
        )
        
        # Filtrer les données par plage de dates
        for symbol in self.market_data:
            self.market_data[symbol] = self.market_data[symbol].loc[start_date:end_date]
        
        self.dates = pd.date_range(start=start_date, end=end_date, freq='B')
        self.logger.info(f"Backtesting prêt avec {len(self.dates)} jours de trading")
    
    def run(self):
        """Exécuter la simulation de backtesting"""
        self.logger.info("Démarrage de la simulation de backtesting")
        
        # Pour chaque jour de trading
        for current_date in self.dates:
            date_str = current_date.strftime('%Y-%m-%d')
            self.logger.info(f"Simulation pour le jour: {date_str}")
            
            # Vérifier si nous avons des données pour cette date
            data_available = all(date_str in df.index for df in self.market_data.values())
            if not data_available:
                self.logger.warning(f"Données non disponibles pour {date_str}, passage au jour suivant")
                continue
            
            # 1. Collecter les analyses des analystes
            analyst_signals = {}
            for name, analyst in self.analysts.items():
                signals = analyst.analyze_backtest(self.market_data, date_str)
                analyst_signals[name] = signals
                self.logger.info(f"Analyste {name}: {len(signals)} signaux générés")
            
            # 2. Le gestionnaire décide de l'allocation
            allocation = self.manager.allocate_backtest(analyst_signals, self.portfolio, self.cash)
            self.logger.info(f"Gestionnaire: allocation pour {len(allocation)} symboles")
            
            # 3. Le trader exécute les transactions
            transactions = self.trader.execute_backtest(
                allocation, 
                self.portfolio, 
                self.cash,
                self.market_data,
                date_str
            )
            
            # Mettre à jour le portefeuille et le cash
            for transaction in transactions:
                symbol, trade_type, price, quantity, value = transaction
                
                if trade_type == 'BUY':
                    # Ajouter au portefeuille
                    if symbol not in self.portfolio:
                        self.portfolio[symbol] = {'shares': 0, 'cost_basis': 0}
                    
                    # Mettre à jour le coût moyen
                    current_value = self.portfolio[symbol]['shares'] * self.portfolio[symbol]['cost_basis']
                    new_value = current_value + value
                    new_shares = self.portfolio[symbol]['shares'] + quantity
                    
                    if new_shares > 0:
                        self.portfolio[symbol]['cost_basis'] = new_value / new_shares
                    self.portfolio[symbol]['shares'] = new_shares
                    
                    # Déduire la valeur du cash
                    self.cash -= value
                
                elif trade_type == 'SELL':
                    # Réduire les actions dans le portefeuille
                    if symbol in self.portfolio:
                        self.portfolio[symbol]['shares'] -= quantity
                        
                        # Supprimer le symbole si plus d'actions
                        if self.portfolio[symbol]['shares'] <= 0:
                            del self.portfolio[symbol]
                    
                    # Ajouter la valeur au cash
                    self.cash += value
                
                # Enregistrer la transaction
                self.transactions.append((date_str, symbol, trade_type, price, quantity, value))
                self.logger.info(f"Transaction: {trade_type} {quantity} {symbol} à {price}$ = {value}$")
            
            # 4. Évaluer le portefeuille pour cette date
            portfolio_value = self.evaluate_portfolio(date_str)
            
            # 5. L'agent de risque vérifie les limites
            risk_action = self.risk_agent.check_risk_backtest(
                self.portfolio_values, 
                self.portfolio, 
                self.cash
            )
            
            if risk_action:
                self.logger.warning(f"Agent de risque: action requise: {risk_action}")
                # Appliquer l'action de réduction des risques si nécessaire
                if risk_action == 'REDUCE_EXPOSURE':
                    reduced_allocation = self.reduce_exposure(self.portfolio, 0.5)  # Réduire de 50%
                    
                    risk_transactions = self.trader.execute_backtest(
                        reduced_allocation,
                        self.portfolio,
                        self.cash,
                        self.market_data,
                        date_str
                    )
                    
                    # Mettre à jour après les transactions de réduction des risques
                    for transaction in risk_transactions:
                        symbol, trade_type, price, quantity, value = transaction
                        
                        # Similaire au code ci-dessus pour les transactions standard
                        if trade_type == 'SELL':
                            if symbol in self.portfolio:
                                self.portfolio[symbol]['shares'] -= quantity
                                if self.portfolio[symbol]['shares'] <= 0:
                                    del self.portfolio[symbol]
                            self.cash += value
                        
                        self.transactions.append((date_str, symbol, trade_type, price, quantity, value))
                        self.logger.info(f"Transaction de risque: {trade_type} {quantity} {symbol} à {price}$ = {value}$")
                    
                    # Réévaluer le portefeuille après les actions de réduction des risques
                    portfolio_value = self.evaluate_portfolio(date_str)
        
        # Fin de la simulation
        self.calculate_performance_metrics()
        self.logger.info("Simulation de backtesting terminée")
        return self.portfolio_values, self.transactions
    
    def evaluate_portfolio(self, date_str):
        """
        Évaluer la valeur du portefeuille à une date donnée
        
        Args:
            date_str (str): Date au format 'YYYY-MM-DD'
        
        Returns:
            float: Valeur totale du portefeuille
        """
        portfolio_value = self.cash
        
        for symbol, details in self.portfolio.items():
            if symbol in self.market_data and date_str in self.market_data[symbol].index:
                price = self.market_data[symbol].loc[date_str, 'Close']
                value = details['shares'] * price
                portfolio_value += value
        
        self.portfolio_values.append((date_str, portfolio_value, self.cash))
        return portfolio_value
    
    def reduce_exposure(self, portfolio, reduction_ratio):
        """
        Réduire l'exposition du portefeuille
        
        Args:
            portfolio (dict): Portefeuille actuel
            reduction_ratio (float): Ratio de réduction (0-1)
        
        Returns:
            dict: Allocation réduite
        """
        reduced_allocation = {}
        
        for symbol, details in portfolio.items():
            # Calculer les nouvelles actions cibles (réduction)
            target_shares = int(details['shares'] * (1 - reduction_ratio))
            reduced_allocation[symbol] = target_shares
        
        return reduced_allocation
    
    def calculate_performance_metrics(self):
        """Calculer les métriques de performance du backtesting"""
        if not self.portfolio_values:
            self.logger.warning("Aucune valeur de portefeuille disponible pour calculer les métriques")
            return {}
        
        # Convertir en DataFrame pour faciliter l'analyse
        df = pd.DataFrame(self.portfolio_values, columns=['date', 'portfolio_value', 'cash'])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        # Calculer les rendements quotidiens
        df['daily_return'] = df['portfolio_value'].pct_change()
        
        # Métriques de base
        initial_value = self.initial_capital
        final_value = df['portfolio_value'].iloc[-1]
        total_return = (final_value / initial_value - 1) * 100
        
        # Rendement annualisé
        days = (df.index[-1] - df.index[0]).days
        annualized_return = ((1 + total_return/100) ** (365/days) - 1) * 100
        
        # Volatilité (annualisée)
        volatility = df['daily_return'].std() * np.sqrt(252) * 100
        
        # Ratio de Sharpe (en supposant un taux sans risque de 0% pour simplifier)
        sharpe_ratio = (annualized_return / 100) / (volatility / 100) if volatility != 0 else 0
        
        # Drawdown
        df['cummax'] = df['portfolio_value'].cummax()
        df['drawdown'] = (df['portfolio_value'] - df['cummax']) / df['cummax'] * 100
        max_drawdown = df['drawdown'].min()
        
        # Calculer le nombre de transactions
        num_transactions = len(self.transactions)
        
        # Afficher les résultats
        metrics = {
            'Initial Capital': f"${initial_value:,.2f}",
            'Final Portfolio Value': f"${final_value:,.2f}",
            'Total Return': f"{total_return:.2f}%",
            'Annualized Return': f"{annualized_return:.2f}%",
            'Volatility (annualized)': f"{volatility:.2f}%",
            'Sharpe Ratio': f"{sharpe_ratio:.2f}",
            'Maximum Drawdown': f"{max_drawdown:.2f}%",
            'Total Transactions': num_transactions
        }
        
        self.logger.info("Métriques de performance calculées:")
        for metric, value in metrics.items():
            self.logger.info(f"{metric}: {value}")
        
        # Créer et sauvegarder des graphiques
        self.plot_portfolio_performance(df)
        
        return metrics
    
    def plot_portfolio_performance(self, df):
        """
        Créer des graphiques de performance du portefeuille
        
        Args:
            df (DataFrame): DataFrame contenant les valeurs du portefeuille
        """
        plt.figure(figsize=(15, 10))
        
        # Graphique 1: Valeur du portefeuille
        plt.subplot(2, 1, 1)
        plt.plot(df.index, df['portfolio_value'], label='Portfolio Value')
        plt.plot(df.index, df['cash'], label='Cash', linestyle='--')
        plt.title('Portfolio Value Over Time')
        plt.xlabel('Date')
        plt.ylabel('Value ($)')
        plt.legend()
        plt.grid(True)
        
        # Graphique 2: Drawdown
        plt.subplot(2, 1, 2)
        plt.fill_between(df.index, df['drawdown'], 0, color='red', alpha=0.3)
        plt.plot(df.index, df['drawdown'], color='red', label='Drawdown')
        plt.title('Portfolio Drawdown')
        plt.xlabel('Date')
        plt.ylabel('Drawdown (%)')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        plt.savefig('backtest_performance.png')
        self.logger.info("Graphique de performance sauvegardé dans 'backtest_performance.png'")
        
        # Graphique des transactions
        if self.transactions:
            tx_df = pd.DataFrame(self.transactions, 
                                columns=['date', 'symbol', 'type', 'price', 'quantity', 'value'])
            tx_df['date'] = pd.to_datetime(tx_df['date'])
            
            # Graphique par symbole
            symbols = tx_df['symbol'].unique()
            
            plt.figure(figsize=(15, 10))
            plt.subplot(2, 1, 1)
            
            for symbol in symbols:
                symbol_data = df.copy()
                if symbol in self.market_data:
                    symbol_prices = self.market_data[symbol]['Close']
                    symbol_prices = symbol_prices / symbol_prices.iloc[0] * 100  # Normaliser à 100
                    plt.plot(symbol_prices.index, symbol_prices, label=symbol)
            
            portfolio_norm = df['portfolio_value'] / df['portfolio_value'].iloc[0] * 100
            plt.plot(df.index, portfolio_norm, label='Portfolio', linewidth=3, color='black')
            
            plt.title('Normalized Performance (Base 100)')
            plt.xlabel('Date')
            plt.ylabel('Value')
            plt.legend()
            plt.grid(True)
            
            # Graphique des transactions
            plt.subplot(2, 1, 2)
            buy_tx = tx_df[tx_df['type'] == 'BUY']
            sell_tx = tx_df[tx_df['type'] == 'SELL']
            
            plt.scatter(buy_tx['date'], buy_tx['value'], color='green', label='Buy', alpha=0.7)
            plt.scatter(sell_tx['date'], sell_tx['value'], color='red', label='Sell', alpha=0.7)
            
            plt.title('Transactions')
            plt.xlabel('Date')
            plt.ylabel('Transaction Value ($)')
            plt.legend()
            plt.grid(True)
            
            plt.tight_layout()
            plt.savefig('backtest_transactions.png')
            self.logger.info("Graphique des transactions sauvegardé dans 'backtest_transactions.png'")


if __name__ == "__main__":
    # Exemple d'utilisation pour backtesting
    start_date = '2020-01-01'
    end_date = '2023-01-01'
    initial_capital = 100000.0
    
    backtest = Backtester(start_date, end_date, initial_capital)
    portfolio_values, transactions = backtest.run()
    
    print("\nBacktesting terminé!")
    print(f"Capital initial: ${initial_capital:,.2f}")
    print(f"Valeur finale du portefeuille: ${portfolio_values[-1][1]:,.2f}")
    print(f"Rendement total: {(portfolio_values[-1][1] / initial_capital - 1) * 100:.2f}%")
    print(f"Nombre total de transactions: {len(transactions)}")