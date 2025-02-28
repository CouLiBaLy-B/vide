
# data/market_data.py
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class MarketData:
    """Gestion des données de marché via yfinance"""
    
    @staticmethod
    def get_historical_data(symbols, period='1y', interval='1d'):
        """
        Récupérer les données historiques pour une liste de symboles
        
        Args:
            symbols (list): Liste des symboles boursiers
            period (str): Période de temps ('1d','5d','1mo','3mo','6mo','1y','2y','5y','10y','ytd','max')
            interval (str): Intervalle ('1m','2m','5m','15m','30m','60m','90m','1h','1d','5d','1wk','1mo','3mo')
        
        Returns:
            dict: Dictionnaire des DataFrames pour chaque symbole
        """
        if isinstance(symbols, str):
            symbols = [symbols]
        
        result = {}
        
        try:
            # Récupérer les données pour tous les symboles d'un coup
            data = yf.download(
                tickers=symbols,
                period=period,
                interval=interval,
                group_by='ticker',
                auto_adjust=True,
                prepost=False,
                threads=True
            )
            
            # Si un seul symbole, yfinance ne structure pas de la même façon
            if len(symbols) == 1:
                result[symbols[0]] = data
            else:
                # Réorganiser les données par symbole
                for symbol in symbols:
                    if symbol in data.columns.levels[0]:
                        result[symbol] = data[symbol].copy()
            
            logger.info(f"Données historiques récupérées pour {len(result)} symboles")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données historiques: {e}")
            return {}
    
    @staticmethod
    def get_fundamental_data(symbol):
        """
        Récupérer les données fondamentales pour un symbole
        
        Args:
            symbol (str): Symbole boursier
        
        Returns:
            dict: Données fondamentales
        """
        try:
            ticker = yf.Ticker(symbol)
            
            # Récupérer les informations de base
            info = ticker.info
            
            # Récupérer les données financières
            financials = {
                'income_statement': ticker.income_stmt,
                'balance_sheet': ticker.balance_sheet,
                'cash_flow': ticker.cashflow
            }
            
            # Récupérer les ratios importants
            # Calculer les ratios à partir des données financières
            fundamental_data = {
                'info': info,
                'financials': financials,
                'ratios': MarketData._calculate_ratios(info, financials)
            }
            
            logger.info(f"Données fondamentales récupérées pour {symbol}")
            return fundamental_data
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données fondamentales pour {symbol}: {e}")
            return {}
    
    @staticmethod
    def _calculate_ratios(info, financials):
        """
        Calculer les ratios financiers
        
        Args:
            info (dict): Informations générales du ticker
            financials (dict): Données financières
        
        Returns:
            dict: Ratios calculés
        """
        ratios = {}
        
        try:
            # Ratios de base à partir des infos
            if 'returnOnEquity' in info:
                ratios['ROE'] = info['returnOnEquity']
            
            if 'debtToEquity' in info:
                ratios['debt_to_equity'] = info['debtToEquity'] / 100.0  # Convertir en ratio décimal
            
            if 'priceToBook' in info:
                ratios['P/B'] = info['priceToBook']
            
            if 'trailingPE' in info:
                ratios['P/E'] = info['trailingPE']
            
            # Calculer la croissance des bénéfices si nous avons l'état des revenus
            if 'income_statement' in financials and not financials['income_statement'].empty:
                income_stmt = financials['income_statement']
                
                if 'Net Income' in income_stmt.index:
                    net_income = income_stmt.loc['Net Income']
                    
                    # Calculer la croissance sur différentes périodes
                    years = len(net_income.columns)
                    
                    if years >= 2:
                        # Croissance sur 1 an
                        latest = net_income.iloc[:, 0]
                        previous = net_income.iloc[:, 1]
                        ratios['earnings_growth_1y'] = ((latest / previous) - 1) * 100
                    
                    if years >= 3:
                        # Croissance sur 3 ans
                        latest = net_income.iloc[:, 0]
                        three_years_ago = net_income.iloc[:, 2]
                        ratios['earnings_growth_3y'] = ((latest / three_years_ago) ** (1/3) - 1) * 100
                    
                    if years >= 5:
                        # Croissance sur 5 ans
                        latest = net_income.iloc[:, 0]
                        five_years_ago = net_income.iloc[:, 4]
                        ratios['earnings_growth_5y'] = ((latest / five_years_ago) ** (1/5) - 1) * 100
            
            # Calculer le Graham Number si possible
            if 'income_statement' in financials and 'balance_sheet' in financials:
                income_stmt = financials['income_statement']
                balance_sheet = financials['balance_sheet']
                
                if ('Net Income' in income_stmt.index and 
                    'Total Stockholder Equity' in balance_sheet.index and
                    'Shares Outstanding' in info):
                    
                    net_income = income_stmt.loc['Net Income'].iloc[0]
                    stockholder_equity = balance_sheet.loc['Total Stockholder Equity'].iloc[0]
                    shares_outstanding = info['sharesOutstanding']
                    
                    eps = net_income / shares_outstanding
                    bvps = stockholder_equity / shares_outstanding
                    
                    # Graham Number = sqrt(15 * EPS * 1.5 * BVPS)
                    ratios['graham_number'] = np.sqrt(15 * eps * 1.5 * bvps)
            
            return ratios
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul des ratios: {e}")
            return ratios
