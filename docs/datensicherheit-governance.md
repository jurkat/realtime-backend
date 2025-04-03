# Datensicherheit und Data Governance

[← Zurück zur README](../README.md)

## Implementierte Sicherheitsmaßnahmen

### Transportverschlüsselung
- TLS/SSL für externe Verbindungen
- Automatische HTTP zu HTTPS Weiterleitung
- Moderne Cipher-Suites (ECDHE-RSA-AES128-GCM-SHA256, ECDHE-RSA-AES256-GCM-SHA384)

### Zugriffskontrolle
- Basic Authentication für administrative Schnittstellen
- Separate Grafana-Authentifizierung
- Netzwerksegmentierung durch Docker-Netzwerke
- IP-basierte Zugriffsbeschränkungen für interne Metriken-Endpunkte

### Datenverarbeitung und Qualitätssicherung
- Strikte Schema-Validierung für Sensordaten
- Automatische Anomalieerkennung für:
  - Temperatur (Hohe Werte >35°C)
  - Druck (Niedrige Werte <950 hPa)
  - Spannung (Hohe Werte >240V, Niedrige Werte <220V)
- Grundlegendes Herkunfts-Tracking durch Verarbeitungszeitstempel
- Kategorisierung nach Geschäfts- und Außergeschäftszeiten (7-19 Uhr als Geschäftszeiten)

### Monitoring und Observability
- Detailliertes Logging mit Zeitstempeln und Kontextinformationen
- Prometheus Metriken für:
  - Verarbeitete Nachrichten pro Sensortyp
  - Erkannte Anomalien (Typ und Anzahl)
  - Verarbeitungszeiten (Durchschnitt, Maximum, p95)
  - Systemressourcen (CPU, RAM, Disk)
- Grafana-Dashboards für Visualisierung mit anpassbaren Grenzwerten

### Datenspeicherung
- Strukturierte Datenhaltung in TimescaleDB
- Automatische Datenkomprimierung für optimierte Speichernutzung
- Definierte Aufbewahrungsfristen:
  - Realtime Messungen: 3 Tage (unkomprimiert), danach komprimiert, Löschung nach 90 Tagen
  - Anomalien: 7 Tage (unkomprimiert), danach komprimiert, Löschung nach 365 Tagen
  - Aggregationen: 
    - Minuten-Daten: 7 Tage (unkomprimiert), danach komprimiert, Löschung nach 180 Tagen
    - 10-Minuten-Daten: 7 Tage (unkomprimiert), danach komprimiert, Löschung nach 365 Tagen
    - Stunden-Daten: 30 Tage (unkomprimiert), danach komprimiert, Löschung nach 730 Tagen

## Data Governance-Framework

### Datenmanagement
- **Datenklassifizierung**: Strukturierte Kategorisierung nach Sensortyp, Zeitraum und Relevanz
- **Datenqualität**: Kontinuierliche Überprüfung durch Schema-Validierung und Anomalieerkennung
- **Datenzugriff**: Zugriffskontrollen über Basic Authentication und Netzwerksegmentierung

### Daten-Lifecycle-Management
- **Erzeugung**: Strukturierte Erfassung mit Metadaten und Zeitstempeln
- **Verarbeitung**: Transparente Transformation mit nachvollziehbarer Anreicherung
- **Analyse**: Aggregationen und Anomalieerkennung mit klarer Methodik
- **Archivierung**: Automatische Komprimierung und Partitionierung nach Zeiträumen
- **Löschung**: Regelbasierte Datenentsorgung nach definierten Aufbewahrungsfristen

### Datenintegration
- **Datenpipeline**: Durchgängiger Datenfluss von Generator über Kafka und Spark bis TimescaleDB
- **Herkunfts-Tracking**: Nachverfolgbarkeit durch Verarbeitungszeitstempel und Metadaten
- **Konsistenz**: Einheitliche Datenmodelle und Schema-Definitionen über alle Systemkomponenten

### Technische Implementierungen
- Spark Streaming nutzt strukturierte Schemas für Datenvalidierung
- TimescaleDB implementiert automatische Partitionierung durch Hypertables
- Docker-Container isolieren Dienste für verbesserte Sicherheit und Skalierbarkeit
- Prometheus und Grafana bieten Echtzeit-Monitoring und Alarmierung
