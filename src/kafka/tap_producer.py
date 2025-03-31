from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

schema_registry_conf = {
    'url': ''
}
schema_registry_client = SchemaRegistryClient(schema_registry_conf)

schema_id = 'lsst.tap.job-run-value'
avro_schema = schema_registry_client.get_latest_version(schema_id).schema
avro_serializer = AvroSerializer(schema_registry_client, avro_schema)

producer_conf = {
    'bootstrap.servers': '',
    'security.protocol': 'SASL_SSL',
    'sasl.mechanism': 'SCRAM-SHA-512',
    'sasl.username': '',
    'sasl.password': ''
}

producer = Producer(producer_conf)

tap_job = {
    'query': 'SELECT TOP 10 * FROM table',
    'jobID': '1'
}
topic = ''

serialization_context = SerializationContext(topic, MessageField.VALUE)
serialized_data = avro_serializer(tap_job, serialization_context)

def delivery_report(err, msg):
    if err is not None:
        print(f'Message delivery failed: {err}')
    else:
        print(f'Message delivered to {msg.topic()} [{msg.partition()}]')


producer.produce(
    topic=topic,
    value=serialized_data,
    callback=delivery_report
)

producer.flush()
