

# data/sentiment_data.py
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
        self.sentiment_analyzer