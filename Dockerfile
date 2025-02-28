# docker-compose.yml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    container_name: trading-rabbitmq
    ports:
      - "5672:5672"   # RabbitMQ standard port
      - "15672:15672" # Management UI
    environment:
      - RABBITMQ_DEFAULT_USER=tradinguser
      - RABBITMQ_DEFAULT_PASS=tradingpass
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    networks:
      - trading_network

  postgres:
    image: postgres:14
    container_name: trading-postgres
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=tradinguser
      - POSTGRES_PASSWORD=tradingpass
      - POSTGRES_DB=trading_db
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - trading_network

  buffet_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: buffet-agent
    command: python -m agents.analysts.buffet_agent
    depends_on:
      - rabbitmq
      - postgres
    env_file:
      - .env
    networks:
      - trading_network

  munger_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: munger-agent
    command: python -m agents.analysts.munger_agent
    depends_on:
      - rabbitmq
      - postgres
    env_file:
      - .env
    networks:
      - trading_network

  lynch_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: lynch-agent
    command: python -m agents.analysts.lynch_agent
    depends_on:
      - rabbitmq
      - postgres
    env_file:
      - .env
    networks:
      - trading_network

  graham_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: graham-agent
    command: python -m agents.analysts.graham_agent
    depends_on:
      - rabbitmq
      - postgres
    env_file:
      - .env
    networks:
      - trading_network

  dalio_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: dalio-agent
    command: python -m agents.analysts.dalio_agent
    depends_on:
      - rabbitmq
      - postgres
    env_file:
      - .env
    networks:
      - trading_network

  manager_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: manager-agent
    command: python -m agents.manager_agent
    depends_on:
      - rabbitmq
      - postgres
      - buffet_agent
      - munger_agent
      - lynch_agent
      - graham_agent
      - dalio_agent
    env_file:
      - .env
    networks:
      - trading_network

  trader_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: trader-agent
    command: python -m agents.trader_agent
    depends_on:
      - rabbitmq
      - postgres
      - manager_agent
    env_file:
      - .env
    networks:
      - trading_network

  risk_agent:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: risk-agent
    command: python -m agents.risk_agent
    depends_on:
      - rabbitmq
      - postgres
      - trader_agent
    env_file:
      - .env
    networks:
      - trading_network

networks:
  trading_network:
    driver: bridge

volumes:
  rabbitmq_data:
  postgres_data:


# Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "agents.base_agent"]


# .env
# Configuration générale
TRADING_HORIZON=LONG_TERM  # Options: SHORT_TERM, LONG_TERM
LOG_LEVEL=INFO
MAX_DRAWDOWN_THRESHOLD=10  # Pourcentage de drawdown maximal avant intervention

# Configuration RabbitMQ
RABBITMQ_HOST=rabbitmq
RABBITMQ_PORT=5672
RABBITMQ_USER=tradinguser
RABBITMQ_PASS=tradingpass
RABBITMQ_VHOST=/

# Configuration PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=tradinguser
POSTGRES_PASS=tradingpass
POSTGRES_DB=trading_db

# Configuration API X (Twitter)
X_API_KEY=your_api_key_here
X_API_SECRET=your_api_secret_here
X_ACCESS_TOKEN=your_access_token_here
X_ACCESS_SECRET=your_access_token_secret_here

# Paramètres agents
TRADING_SYMBOLS=AAPL,MSFT,GOOGL,AMZN,META,TSLA,JPM,JNJ,V,NVDA,PG,HD,DIS


# requirements.txt
# Data sources
yfinance==0.2.36
tweepy==4.14.0
pandas==2.0.3
numpy==1.26.0

# Database and messaging
psycopg2-binary==2.9.9
pika==1.3.2

# Machine learning
scikit-learn==1.3.1
tensorflow==2.15.0

# Visualization
matplotlib==3.8.0

# Utils
python-dotenv==1.0.0