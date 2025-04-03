#!/bin/bash

# Skript zum Starten der Debug-Umgebung ohne Monitoring

# Stoppe alle laufenden Container und entferne Volumes
./stop-all.sh

# Starte die Basis-Services mit der Override-Datei für Debug-Einstellungen
echo "Starte die Debug-Umgebung..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

echo "Debug-Umgebung wurde gestartet. Zugriff über:"
echo "- Nginx Gateway: http://localhost"
echo "- Grafana: http://metrics.localhost"
echo "- Spark Master: http://spark.localhost"
echo "- Spark Worker 1: http://worker-1.localhost"
echo "- Spark Worker 2: http://worker-2.localhost"
echo "- Spark Worker 3: http://worker-3.localhost"
echo "- Data Processor: http://processor.localhost"
echo "- Kafka UI: http://kafka.localhost"
echo "- Debug Ports: 5678 (Data Generator), 5679 (Data Processor)"
