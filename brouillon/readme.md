Pour lancer le code et effectuer le backtesting du système multi-agent de trading, vous devrez suivre les étapes ci-dessous. Je vais vous guider à travers le processus de démarrage, de configuration et d'exécution du backtesting.

## 1. Préparation du système

Avant de lancer le système, assurez-vous que tous les fichiers sont correctement organisés selon la structure décrite dans l'architecture et que tous les fichiers sont créés avec leur contenu respectif.

## 2. Installation des dépendances

```bash
# Cloner le dépôt depuis GitHub (supposant que le code a été poussé sur GitHub)
git clone <votre-repo-github>
cd <nom-du-repo>

# Installer les dépendances
pip install -r requirements.txt
```

## 3. Configuration des variables d'environnement

Modifiez le fichier `.env` avec vos paramètres spécifiques, notamment :
- Les clés API pour Twitter/X
- Les symboles d'actions que vous souhaitez trader
- L'horizon de trading (LONG_TERM ou SHORT_TERM)

## 4. Initialisation de la base de données

Avant de lancer le système complet, il est recommandé d'initialiser la base de données :

```bash
python -c "from utils.database import PostgresDB; db = PostgresDB(); db.connect(); db.init_tables()"
```

## 5. Lancer le backtesting

Pour exécuter le backtesting du système, vous pouvez utiliser le script suivant que vous devriez créer (si ce n'est pas déjà fait) :


Pour exécuter le backtesting, utilisez la commande suivante :

```bash
python backtest.py
```

## 6. Lancer le système complet avec Docker

Si vous souhaitez lancer le système complet plutôt que le backtesting, utilisez Docker Compose :

```bash
# Construire les images
docker-compose build

# Lancer les services
docker-compose up -d
```

Ce processus va démarrer :
1. Les services d'infrastructure (RabbitMQ, PostgreSQL)
2. Les 5 agents analystes
3. L'agent gestionnaire
4. L'agent trader
5. L'agent de risque

## 7. Visualiser les résultats et les logs

Après avoir exécuté le backtesting ou le système en temps réel, vous pouvez visualiser :

- Les graphiques générés dans `backtest_performance.png` et `backtest_transactions.png`
- Les logs de chaque agent dans le dossier `logs/`
- Les données stockées dans la base de données PostgreSQL

Pour consulter les données dans PostgreSQL :

```bash
# Se connecter à la base de données
docker exec -it trading-postgres psql -U tradinguser -d trading_db

# Exemples de requêtes
SELECT * FROM analyst_recommendations ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM portfolio_allocations ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 10;
SELECT * FROM performance_metrics ORDER BY timestamp DESC LIMIT 10;
```

## 8. Personnalisation et optimisation

Pour adapter le système à vos besoins spécifiques :

1. Modifiez les paramètres dans le fichier `.env`
2. Ajustez les critères d'analyse dans les agents analystes
3. Modifiez les stratégies de trading dans l'agent trader
4. Ajustez les seuils de risque dans l'agent de risque

## 9. Pousser les modifications vers GitHub

Une fois que vous êtes satisfait de votre implémentation :

```bash
git add .
git commit -m "Implémentation du système multi-agent de trading"
git push origin main
```

Cette démarche vous permettra de lancer complètement le système, d'effectuer des simulations sur des données historiques, et d'optimiser ses performances avant de le déployer en production.