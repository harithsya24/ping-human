"""Kafka consumer setup and management."""
import os
import json
from kafka import KafkaConsumer
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC_NAME")
KAFKA_GROUP = os.getenv("KAFKA_CONSUMER_GROUP")
KAFKA_USER = os.getenv("KAFKA_SASL_USERNAME")
KAFKA_PASS = os.getenv("KAFKA_SASL_PASSWORD")
KAFKA_MECH = os.getenv("KAFKA_SASL_MECHANISM", "PLAIN")

security_protocol = "SASL_SSL" if KAFKA_USER and KAFKA_PASS else "PLAINTEXT"

def create_consumer():
    """Create a new Kafka consumer with connection settings."""
    bootstrap_servers = KAFKA_BOOTSTRAP.split(",") if isinstance(KAFKA_BOOTSTRAP, str) else KAFKA_BOOTSTRAP
    print(f"[Kafka] Creating consumer with bootstrap_servers: {bootstrap_servers}")
    print(f"[Kafka] Topic: {KAFKA_TOPIC}, Group: {KAFKA_GROUP}")
    
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=bootstrap_servers,
        security_protocol=security_protocol,
        sasl_mechanism=KAFKA_MECH if KAFKA_USER else None,
        sasl_plain_username=KAFKA_USER if KAFKA_USER else None,
        sasl_plain_password=KAFKA_PASS if KAFKA_PASS else None,
        group_id=KAFKA_GROUP,
        auto_offset_reset="earliest",
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        enable_auto_commit=True,
        session_timeout_ms=30000,
        heartbeat_interval_ms=10000,
    )
    
    # Log subscription info
    print(f"[Kafka] Subscribed topics: {consumer.subscription()}")
    return consumer

