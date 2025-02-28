# utils/messaging.py
import json
import pika
from utils.config import Config
import logging

logger = logging.getLogger(__name__)

class RabbitMQ:
    """Interface pour les communications via RabbitMQ"""
    
    def __init__(self):
        self.connection = None
        self.channel = None
        
    def connect(self):
        """Établir une connexion avec RabbitMQ"""
        try:
            credentials = pika.PlainCredentials(
                Config.RABBITMQ_USER, 
                Config.RABBITMQ_PASS
            )
            
            parameters = pika.ConnectionParameters(
                host=Config.RABBITMQ_HOST,
                port=Config.RABBITMQ_PORT,
                virtual_host=Config.RABBITMQ_VHOST,
                credentials=credentials
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info("Connexion établie avec RabbitMQ")
            
        except Exception as e:
            logger.error(f"Erreur de connexion à RabbitMQ: {e}")
            raise
    
    def close(self):
        """Fermer la connexion"""
        if self.connection and self.connection.is_open:
            self.connection.close()
            logger.info("Connexion RabbitMQ fermée")
    
    def declare_exchange(self, exchange_name, exchange_type='direct'):
        """Déclarer un exchange"""
        if not self.channel:
            self.connect()
        
        self.channel.exchange_declare(
            exchange=exchange_name,
            exchange_type=exchange_type,
            durable=True
        )
        logger.info(f"Exchange '{exchange_name}' déclaré")
    
    def declare_queue(self, queue_name):
        """Déclarer une file d'attente"""
        if not self.channel:
            self.connect()
        
        self.channel.queue_declare(
            queue=queue_name,
            durable=True
        )
        logger.info(f"Queue '{queue_name}' déclarée")
    
    def bind_queue(self, queue_name, exchange_name, routing_key):
        """Lier une file d'attente à un exchange"""
        if not self.channel:
            self.connect()
        
        self.channel.queue_bind(
            queue=queue_name,
            exchange=exchange_name,
            routing_key=routing_key
        )
        logger.info(f"Queue '{queue_name}' liée à l'exchange '{exchange_name}' avec la clé '{routing_key}'")
    
    def publish(self, exchange_name, routing_key, message):
        """Publier un message"""
        if not self.channel:
            self.connect()
        
        if isinstance(message, dict):
            message = json.dumps(message)
        
        self.channel.basic_publish(
            exchange=exchange_name,
            routing_key=routing_key,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2,  # Message persistant
                content_type='application/json'
            )
        )
        logger.debug(f"Message publié sur l'exchange '{exchange_name}', clé '{routing_key}'")
    
    def consume(self, queue_name, callback):
        """Consommer des messages d'une file d'attente"""
        if not self.channel:
            self.connect()
        
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=False
        )
        
        logger.info(f"En attente de messages sur la queue '{queue_name}'...")
        self.channel.start_consuming()
