# data/sentiment_data.py (suite)
import tweepy
import pandas as pd
import re
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from utils.config import Config
import logging

logger = logging.getLogger(__name__)

class SentimentData:
    """Gestion des données de sentiment via l'API Twitter/X"""
    
    def __init__(self):
        """Initialisation de l'API Twitter et du sentiment analyzer"""
        # Télécharger les ressources NLTK nécessaires si pas déjà présentes
        try:
            nltk.data.find('vader_lexicon')
        except LookupError:
            nltk.download('vader_lexicon')
            
        # Initialiser l'analyseur de sentiment
        self.sentiment_analyzer = SentimentIntensityAnalyzer()
        
        # Initialiser l'API Twitter/X
        self._init_twitter_api()
    
    def _init_twitter_api(self):
        """Initialiser l'API Twitter/X avec les identifiants"""
        try:
            auth = tweepy.OAuth1UserHandler(
                Config.X_API_KEY,
                Config.X_API_SECRET,
                Config.X_ACCESS_TOKEN,
                Config.X_ACCESS_SECRET
            )
            self.api = tweepy.API(auth)
            logger.info("API Twitter/X initialisée avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de l'API Twitter/X: {e}")
            self.api = None
    
    def get_tweets(self, query, count=100, lang='en'):
        """
        Rechercher des tweets sur un sujet spécifique
        
        Args:
            query (str): Requête de recherche
            count (int): Nombre de tweets à récupérer
            lang (str): Langue des tweets
        
        Returns:
            list: Liste des tweets récupérés
        """
        if not self.api:
            logger.error("API Twitter/X non initialisée")
            return []
        
        try:
            tweets = self.api.search_tweets(
                q=query,
                count=count,
                lang=lang,
                tweet_mode='extended'
            )
            
            logger.info(f"{len(tweets)} tweets récupérés pour la requête '{query}'")
            return tweets
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des tweets: {e}")
            return []
    
    def preprocess_tweet(self, tweet_text):
        """
        Prétraiter le texte d'un tweet
        
        Args:
            tweet_text (str): Texte du tweet
        
        Returns:
            str: Texte prétraité
        """
        # Supprimer les URLs
        tweet_text = re.sub(r'http\S+', '', tweet_text)
        # Supprimer les mentions et hashtags
        tweet_text = re.sub(r'@\w+|#\w+', '', tweet_text)
        # Supprimer les caractères spéciaux et convertir en minuscules
        tweet_text = re.sub(r'[^\w\s]', '', tweet_text.lower())
        return tweet_text.strip()
    
    def analyze_sentiment(self, tweet_text):
        """
        Analyser le sentiment d'un texte
        
        Args:
            tweet_text (str): Texte à analyser
        
        Returns:
            dict: Scores de sentiment
        """
        return self.sentiment_analyzer.polarity_scores(tweet_text)
    
    def get_company_sentiment(self, company_symbol, company_name=None, count=100):
        """
        Obtenir le sentiment général pour une entreprise
        
        Args:
            company_symbol (str): Symbole boursier
            company_name (str): Nom de l'entreprise (optionnel)
            count (int): Nombre de tweets à analyser
        
        Returns:
            dict: Résumé du sentiment
        """
        # Construire la requête
        query = f"${company_symbol}"
        if company_name:
            query += f" OR {company_name}"
        
        # Récupérer les tweets
        tweets = self.get_tweets(query, count)
        
        if not tweets:
            return {
                'symbol': company_symbol,
                'tweet_count': 0,
                'sentiment_avg': 0,
                'sentiment_std': 0,
                'positive_ratio': 0,
                'negative_ratio': 0,
                'neutral_ratio': 0
            }
        
        # Analyser le sentiment de chaque tweet
        sentiments = []
        for tweet in tweets:
            text = tweet.full_text if hasattr(tweet, 'full_text') else tweet.text
            processed_text = self.preprocess_tweet(text)
            sentiment = self.analyze_sentiment(processed_text)
            sentiments.append(sentiment)
        
        # Calculer les statistiques
        compound_scores = [s['compound'] for s in sentiments]
        positive_count = sum(1 for s in compound_scores if s > 0.05)
        negative_count = sum(1 for s in compound_scores if s < -0.05)
        neutral_count = len(compound_scores) - positive_count - negative_count
        
        return {
            'symbol': company_symbol,
            'tweet_count': len(tweets),
            'sentiment_avg': pd.Series(compound_scores).mean(),
            'sentiment_std': pd.Series(compound_scores).std(),
            'positive_ratio': positive_count / len(tweets),
            'negative_ratio': negative_count / len(tweets),
            'neutral_ratio': neutral_count / len(tweets)
        }
