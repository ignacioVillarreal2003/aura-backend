import pika
import json

from app.configuration.environment_variables import environment_variables


credentials = pika.PlainCredentials(
    environment_variables.rabbitmq_user,
    environment_variables.rabbitmq_password
)

parameters = pika.ConnectionParameters(
    host=environment_variables.rabbitmq_host,
    port=environment_variables.rabbitmq_port,
    credentials=credentials
)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()

channel.exchange_declare(
    exchange=environment_variables.exchange,
    exchange_type='direct',
    durable=True
)

channel.queue_declare(
    queue=environment_variables.queue,
    durable=True
)

channel.queue_bind(
    exchange=environment_variables.exchange,
    queue=environment_variables.queue,
    routing_key=environment_variables.queue
)

def publish_document(document_id: int):
    message = json.dumps({"document_id": document_id})

    channel.basic_publish(
        exchange=environment_variables.exchange,
        routing_key=environment_variables.queue,
        body=message,
        properties=pika.BasicProperties(
            delivery_mode=2
        )
    )

def close_rabbitmq_connection():
    if connection and not connection.is_closed:
        connection.close()