-- TimescaleDB Initialization Script
-- Creates the required time series tables (hypertables) for sensor data

-- Activate TimescaleDB Extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

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
-- Minutes table
SELECT create_hypertable('minute_sensor_aggregates', 'window_start');

-- 10-minutes table
SELECT create_hypertable('ten_minute_sensor_aggregates', 'window_start');

-- Hourly table
SELECT create_hypertable('hourly_sensor_aggregates', 'window_start');

-- Indexes for improved performance
CREATE INDEX ON minute_sensor_aggregates (sensor_type, window_start DESC);
CREATE INDEX ON ten_minute_sensor_aggregates (sensor_type, window_start DESC);
CREATE INDEX ON hourly_sensor_aggregates (sensor_type, window_start DESC);

-- Enable compression for older data (after 7 days)
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

-- Compression policies (compress after 7 days)
SELECT add_compression_policy('minute_sensor_aggregates', INTERVAL '7 days');
SELECT add_compression_policy('ten_minute_sensor_aggregates', INTERVAL '7 days');
SELECT add_compression_policy('hourly_sensor_aggregates', INTERVAL '30 days');

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