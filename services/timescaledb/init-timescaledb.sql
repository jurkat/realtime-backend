-- TimescaleDB Initialization Script
-- Creates the required time series tables (hypertables) for sensor data

-- Activate TimescaleDB Extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Table for realtime measurements (replacing MongoDB time series collection)
CREATE TABLE realtime_measurements (
  id SERIAL,
  sensor_id TEXT NOT NULL,
  sensor_type TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  unit TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  processed_timestamp TIMESTAMPTZ DEFAULT NOW(),
  time_diff_seconds DOUBLE PRECISION,
  day_of_week TEXT,
  hour_of_day INTEGER,
  data_category TEXT,
  anomaly TEXT,
  PRIMARY KEY (sensor_id, timestamp)
);

-- Table for anomalies (replacing MongoDB anomalies collection)
CREATE TABLE anomalies (
  id SERIAL,
  sensor_id TEXT NOT NULL,
  sensor_type TEXT NOT NULL,
  value DOUBLE PRECISION NOT NULL,
  unit TEXT NOT NULL,
  timestamp TIMESTAMPTZ NOT NULL,
  processed_timestamp TIMESTAMPTZ DEFAULT NOW(),
  anomaly TEXT NOT NULL,
  time_diff_seconds DOUBLE PRECISION,
  day_of_week TEXT,
  hour_of_day INTEGER,
  data_category TEXT,
  PRIMARY KEY (sensor_id, timestamp)
);

-- Table for sensor raw data
CREATE TABLE historical_sensor_aggregates (
  id SERIAL PRIMARY KEY,
  sensor_type TEXT NOT NULL,
  unit TEXT NOT NULL,
  avg_value DOUBLE PRECISION NOT NULL,
  max_value DOUBLE PRECISION NOT NULL,
  min_value DOUBLE PRECISION NOT NULL,
  measurement_count INTEGER NOT NULL,
  stored_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Minute aggregations
CREATE TABLE minute_sensor_aggregates (
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  sensor_type TEXT NOT NULL,
  unit TEXT NOT NULL,
  avg_value DOUBLE PRECISION NOT NULL,
  max_value DOUBLE PRECISION NOT NULL,
  min_value DOUBLE PRECISION NOT NULL,
  measurement_count INTEGER NOT NULL,
  stored_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  PRIMARY KEY (window_start, sensor_type, unit)
);

-- 10-minute aggregations
CREATE TABLE ten_minute_sensor_aggregates (
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  sensor_type TEXT NOT NULL,
  unit TEXT NOT NULL,
  avg_value DOUBLE PRECISION NOT NULL,
  max_value DOUBLE PRECISION NOT NULL,
  min_value DOUBLE PRECISION NOT NULL,
  measurement_count INTEGER NOT NULL,
  stored_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  PRIMARY KEY (window_start, sensor_type, unit)
);

-- Hourly aggregations
CREATE TABLE hourly_sensor_aggregates (
  window_start TIMESTAMPTZ NOT NULL,
  window_end TIMESTAMPTZ NOT NULL,
  sensor_type TEXT NOT NULL,
  unit TEXT NOT NULL,
  avg_value DOUBLE PRECISION NOT NULL,
  max_value DOUBLE PRECISION NOT NULL,
  min_value DOUBLE PRECISION NOT NULL,
  measurement_count INTEGER NOT NULL,
  stored_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  PRIMARY KEY (window_start, sensor_type, unit)
);

-- Convert to TimescaleDB hypertables for better time series performance
-- Realtime measurements table (partitioned by timestamp)
SELECT create_hypertable('realtime_measurements', 'timestamp');

-- Anomalies table (partitioned by timestamp)
SELECT create_hypertable('anomalies', 'timestamp');

-- Minutes table
SELECT create_hypertable('minute_sensor_aggregates', 'window_start');

-- 10-minutes table
SELECT create_hypertable('ten_minute_sensor_aggregates', 'window_start');

-- Hourly table
SELECT create_hypertable('hourly_sensor_aggregates', 'window_start');

-- Indexes for improved performance
-- Realtime measurements indexes
CREATE INDEX ON realtime_measurements (sensor_id, timestamp DESC);
CREATE INDEX ON realtime_measurements (sensor_type, timestamp DESC);
CREATE INDEX ON realtime_measurements (timestamp DESC, sensor_id);

-- Anomalies indexes
CREATE INDEX ON anomalies (sensor_id, timestamp DESC);
CREATE INDEX ON anomalies (anomaly, timestamp DESC);
CREATE INDEX ON anomalies (timestamp DESC, anomaly);

-- Aggregation indexes
CREATE INDEX ON minute_sensor_aggregates (sensor_type, window_start DESC);
CREATE INDEX ON ten_minute_sensor_aggregates (sensor_type, window_start DESC);
CREATE INDEX ON hourly_sensor_aggregates (sensor_type, window_start DESC);

-- Enable compression for older data
-- Realtime measurements compression (after 3 days)
ALTER TABLE realtime_measurements SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensor_id,sensor_type'
);

-- Anomalies compression (after 7 days)
ALTER TABLE anomalies SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensor_id,anomaly'
);

-- Aggregation tables compression (after 7 days)
ALTER TABLE minute_sensor_aggregates SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensor_type,unit'
);

ALTER TABLE ten_minute_sensor_aggregates SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensor_type,unit'
);

ALTER TABLE hourly_sensor_aggregates SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'sensor_type,unit'
);

-- Compression policies
SELECT add_compression_policy('realtime_measurements', INTERVAL '3 days');
SELECT add_compression_policy('anomalies', INTERVAL '7 days');
SELECT add_compression_policy('minute_sensor_aggregates', INTERVAL '7 days');
SELECT add_compression_policy('ten_minute_sensor_aggregates', INTERVAL '7 days');
SELECT add_compression_policy('hourly_sensor_aggregates', INTERVAL '30 days');

-- Data retention policies 
-- These policies define when data will be permanently removed from the database
-- The retention periods are set to ensure that:
-- 1. Data isn't deleted before it's been aggregated
-- 2. Aggregations remain available longer than raw data
-- 3. The Spark processor won't try to access deleted data

-- Realtime measurements retention (remove after 90 days)
SELECT add_retention_policy('realtime_measurements', INTERVAL '90 days');

-- Anomalies retention (remove after 365 days/1 year)
SELECT add_retention_policy('anomalies', INTERVAL '365 days');

-- Aggregated data retention (staged removal)
SELECT add_retention_policy('minute_sensor_aggregates', INTERVAL '180 days');  -- 6 months
SELECT add_retention_policy('ten_minute_sensor_aggregates', INTERVAL '365 days');  -- 1 year
SELECT add_retention_policy('hourly_sensor_aggregates', INTERVAL '730 days');  -- 2 years

-- Continuous Aggregates for automatic updating of aggregates
-- 10-minute aggregate from minute data
CREATE MATERIALIZED VIEW cagg_10min_view
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('10 minutes', window_start) AS bucket,
  sensor_type,
  unit,
  AVG(avg_value) AS avg_value,
  MAX(max_value) AS max_value,
  MIN(min_value) AS min_value,
  SUM(measurement_count) AS total_measurements
FROM minute_sensor_aggregates
GROUP BY bucket, sensor_type, unit;

-- Hourly aggregate from 10-minute data
CREATE MATERIALIZED VIEW cagg_hourly_view
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', bucket) AS bucket,
  sensor_type,
  unit,
  AVG(avg_value) AS avg_value,
  MAX(max_value) AS max_value,
  MIN(min_value) AS min_value,
  SUM(total_measurements) AS total_measurements
FROM cagg_10min_view
GROUP BY time_bucket('1 hour', bucket), sensor_type, unit;

-- Policies for continuous aggregation
SELECT add_continuous_aggregate_policy('cagg_10min_view',
  start_offset => INTERVAL '1 day',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');

SELECT add_continuous_aggregate_policy('cagg_hourly_view',
  start_offset => INTERVAL '7 days',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');

-- Access rights for postgres user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;