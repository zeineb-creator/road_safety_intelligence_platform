from confluent_kafka import Producer

p = Producer({"bootstrap.servers": "localhost:9092"})
for i in range(10):
    p.produce("crashes.raw", key=str(i), value=f'{{"id": {i}}}')
p.flush()
print("sent 10 messages")