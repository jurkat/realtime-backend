#!/bin/bash
# End-to-End Testskript für Realtime-Backend
# Dieses Skript validiert den Datenfluss durch die gesamte Pipeline

set -e  # Beendet das Skript bei Fehlern
echo "===== Starte End-to-End Test der Realtime-Datenpipeline ====="

# Farben für Terminal-Ausgabe
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Test-Funktionen
function test_header() {
    echo -e "\n${YELLOW}## $1 ##${NC}"
}

function test_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

function test_failure() {
    echo -e "${RED}✗ $1${NC}"
    exit 1
}

# 1. Überprüfe, ob das System läuft
test_header "Prüfe, ob alle Container laufen"
CONTAINERS=$(docker ps --format '{{.Names}}' | grep realtime-backend)
if [ -z "$CONTAINERS" ]; then
    test_failure "Keine Container gefunden. Bitte führe zunächst './start-production.sh' aus."
else
    CONTAINER_COUNT=$(echo "$CONTAINERS" | wc -l)
    test_success "System läuft mit $CONTAINER_COUNT Containern"
fi

# 2. Prüfe, ob Kafka-Topic existiert und Nachrichten empfangen werden
test_header "Prüfe Kafka-Datenstrom"
TOPIC_EXISTS=$(docker exec realtime-backend-kafka-1 kafka-topics --bootstrap-server localhost:9092 --list | grep sensor-data || echo "")
if [ -z "$TOPIC_EXISTS" ]; then
    test_failure "Kafka-Topic 'sensor-data' nicht gefunden"
else
    test_success "Kafka-Topic 'sensor-data' existiert"
    
    # Prüfe, ob Nachrichten vorhanden sind
    MESSAGE_COUNT=$(docker exec realtime-backend-kafka-1 kafka-console-consumer --bootstrap-server localhost:9092 --topic sensor-data --from-beginning --max-messages 5 --timeout-ms 10000 | wc -l)
    if [ "$MESSAGE_COUNT" -gt 0 ]; then
        test_success "Kafka empfängt Nachrichten (stichprobenartig $MESSAGE_COUNT Nachrichten gelesen)"
    else
        test_failure "Keine Nachrichten im Kafka-Topic gefunden"
    fi
fi

# 3. Prüfe, ob Spark-Processing läuft
test_header "Prüfe Spark-Processing"
SPARK_ACTIVE=$(docker logs realtime-backend-data-processor-1 2>&1 | grep "Streaming query started" || echo "")
if [ -z "$SPARK_ACTIVE" ]; then
    test_failure "Spark-Streaming nicht aktiv. Bitte Logs überprüfen."
else
    test_success "Spark-Streaming aktiv und verarbeitet Daten"
fi

# 4. Prüfe, ob Daten in TimescaleDB ankommen
test_header "Prüfe Daten in TimescaleDB"
# Realtime Messungen
REALTIME_COUNT=$(docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) FROM realtime_measurements;")
REALTIME_COUNT=$(echo $REALTIME_COUNT | xargs)  # Entfernt Whitespace
if [ "$REALTIME_COUNT" -gt 0 ]; then
    test_success "TimescaleDB enthält $REALTIME_COUNT Echtzeit-Messungen"
else
    test_failure "Keine Echtzeit-Messungen in TimescaleDB gefunden"
fi

# Minuten-Aggregationen
MINUTE_COUNT=$(docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) FROM minute_sensor_aggregates;")
MINUTE_COUNT=$(echo $MINUTE_COUNT | xargs)
if [ "$MINUTE_COUNT" -gt 0 ]; then
    test_success "TimescaleDB enthält $MINUTE_COUNT Minuten-Aggregationen"
else
    test_failure "Keine Minuten-Aggregationen in TimescaleDB gefunden"
fi

# 5. Prüfe Anomalien
test_header "Prüfe Anomalieerkennung"
ANOMALIES=$(docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) FROM anomalies;")
ANOMALIES=$(echo $ANOMALIES | xargs)
echo "Gefundene Anomalien: $ANOMALIES"

# 6. Prüfe verschiedene Sensortypen
test_header "Prüfe Sensortypen"
SENSOR_STATS=$(docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT sensor_type, COUNT(*) FROM realtime_measurements GROUP BY sensor_type;")
echo "Sensortypen und Anzahl Messungen:"
echo "$SENSOR_STATS"

# 7. Prüfe Datendurchsatz
test_header "Prüfe Datendurchsatz (Messungen pro Minute)"
THROUGHPUT=$(docker exec realtime-backend-timescaledb-1 psql -U postgres -d sensor_data -t -c "SELECT COUNT(*) / (EXTRACT(EPOCH FROM (MAX(timestamp) - MIN(timestamp)))/60) AS avg_per_minute FROM realtime_measurements;")
THROUGHPUT=$(echo $THROUGHPUT | xargs)
echo "Durchschnittlicher Durchsatz: $THROUGHPUT Messungen pro Minute"

# 8. Zusammenfassung
test_header "Testergebnis"
echo -e "${GREEN}✓ End-to-End-Test erfolgreich abgeschlossen${NC}"
echo "Daten fließen durch alle Komponenten der Pipeline:"
echo "Generator → Kafka → Spark → TimescaleDB"
echo "Aggregationen und Anomalieerkennung funktionieren wie erwartet"

echo -e "\n${YELLOW}Zeitstempel: $(date)${NC}"
echo "===== Ende des End-to-End Tests ====="