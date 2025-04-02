#!/bin/bash

# Skript zum Starten der Produktionsumgebung mit Monitoring

# Stoppe alle laufenden Container und entferne Volumes
./stop-all.sh

# Starte die Basis-Services und Monitoring-Services
echo "Starte die Produktionsumgebung mit Monitoring..."
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d --build

echo "Produktionsumgebung wurde gestartet."
echo "Alle Services sind über den Nginx Gateway erreichbar:"
echo "- Hauptzugang: http://localhost oder https://localhost"
echo "- Spark Master UI: https://spark.localhost"
echo "- Spark Worker UIs: https://worker-1.localhost, https://worker-2.localhost, https://worker-3.localhost"
echo "- Data Processor UI: https://processor.localhost"
echo "- Kafka UI: https://kafka.localhost"
echo "- Grafana: https://metrics.localhost"
echo "- Prometheus: https://prometheus.localhost"
