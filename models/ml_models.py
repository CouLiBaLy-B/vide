# models/ml_models.py
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import train_test_split, TimeSeriesSplit
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import logging

logger = logging.getLogger(__name__)

class PredictionModel:
    """Classe de base pour les modèles de prédiction"""
    
    def __init__(self, model_name):
        self.model_name = model_name
        self.model = None
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        
    def prepare_data(self, df, features, target, test_size=0.2):
        """
        Préparer les données pour l'entraînement et les tests
        
        Args:
            df (DataFrame): DataFrame contenant les données
            features (list): Liste des colonnes à utiliser comme features
            target (str): Colonne cible à prédire
            test_size (float): Proportion des données à utiliser pour les tests
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        try:
            # Sélectionner les features et la cible
            X = df[features].values
            y = df[target].values.reshape(-1, 1)
            
            # Normaliser les données
            X_scaled = self.scaler_X.fit_transform(X)
            y_scaled = self.scaler_y.fit_transform(y)
            
            # Division en ensembles d'entraînement et de test en respectant l'ordre temporel
            X_train, X_test, y_train, y_test = train_test_split(
                X_scaled, y_scaled, test_size=test_size, shuffle=False
            )
            
            logger.info(f"Données préparées: {X_train.shape[0]} échantillons d'entraînement, {X_test.shape[0]} échantillons de test")
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            logger.error(f"Erreur lors de la préparation des données: {e}")
            raise
    
    def train(self, X_train, y_train):
        """
        Entraîner le modèle (à implémenter dans les sous-classes)
        
        Args:
            X_train: Features d'entraînement
            y_train: Cible d'entraînement
        """
        raise NotImplementedError("Cette méthode doit être implémentée dans une sous-classe")
    
    def predict(self, X):
        """
        Faire des prédictions
        
        Args:
            X: Features pour la prédiction
            
        Returns:
            array: Prédictions
        """
        if self.model is None:
            logger.error("Le modèle n'a pas été entraîné")
            return None
        
        try:
            # Normaliser les données d'entrée
            X_scaled = self.scaler_X.transform(X)
            
            # Faire la prédiction
            y_pred_scaled = self.model.predict(X_scaled)
            
            # Dénormaliser la prédiction
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1))
            
            return y_pred
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            return None
    
    def evaluate(self, X_test, y_test):
        """
        Évaluer les performances du modèle
        
        Args:
            X_test: Features de test
            y_test: Cible de test
            
        Returns:
            dict: Métriques d'évaluation
        """
        if self.model is None:
            logger.error("Le modèle n'a pas été entraîné")
            return None
        
        try:
            # Faire des prédictions sur les données de test
            y_pred_scaled = self.model.predict(X_test)
            
            # Dénormaliser les prédictions et les valeurs réelles
            y_pred = self.scaler_y.inverse_transform(y_pred_scaled.reshape(-1, 1))
            y_true = self.scaler_y.inverse_transform(y_test)
            
            # Calculer les métriques
            metrics = {
                'mse': mean_squared_error(y_true, y_pred),
                'rmse': np.sqrt(mean_squared_error(y_true, y_pred)),
                'mae': mean_absolute_error(y_true, y_pred),
                'r2': r2_score(y_true, y_pred)
            }
            
            logger.info(f"Évaluation du modèle {self.model_name}: {metrics}")
            return metrics
            
        except Exception as e:
            logger.error(f"Erreur lors de l'évaluation: {e}")
            return None


class RandomForestModel(PredictionModel):
    """Modèle de prédiction basé sur Random Forest"""
    
    def __init__(self, n_estimators=100, random_state=42):
        super().__init__("RandomForest")
        self.n_estimators = n_estimators
        self.random_state = random_state
    
    def train(self, X_train, y_train):
        """
        Entraîner le modèle Random Forest
        
        Args:
            X_train: Features d'entraînement
            y_train: Cible d'entraînement
        """
        try:
            # Initialiser le modèle
            self.model = RandomForestRegressor(
                n_estimators=self.n_estimators,
                random_state=self.random_state,
                n_jobs=-1  # Utiliser tous les cœurs disponibles
            )
            
            # Entraîner le modèle
            self.model.fit(X_train, y_train.ravel())
            
            logger.info(f"Modèle {self.model_name} entraîné avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle {self.model_name}: {e}")
            return False


class GradientBoostingModel(PredictionModel):
    """Modèle de prédiction basé sur Gradient Boosting"""
    
    def __init__(self, n_estimators=100, learning_rate=0.1, random_state=42):
        super().__init__("GradientBoosting")
        self.n_estimators = n_estimators
        self.learning_rate = learning_rate
        self.random_state = random_state
    
    def train(self, X_train, y_train):
        """
        Entraîner le modèle Gradient Boosting
        
        Args:
            X_train: Features d'entraînement
            y_train: Cible d'entraînement
        """
        try:
            # Initialiser le modèle
            self.model = GradientBoostingRegressor(
                n_estimators=self.n_estimators,
                learning_rate=self.learning_rate,
                random_state=self.random_state
            )
            
            # Entraîner le modèle
            self.model.fit(X_train, y_train.ravel())
            
            logger.info(f"Modèle {self.model_name} entraîné avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle {self.model_name}: {e}")
            return False


class LSTMModel(PredictionModel):
    """Modèle de prédiction basé sur LSTM (Long Short-Term Memory)"""
    
    def __init__(self, sequence_length=10, units=50, dropout=0.2, epochs=50, batch_size=32):
        super().__init__("LSTM")
        self.sequence_length = sequence_length
        self.units = units
        self.dropout = dropout
        self.epochs = epochs
        self.batch_size = batch_size
    
    def prepare_sequences(self, df, features, target, test_size=0.2):
        """
        Préparer les séquences pour LSTM
        
        Args:
            df (DataFrame): DataFrame contenant les données
            features (list): Liste des colonnes à utiliser comme features
            target (str): Colonne cible à prédire
            test_size (float): Proportion des données à utiliser pour les tests
            
        Returns:
            tuple: (X_train, X_test, y_train, y_test)
        """
        try:
            # Sélectionner les features et la cible
            data = df[features + [target]].values
            
            # Normaliser les données
            data_scaled = self.scaler_X.fit_transform(data)
            
            # Créer des séquences
            X_sequences = []
            y_values = []
            
            for i in range(len(data_scaled) - self.sequence_length):
                X_sequences.append(data_scaled[i:i+self.sequence_length, :-1])
                y_values.append(data_scaled[i+self.sequence_length, -1])
            
            X = np.array(X_sequences)
            y = np.array(y_values).reshape(-1, 1)
            
            # Division en ensembles d'entraînement et de test en respectant l'ordre temporel
            train_size = int(len(X) * (1 - test_size))
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]
            
            logger.info(f"Séquences préparées: {X_train.shape[0]} séquences d'entraînement, {X_test.shape[0]} séquences de test")
            return X_train, X_test, y_train, y_test
            
        except Exception as e:
            logger.error(f"Erreur lors de la préparation des séquences: {e}")
            raise
    
    def train(self, X_train, y_train):
        """
        Entraîner le modèle LSTM
        
        Args:
            X_train: Features d'entraînement (séquences)
            y_train: Cible d'entraînement
        """
        try:
            # Récupérer les dimensions
            n_samples, n_timesteps, n_features = X_train.shape
            
            # Initialiser le modèle
            self.model = Sequential()
            
            # Première couche LSTM avec retour de séquences
            self.model.add(LSTM(
                units=self.units,
                return_sequences=True,
                input_shape=(n_timesteps, n_features)
            ))
            self.model.add(Dropout(self.dropout))
            
            # Deuxième couche LSTM
            self.model.add(LSTM(units=self.units))
            self.model.add(Dropout(self.dropout))
            
            # Couche de sortie
            self.model.add(Dense(1))
            
            # Compiler le modèle
            self.model.compile(optimizer='adam', loss='mean_squared_error')
            
            # Entraîner le modèle
            self.model.fit(
                X_train, y_train,
                epochs=self.epochs,
                batch_size=self.batch_size,
                validation_split=0.1,
                verbose=1
            )
            
            logger.info(f"Modèle {self.model_name} entraîné avec succès")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'entraînement du modèle {self.model_name}: {e}")
            return False
    
    def predict(self, X):
        """
        Faire des prédictions avec le modèle LSTM
        
        Args:
            X: Features pour la prédiction (séquences)
            
        Returns:
            array: Prédictions
        """
        if self.model is None:
            logger.error("Le modèle n'a pas été entraîné")
            return None
        
        try:
            # Faire la prédiction
            y_pred_scaled = self.model.predict(X)
            
            # Créer un tableau pour la dénormalisation
            # Nous avons besoin d'un tableau avec toutes les colonnes des données d'origine
            # mais nous ne nous intéressons qu'à la colonne cible
            dummy_array = np.zeros((y_pred_scaled.shape[0], self.scaler_X.n_features_in_))
            dummy_array[:, -1] = y_pred_scaled.flatten()
            
            # Dénormaliser la prédiction
            dummy_array_inverse = self.scaler_X.inverse_transform(dummy_array)
            y_pred = dummy_array_inverse[:, -1].reshape(-1, 1)
            
            return y_pred
            
        except Exception as e:
            logger.error(f"Erreur lors de la prédiction: {e}")
            return None
