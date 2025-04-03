# End-to-End Tests

[← Zurück zur README](../README.md)

Dieses Dokument beschreibt die End-to-End Tests für das Real-time Backend System.

## Voraussetzungen

### Hosts-Konfiguration

Um lokalen Zugriff auf die Services zu ermöglichen, sind folgende Einträge in `/etc/hosts` erforderlich:

```
127.0.0.1   metrics.localhost
127.0.0.1   spark.localhost
127.0.0.1   worker-1.localhost
127.0.0.1   worker-2.localhost
127.0.0.1   worker-3.localhost
127.0.0.1   processor.localhost
127.0.0.1   kafka.localhost
127.0.0.1   prometheus.localhost
```

## Testausführung

### 1. Produktionsumgebung starten

```bash
./start-production.sh
```

Das Hochfahren aller Services kann einige Zeit in Anspruch nehmen (ca. 2-3 Minuten).

### 2. Tests ausführen

```bash
./e2e-test.sh
```

Dieser Test führt automatisch folgende Überprüfungen durch:

1. **Container-Status**: Überprüft, ob alle erforderlichen Container laufen
2. **Kafka-Konnektivität**: Stellt sicher, dass Nachrichten in Kafka ankommen
3. **Spark-Verarbeitung**: Verifiziert, dass Spark Streaming aktiv ist
4. **Datenspeicherung**: Prüft, ob Daten in der TimescaleDB ankommen
5. **Aggregationen**: Überprüft die Erstellung der Minuten-Aggregationen
6. **Anomalieerkennung**: Validiert die Erkennung von Ausreißern
7. **Sensortypen**: Prüft die verschiedenen Arten von Sensordaten
8. **Datendurchsatz**: Analysiert den durchschnittlichen Durchsatz an Messungen pro Minute

## Details der Tests

### Container-Status-Prüfung

Der Test ruft `docker ps --format '{{.Names}}' | grep realtime-backend` auf und prüft, ob alle erforderlichen Container laufen, darunter:
- nginx-gateway
- kafka
- zookeeper
- spark-master
- spark-worker (1-3)
- data-generator
- data-processor
- timescaledb
- prometheus
- grafana

### Kafka-Konnektivität

Der Test prüft zunächst, ob das Topic "sensor-data" existiert und liest dann stichprobenartig Nachrichten:
```bash
docker exec realtime-backend-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list
docker exec realtime-backend-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic sensor-data --from-beginning --max-messages 5 --timeout-ms 10000
```

### Spark-Verarbeitung

In den Logs des data-processor-Containers wird nach dem Eintrag "Streaming query started" gesucht:
```bash
docker logs realtime-backend-data-processor-1 2>&1 | grep "Streaming query started"
```

### Datenspeicherung und Aggregation

Der Test führt SQL-Abfragen gegen die TimescaleDB aus:
- Zählt Einträge in der Tabelle `realtime_measurements`
- Überprüft Aggregationen in `minute_sensor_aggregates`
- Prüft auf das Vorhandensein von Anomalien in der `anomalies`-Tabelle

### Sensortypen und Durchsatz

Das Skript führt zusätzliche Analysen durch:
- Gruppiert und zählt Messungen nach Sensortyp
- Berechnet den durchschnittlichen Datendurchsatz (Messungen pro Minute)

## Fehlerbehebung

### Typische Fehler

#### Keine Daten in Kafka

Überprüfen Sie:
- Läuft der data-generator-Container? (`docker logs realtime-backend-data-generator-1`)
- Sind Netzwerkprobleme zwischen data-generator und Kafka vorhanden?

#### Keine Verarbeitung durch Spark

Überprüfen Sie:
- Logs des data-processor-Containers (`docker logs realtime-backend-data-processor-1`)
- Verbindung zwischen Spark und Kafka
- Java-Heap-Space (bei OutOfMemoryError)

#### Keine Daten in TimescaleDB

Überprüfen Sie:
- Verbindung zwischen data-processor und TimescaleDB
- Datenbank-Schema (wurden alle Tabellen korrekt erstellt?)
- Datenbank-Logs (`docker logs realtime-backend-timescaledb-1`)

### Manuelles Testen

Um die Tests manuell durchzuführen:

1. **Kafka-Nachrichten überprüfen**:
   ```bash
   docker exec realtime-backend-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic sensor-data --from-beginning --max-messages 5 --timeout-ms 10000
   ```

2. **TimescaleDB-Einträge prüfen**:
   ```bash
   docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) FROM realtime_measurements;"
   ```

3. **Anomalien überprüfen**:
   ```bash
   docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT anomaly, COUNT(*) FROM anomalies GROUP BY anomaly;"
   ```

4. **Datendurchsatz überprüfen**:
   ```bash
   docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) / (EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/60) AS avg_per_minute FROM realtime_measurements;"
   ```

## Zugriff auf Services für manuelle Inspektion

### Authentifizierung

Alle Services (außer Grafana) verwenden Basic Auth:
- Username: admin
- Password: admin

Grafana verwendet eigene Authentifizierung:
- Username: admin
- Password: admin

### Service-Endpunkte

- **Grafana**: https://metrics.localhost
- **Spark Master**: https://spark.localhost
- **Spark Worker 1-3**: https://worker-[1-3].localhost
- **Data Processor**: https://processor.localhost
- **Kafka UI**: https://kafka.localhost
- **Prometheus**: https://prometheus.localhost
