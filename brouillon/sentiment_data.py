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
        
        # Configurer l'authentification Twitter/X
        self.api = None
        self.setup_twitter_api()
    
    def setup_twitter_api(self):
        """Configurer l'API Twitter/X avec les clés d'authentification"""
        try:
            auth = tweepy.OAuth1UserHandler(
                Config.X_API_KEY,
                Config.X_API_SECRET,
                Config.X_ACCESS_TOKEN,
                Config.X_ACCESS_SECRET
            )
            self.api = tweepy.API(auth)
            logger.info("API Twitter/X configurée avec succès")
            
        except Exception as e:
            logger.error(f"Erreur lors de la configuration de l'API Twitter/X: {e}")
    
    def get_sentiment(self, symbol, days=7, count=100):
        """
        Récupérer et analyser le sentiment pour un symbole boursier
        
        Args:
            symbol (str): Symbole boursier
            days (int): Nombre de jours à remonter
            count (int): Nombre de tweets à récupérer
            
        Returns:
            dict: Résultats d'analyse de sentiment
        """
        if not self.api:
            logger.error("API Twitter/X non configurée")
            return {'compound': 0, 'positive': 0, 'neutral': 0, 'negative': 0, 'tweet_count': 0}
        
        try:
            # Préparer la recherche: symbole + nom de l'entreprise si disponible
            query = f"${symbol} OR {symbol}"
            
            # Récupérer les tweets
            tweets = tweepy.Cursor(
                self.api.search_tweets,
                q=query,
                lang="en",
                result_type="mixed",
                count=count,
                tweet_mode="extended"
            ).items(count)
            
            # Analyser le sentiment
            sentiments = []
            tweet_texts = []
            
            for tweet in tweets:
                # Prétraiter le texte du tweet
                text = self._preprocess_tweet(tweet.full_text)
                
                # Analyser le sentiment
                sentiment = self.sentiment_analyzer.polarity_scores(text)
                sentiments.append(sentiment)
                tweet_texts.append(text)
            
            # Calcul des moyennes
            if sentiments:
                avg_sentiment = {
                    'compound': sum(s['compound'] for s in sentiments) / len(sentiments),
                    'positive': sum(s['pos'] for s in sentiments) / len(sentiments),
                    'neutral': sum(s['neu'] for s in sentiments) / len(sentiments),
                    'negative': sum(s['neg'] for s in sentiments) / len(sentiments),
                    'tweet_count': len(sentiments)
                }
            else:
                avg_sentiment = {
                    'compound': 0, 'positive': 0, 'neutral': 0, 'negative': 0, 'tweet_count': 0
                }
            
            logger.info(f"Analyse de sentiment pour {symbol}: {avg_sentiment['compound']:.2f} (sur {avg_sentiment['tweet_count']} tweets)")
            
            return avg_sentiment
            
        except Exception as e:
            logger.error(f"Erreur lors de l'analyse de sentiment pour {symbol}: {e}")
            return {'compound': 0, 'positive': 0, 'neutral': 0, 'negative': 0, 'tweet_count': 0}
    
    def _preprocess_tweet(self, text):
        """
        Prétraiter le texte d'un tweet
        
        Args:
            text (str): Texte du tweet
            
        Returns:
            str: Texte prétraité
        """
        # Supprimer les URLs
        text = re.sub(r'http\S+', '', text)
        
        # Supprimer les mentions
        text = re.sub(r'@\w+', '', text)
        
        # Supprimer les hashtags
        text = re.sub(r'#\w+', '', text)
        
        # Supprimer les caractères non alphanumériques
        text = re.sub(r'[^\w\s]', '', text)
        
        # Supprimer les espaces multiples
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text