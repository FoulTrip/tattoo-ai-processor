import pika
import json
import os
from dotenv import load_dotenv
from typing import Optional, Callable, Dict, Any
from pika.exceptions import AMQPConnectionError
from pika.adapters.blocking_connection import BlockingChannel

# Cargar variables de entorno
load_dotenv()

# Variables de configuración desde .env
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "admin")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "admin123")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
RABBITMQ_QUEUE_NAME = os.getenv("RABBITMQ_QUEUE_NAME", "image_processing_queue")


class RabbitMQClient:
    """
    Cliente para la gestión de colas de mensajes con RabbitMQ.
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        vhost: str = "/",
        queue_name: str = "default_queue"
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.vhost = vhost
        self.queue_name = queue_name
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[BlockingChannel] = None
        
        try:
            self._connect()
            print(f"✅ Conexión a RabbitMQ establecida en: {host}:{port}")
        except Exception as e:
            print(f"❌ Error al inicializar el cliente de RabbitMQ: {e}")
            raise

    def _connect(self):
        """Establece la conexión con RabbitMQ."""
        credentials = pika.PlainCredentials(self.user, self.password)
        parameters = pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300
        )
        
        try:
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            
            # Declarar la cola (idempotente: si existe, no hace nada)
            self.channel.queue_declare(
                queue=self.queue_name,
                durable=True  # La cola sobrevive a reinicios del broker
            )
        except AMQPConnectionError as e:
            raise Exception(f"No se pudo conectar a RabbitMQ: {e}")

    def _ensure_connection(self):
        """Verifica y reestablece la conexión si es necesario."""
        if self.connection is None or self.connection.is_closed:
            self._connect()

    # ------------------------------------
    # MÉTODOS PARA PUBLICAR MENSAJES
    # ------------------------------------

    def publish_message(
        self,
        message: Dict[str, Any],
        routing_key: Optional[str] = None
    ) -> bool:
        """
        Publica un mensaje en la cola.
        
        Args:
            message: Diccionario con los datos del mensaje
            routing_key: Nombre de la cola (si es None, usa self.queue_name)
        
        Returns:
            bool: True si se publicó correctamente
        """
        try:
            self._ensure_connection()
            
            if self.channel is None:
                raise Exception("No se pudo establecer conexión con RabbitMQ")
            
            queue = routing_key or self.queue_name
            
            # Convertir el mensaje a JSON
            message_body = json.dumps(message)
            
            # Publicar el mensaje
            self.channel.basic_publish(
                exchange='',  # Exchange por defecto
                routing_key=queue,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,  # Hacer el mensaje persistente
                    content_type='application/json'
                )
            )
            
            print(f"📤 Mensaje publicado en cola '{queue}': {message}")
            return True
            
        except Exception as e:
            print(f"❌ Error al publicar mensaje: {e}")
            return False

    def publish_image_task(
        self,
        filename: str,
        bucket: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Publica una tarea de procesamiento de imagen.
        
        Args:
            filename: Nombre del archivo en MinIO
            bucket: Nombre del bucket donde está la imagen
            metadata: Metadata adicional de la imagen
        
        Returns:
            bool: True si se publicó correctamente
        """
        task = {
            "task_type": "image_processing",
            "filename": filename,
            "bucket": bucket,
            "metadata": metadata or {}
        }
        return self.publish_message(task)

    # ------------------------------------
    # MÉTODOS PARA CONSUMIR MENSAJES
    # ------------------------------------

    def consume_messages(
        self,
        callback: Callable[[Dict[str, Any]], None],
        auto_ack: bool = False
    ):
        """
        Consume mensajes de la cola de forma continua.
        
        Args:
            callback: Función que se ejecutará por cada mensaje recibido
            auto_ack: Si True, confirma automáticamente los mensajes
        """
        try:
            self._ensure_connection()
            
            if self.channel is None:
                raise Exception("No se pudo establecer conexión con RabbitMQ")
            
            def wrapper_callback(ch, method, properties, body):
                try:
                    # Decodificar el mensaje JSON
                    message = json.loads(body.decode('utf-8'))
                    print(f"📥 Mensaje recibido: {message}")
                    
                    # Ejecutar el callback del usuario
                    callback(message)
                    
                    # Confirmar el mensaje si no es auto_ack
                    if not auto_ack:
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                        
                except json.JSONDecodeError as e:
                    print(f"❌ Error al decodificar mensaje: {e}")
                    if not auto_ack:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                except Exception as e:
                    print(f"❌ Error al procesar mensaje: {e}")
                    if not auto_ack:
                        # Reencolar el mensaje para reintentarlo
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            
            # Configurar QoS: procesar un mensaje a la vez
            self.channel.basic_qos(prefetch_count=1)
            
            # Comenzar a consumir
            self.channel.basic_consume(
                queue=self.queue_name,
                on_message_callback=wrapper_callback,
                auto_ack=auto_ack
            )
            
            print(f"🔄 Esperando mensajes en la cola '{self.queue_name}'. Presiona CTRL+C para salir.")
            self.channel.start_consuming()
            
        except KeyboardInterrupt:
            print("\n⏹️  Deteniendo consumidor...")
            self.stop_consuming()
        except Exception as e:
            print(f"❌ Error al consumir mensajes: {e}")
            raise

    def stop_consuming(self):
        """Detiene el consumo de mensajes."""
        if self.channel:
            self.channel.stop_consuming()

    # ------------------------------------
    # MÉTODOS DE UTILIDAD
    # ------------------------------------

    def get_queue_size(self, queue_name: Optional[str] = None) -> int:
        """Obtiene el número de mensajes en la cola."""
        try:
            self._ensure_connection()
            
            if self.channel is None:
                raise Exception("No se pudo establecer conexión con RabbitMQ")
            
            queue = queue_name or self.queue_name
            result = self.channel.queue_declare(queue=queue, durable=True, passive=True)
            return result.method.message_count
        except Exception as e:
            print(f"❌ Error al obtener tamaño de cola: {e}")
            return -1

    def purge_queue(self, queue_name: Optional[str] = None) -> bool:
        """Elimina todos los mensajes de la cola."""
        try:
            self._ensure_connection()
            
            if self.channel is None:
                raise Exception("No se pudo establecer conexión con RabbitMQ")
            
            queue = queue_name or self.queue_name
            self.channel.queue_purge(queue=queue)
            print(f"🗑️  Cola '{queue}' purgada exitosamente")
            return True
        except Exception as e:
            print(f"❌ Error al purgar cola: {e}")
            return False

    def close(self):
        """Cierra la conexión con RabbitMQ."""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            print("🔴 Conexión a RabbitMQ cerrada")
        except Exception as e:
            print(f"❌ Error al cerrar conexión: {e}")


# ------------------------------------
# INSTANCIA GLOBAL
# ------------------------------------

rabbitmq_client: Optional[RabbitMQClient] = None


def get_rabbitmq_client() -> RabbitMQClient:
    """
    Obtiene la instancia global del cliente de RabbitMQ.
    Si no existe, la crea con las configuraciones por defecto.
    """
    global rabbitmq_client
    if rabbitmq_client is None:
        rabbitmq_client = RabbitMQClient(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            user=RABBITMQ_USER,
            password=RABBITMQ_PASSWORD,
            vhost=RABBITMQ_VHOST,
            queue_name=RABBITMQ_QUEUE_NAME
        )
    return rabbitmq_client