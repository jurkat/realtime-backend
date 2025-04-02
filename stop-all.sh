#!/bin/bash

# Skript zum Stoppen aller Docker-Compose-Umgebungen

echo "Stoppe alle laufenden Container und entferne Volumes..."

# Stoppe die Produktionsumgebung
echo "Stoppe Produktionsumgebung..."
docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down -v

# Stoppe die Debug-Umgebung
echo "Stoppe Debug-Umgebung..."
docker compose -f docker-compose.yml -f docker-compose.override.yml down -v

echo "Alle Container wurden gestoppt und Volumes entfernt."
