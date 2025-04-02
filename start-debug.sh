#!/bin/bash

# Skript zum Starten der Debug-Umgebung ohne Monitoring

# Stoppe alle laufenden Container und entferne Volumes
./stop-all.sh

# Starte die Basis-Services mit der Override-Datei für Debug-Einstellungen
echo "Starte die Debug-Umgebung..."
docker compose -f docker-compose.yml -f docker-compose.override.yml up -d --build

echo "Debug-Umgebung wurde gestartet. Zugriff über:"
echo "- Nginx Gateway: http://localhost:8000"
echo "- Spark Master UI: http://localhost:8090"
echo "- Spark Worker UIs: http://localhost:8091, http://localhost:8092, http://localhost:8093"
echo "- Data Processor UI: http://localhost:4040"
echo "- Kafka UI: http://localhost:8080"
echo "- Debug Ports: 5678 (Data Generator), 5679 (Data Processor)"
