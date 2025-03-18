
# models/backtesting.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)

class BacktestStrategy:
    """Classe de base pour les stratégies de backtest"""
    
    def __init__(self, name, initial_capital=100000.0):
        self.name = name
        self.initial_capital = initial_capital
        self.positions = {}  # Dictionnaire des positions {symbole: nombre d'actions}
        self.capital = initial_capital
        self.portfolio_value_history = []
        self.trades_history = []
    
    def generate_signals(self, data):
        """
        Générer des signaux d'achat/vente (à implémenter dans les sous-classes)
        
        Args:
            data (dict): Dictionnaire des données de prix par symbole
            
        Returns:
            dict: Signaux par symbole et date
        """
        raise NotImplementedError("Cette méthode doit être implémentée dans une sous-classe")
    
    def execute_backtest(self, data, signals):
        """
        Exécuter le backtest en fonction des signaux
        
        Args:
            data (dict): Dictionnaire des données de prix par symbole
            signals (dict): Signaux d'achat/vente par symbole et date
            
        Returns:
            DataFrame: Historique de la valeur du portefeuille
        """
        try:
            # Récupérer les dates uniques triées
            all_dates = set()
            for symbol in data:
                all_dates.update(data[symbol].index)
            dates = sorted(list(all_dates))
            
            # Initialiser l'historique du portefeuille
            portfolio_history = []
            
            # Exécuter le backtest jour par jour
            for date in dates:
                daily_value = self.capital
                
                # Mettre à jour la valeur des positions existantes
                for symbol, quantity in self.positions.items():
                    if symbol in data and date in data[symbol].index:
                        price = data[symbol].loc[date, 'Close']
                        daily_value += price * quantity
                
                # Traiter les signaux du jour
                for symbol in signals:
                    if date in signals[symbol].index:
                        signal = signals[symbol].loc[date, 'Signal']
                        
                        # Exécuter les trades en fonction des signaux
                        if signal != 0 and symbol in data and date in data[symbol].index:
                            self._execute_trade(symbol, signal, data[symbol].loc[date, 'Close'], date)
                
                # Enregistrer la valeur du portefeuille pour cette date
                portfolio_history.append({
                    'Date': date,
                    'Portfolio_Value': daily_value
                })
            
            # Convertir l'historique en DataFrame
            portfolio_df = pd.DataFrame(portfolio_history)
            portfolio_df.set_index('Date', inplace=True)
            
            # Calculer les rendements journaliers
            portfolio_df['Daily_Return'] = portfolio_df['Portfolio_Value'].pct_change()
            
            # Calculer les métriques de performance
            performance_metrics = self._calculate_performance_metrics(portfolio_df)
            
            logger.info(f"Backtest terminé pour la stratégie {self.name}: {performance_metrics}")
            return portfolio_df, performance_metrics
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du backtest: {e}")
            return pd.DataFrame(), {}
    
    def _execute_trade(self, symbol, signal, price, date):
        """
        Exécuter un trade
        
        Args:
            symbol (str): Symbole de l'actif
            signal (int): Signal d'achat (1), de vente (-1) ou neutre (0)
            price (float): Prix de l'actif
            date (datetime): Date du trade
        """
        try:
            if signal > 0:  # Achat
                # Calculer le nombre d'actions à acheter (25% du capital disponible)
                allocation = self.capital * 0.25
                shares_to_buy = int(allocation / price)
                
                if shares_to_buy > 0:
                    cost = shares_to_buy * price
                    
                    # Mettre à jour le capital et les positions
                    self.capital -= cost
                    self.positions[symbol] = self.positions.get(symbol, 0) + shares_to_buy
                    
                    # Enregistrer le trade
                    self.trades_history.append({
                        'Date': date,
                        'Symbol': symbol,
                        'Action': 'BUY',
                        'Price': price,
                        'Quantity': shares_to_buy,
                        'Value': cost
                    })
                    
                    logger.debug(f"Achat de {shares_to_buy} actions de {symbol} à {price} le {date}")
            
            elif signal < 0:  # Vente
                # Vendre toutes les actions si on en possède
                if symbol in self.positions and self.positions[symbol] > 0:
                    shares_to_sell = self.positions[symbol]
                    proceeds = shares_to_sell * price
                    
                    # Mettre à jour le capital et les positions
                    self.capital += proceeds
                    self.positions[symbol] = 0
                    
                    # Enregistrer le trade
                    self.trades_history.append({
                        'Date': date,
                        'Symbol': symbol,
                        'Action': 'SELL',
                        'Price': price,
                        'Quantity': shares_to_sell,
                        'Value': proceeds
                    })
                    
                    logger.debug(f"Vente de {shares_to_sell} actions de {symbol} à {price} le {date}")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution du trade: {e}")
    
    def _calculate_performance_metrics(self, portfolio_df):
        """
        Calculer les métriques de performance du backtest
        
        Args:
            portfolio_df (DataFrame): Historique de la valeur du portefeuille
            
        Returns:
            dict: Métriques de performance
        """
        try:
            # Rendement total
            total_return = (portfolio_df['Portfolio_Value'].iloc[-1] / self.initial_capital) - 1
            
            # Rendement annualisé
            days = (portfolio_df.index[-1] - portfolio_df.index[0]).days
            annual_return = (1 + total_return) ** (365.25 / days) - 1
            
            # Volatilité annualisée
            volatility = portfolio_df['Daily_Return'].std() * np.sqrt(252)
            
            # Ratio de Sharpe (supposant un taux sans risque de 0%)
            sharpe_ratio = annual_return / volatility if volatility != 0 else 0
            
            # Drawdown maximum
            portfolio_df['Cumulative_Return'] = (1 + portfolio_df['Daily_Return']).cumprod()
            portfolio_df['Running_Max'] = portfolio_df['Cumulative_Return'].cummax()
            portfolio_df['Drawdown'] = (portfolio_df['Cumulative_Return'] / portfolio_df['Running_Max']) - 1
            max_drawdown = portfolio_df['Drawdown'].min()
            
            # Nombre de trades
            num_trades = len(self.trades_history)
            
            # Transactions gagnantes vs perdantes
            if num_trades > 0:
                trades_df = pd.DataFrame(self.trades_history)
                buy_trades = trades_df[trades_df['Action'] == 'BUY'].set_index(['Symbol', 'Date'])
                sell_trades = trades_df[trades_df['Action'] == 'SELL'].set_index(['Symbol', 'Date'])
                
                profitable_trades = 0
                losing_trades = 0
                
                for symbol in self.positions:
                    buys = buy_trades.loc[symbol] if symbol in buy_trades.index else pd.DataFrame()
                    sells = sell_trades.loc[symbol] if symbol in sell_trades.index else pd.DataFrame()
                    
                    if not buys.empty and not sells.empty:
                        # Simplification: on compare le prix moyen d'achat au prix de vente
                        avg_buy_price = buys['Value'].sum() / buys['Quantity'].sum()
                        avg_sell_price = sells['Value'].sum() / sells['Quantity'].sum()
                        
                        if avg_sell_price > avg_buy_price:
                            profitable_trades += 1
                        else:
                            losing_trades += 1
                
                win_rate = profitable_trades / (profitable_trades + losing_trades) if (profitable_trades + losing_trades) > 0 else 0
            else:
                win_rate = 0
            
            # Résultats
            metrics = {
                'total_return': total_return * 100,  # En pourcentage
                'annual_return': annual_return * 100,  # En pourcentage
                'volatility': volatility * 100,  # En pourcentage
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown * 100,  # En pourcentage
                'num_trades': num_trades,
                'win_rate': win_rate * 100  # En pourcentage
            }
            
            return metrics
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des métriques de performance: {e}")
            return {}
    
    def plot_results(self, portfolio_df):
        """
        Tracer les résultats du backtest
        
        Args:
            portfolio_df (DataFrame): Historique de la valeur du portefeuille
        """
        try:
            # Créer une figure avec 2 sous-graphiques
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [3, 1]})
            
            # Tracer la valeur du portefeuille
            portfolio_df['Portfolio_Value'].plot(ax=ax1, color='blue', linewidth=2)
            ax1.set_title(f'Résultats du Backtest - Stratégie {self.name}')
            ax1.set_ylabel('Valeur du Portefeuille ($)')
            ax1.grid(True)
            
            # Tracer le drawdown
            portfolio_df['Drawdown'].plot(ax=ax2, color='red', linewidth=2)
            ax2.set_title('Drawdown')
            ax2.set_ylabel('Drawdown (%)')
            ax2.set_ylim(bottom=min(portfolio_df['Drawdown'].min() * 1.1, -0.01), top=0.01)
            ax2.grid(True)
            
            # Ajuster la mise en page
            plt.tight_layout()
            
            # Enregistrer le graphique
            plt.savefig(f'backtest_results_{self.name}.png')
            plt.close()
            
            logger.info(f"Graphique des résultats enregistré : backtest_results_{self.name}.png")
            
        except Exception as e:
            logger.error(f"Erreur lors de la création du graphique: {e}")


class MovingAverageStrategy(BacktestStrategy):
    """Stratégie de backtest basée sur les moyennes mobiles"""
    
    def __init__(self, name="MA_Crossover", initial_capital=100000.0, short_window=50, long_window=200):
        super().__init__(name, initial_capital)
        self.short_window = short_window
        self.long_window = long_window
    
    def generate_signals(self, data):
        """
        Générer des signaux basés sur le croisement de moyennes mobiles
        
        Args:
            data (dict): Dictionnaire des données de prix par symbole
            
        Returns:
            dict: Signaux par symbole et date
        """
        signals = {}
        
        for symbol, df in data.items():
            # Copier le DataFrame pour éviter de modifier l'original
            signals_df = df.copy()
            
            # Calculer les moyennes mobiles
            signals_df[f'MA_{self.short_window}'] = df['Close'].rolling(window=self.short_window, min_periods=1).mean()
            signals_df[f'MA_{self.long_window}'] = df['Close'].rolling(window=self.long_window, min_periods=1).mean()
            
            # Initialiser la colonne des signaux
            signals_df['Signal'] = 0
            
            # Générer les signaux de croisement
            signals_df['Signal'] = np.where(
                signals_df[f'MA_{self.short_window}'] > signals_df[f'MA_{self.long_window}'], 1, 0
            )
            
            # Générer des ordres uniquement lors des changements de direction
            signals_df['Position'] = signals_df['Signal'].diff()
            
            # Ne garder que les colonnes pertinentes
            signals_df = signals_df[['Close', 'Signal', 'Position']]
            
            # Stocker les signaux pour ce symbole
            signals[symbol] = signals_df
        
        return signals


class RSIStrategy(BacktestStrategy):
    """Stratégie de backtest basée sur l'indice de force relative (RSI)"""
    
    def __init__(self, name="RSI_Strategy", initial_capital=100000.0, rsi_period=14, oversold=30, overbought=70):
        super().__init__(name, initial_capital)
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
    
    def generate_signals(self, data):
        """
        Générer des signaux basés sur le RSI
        
        Args:
            data (dict): Dictionnaire des données de prix par symbole
            
        Returns:
            dict: Signaux par symbole et date
        """
        signals = {}
        
        for symbol, df in data.items():
            # Copier le DataFrame pour éviter de modifier l'original
            signals_df = df.copy()
            
            # Calculer le RSI
            delta = signals_df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            
            rs = gain / loss
            signals_df['RSI'] = 100 - (100 / (1 + rs))
            
            # Initialiser la colonne des signaux
            signals_df['Signal'] = 0
            
            # Générer les signaux de RSI
            signals_df['Signal'] = np.where(signals_df['RSI'] < self.oversold, 1, 0)  # Achat en zone de survente
            signals_df['Signal'] = np.where(signals_df['RSI'] > self.overbought, -1, signals_df['Signal'])  # Vente en zone de surachat
            
            # Générer des ordres uniquement lors des changements de direction
            signals_df['Position'] = signals_df['Signal'].diff().fillna(0)
            
            # Ne garder que les colonnes pertinentes
            signals_df = signals_df[['Close', 'RSI', 'Signal', 'Position']]
            
            # Stocker les signaux pour ce symbole
            signals[symbol] = signals_df
        
        return signals


class MACDStrategy(BacktestStrategy):
    """Stratégie de backtest basée sur le MACD (Moving Average Convergence Divergence)"""
    
    def __init__(self, name="MACD_Strategy", initial_capital=100000.0, fast_period=12, slow_period=26, signal_period=9):
        super().__init__(name, initial_capital)
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
    
    def generate_signals(self, data):
        """
        Générer des signaux basés sur le MACD
        
        Args:
            data (dict): Dictionnaire des données de prix par symbole
            
        Returns:
            dict: Signaux par symbole et date
        """
        signals = {}
        
        for symbol, df in data.items():
            # Copier le DataFrame pour éviter de modifier l'original
            signals_df = df.copy()
            
            # Calculer les EMA
            signals_df['EMA_fast'] = signals_df['Close'].ewm(span=self.fast_period, adjust=False).mean()
            signals_df['EMA_slow'] = signals_df['Close'].ewm(span=self.slow_period, adjust=False).mean()
            
            # Calculer le MACD et sa ligne de signal
            signals_df['MACD'] = signals_df['EMA_fast'] - signals_df['EMA_slow']
            signals_df['MACD_Signal'] = signals_df['MACD'].ewm(span=self.signal_period, adjust=False).mean()
            signals_df['MACD_Hist'] = signals_df['MACD'] - signals_df['MACD_Signal']
            
            # Initialiser la colonne des signaux
            signals_df['Signal'] = 0
            
            # Générer les signaux de MACD
            signals_df['Signal'] = np.where(signals_df