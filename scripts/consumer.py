from confluent_kafka import Consumer

c = Consumer({
    "bootstrap.servers": "localhost:9092",
    "group.id": "test2",
    "auto.offset.reset": "earliest",
})
c.subscribe(["crashes.raw"])
while True:
    m = c.poll(1.0)
    if m is None:
        continue
    if m.error():
        print(m.error())
        continue
    print(m.key(), m.value())