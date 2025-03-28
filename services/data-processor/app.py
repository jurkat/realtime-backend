import logging
import sys
import json
import os
from datetime import datetime, timedelta
import time
import psycopg2
import psycopg2.extras
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import from_json, col, window, avg, max, min, count, sum, expr, current_timestamp, to_timestamp, lit
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from pyspark.sql.streaming import StreamingQuery

# Log level from environment variable or default (ERROR)
log_level_name = os.getenv('LOG_LEVEL', 'ERROR')
log_level = getattr(logging, log_level_name, logging.ERROR)

# Basic logging configuration for console output
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("data-processor")

# Define schema for sensor data
schema = StructType([
    StructField("sensor_id", StringType(), True),
    StructField("sensor_type", StringType(), True),
    StructField("value", DoubleType(), True),
    StructField("unit", StringType(), True),
    StructField("timestamp", TimestampType(), True)
])

# Database connection settings (from environment variables with defaults)
POSTGRES_URI = os.getenv('POSTGRES_URI', 'postgresql://postgres:password@timescaledb:5432/sensor_data')

# PostgreSQL Constants
POSTGRES_TABLE_REALTIME = "realtime_measurements"
POSTGRES_TABLE_ANOMALIES = "anomalies"
POSTGRES_TABLE_RAW = "historical_sensor_aggregates"
POSTGRES_TABLE_MINUTE = "minute_sensor_aggregates"
POSTGRES_TABLE_10MIN = "ten_minute_sensor_aggregates"
POSTGRES_TABLE_HOURLY = "hourly_sensor_aggregates"

# Processing parameters
WINDOW_DURATION = os.getenv("WINDOW_DURATION", "5 minutes")
SLIDING_DURATION = os.getenv("SLIDING_DURATION", "1 minute")
CHECKPOINT_LOCATION = "/opt/spark/checkpoints"

# Define thresholds for alerts
TEMPERATURE_HIGH_THRESHOLD = 35.0
PRESSURE_LOW_THRESHOLD = 950.0
VOLTAGE_LOW_THRESHOLD = 220.0
VOLTAGE_HIGH_THRESHOLD = 240.0

# PostgreSQL Connection (lazy initialization)
postgres_conn = None

def get_postgres_connection():
    """Get or create a PostgreSQL connection."""
    global postgres_conn

    if postgres_conn is None or postgres_conn.closed:
        # Extract connection parameters from URI
        db_uri = POSTGRES_URI.replace("postgresql://", "")
        user_pass, host_port_db = db_uri.split("@")

        if ":" in user_pass:
            user, password = user_pass.split(":")
        else:
            user = user_pass
            password = ""

        host_port, db_name = host_port_db.split("/")

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 5432  # Default PostgreSQL port

        # Max retries for PostgreSQL connection
        max_retries = 5
        retry_delay = 5  # seconds

        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to PostgreSQL (attempt {attempt+1}/{max_retries}): {host}:{port}/{db_name}")
                postgres_conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    dbname=db_name
                )
                postgres_conn.autocommit = True  # Auto commit each operation
                logger.info("Successfully connected to PostgreSQL")
                break

            except Exception as e:
                logger.error(f"Failed to connect to PostgreSQL (attempt {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    logger.error("Maximum retries reached. Could not connect to PostgreSQL.")
                    raise

    return postgres_conn

def write_realtime_data_to_postgres(batch_df, batch_id):
    """Write realtime data to PostgreSQL/TimescaleDB."""
    try:
        # Convert batch DataFrame to records
        records = [row.asDict() for row in batch_df.collect()]

        if records:
            # Get PostgreSQL connection
            conn = get_postgres_connection()
            cursor = conn.cursor()

            # Insert records into realtime_measurements table
            for record in records:
                # Handle datetime objects
                timestamp = record["timestamp"] if isinstance(record["timestamp"], datetime) else datetime.fromisoformat(record["timestamp"])
                processed_timestamp = record.get("processed_timestamp", datetime.now())
                if not isinstance(processed_timestamp, datetime):
                    processed_timestamp = datetime.fromisoformat(processed_timestamp)

                # Use UPSERT pattern (INSERT ON CONFLICT DO UPDATE)
                cursor.execute(
                    f"""
                    INSERT INTO {POSTGRES_TABLE_REALTIME}
                    (sensor_id, sensor_type, value, unit, timestamp, processed_timestamp,
                     time_diff_seconds, day_of_week, hour_of_day, data_category, anomaly)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (sensor_id, timestamp)
                    DO UPDATE SET
                        processed_timestamp = EXCLUDED.processed_timestamp,
                        time_diff_seconds = EXCLUDED.time_diff_seconds,
                        day_of_week = EXCLUDED.day_of_week,
                        hour_of_day = EXCLUDED.hour_of_day,
                        data_category = EXCLUDED.data_category,
                        anomaly = EXCLUDED.anomaly
                    """,
                    (
                        record["sensor_id"],
                        record["sensor_type"],
                        record["value"],
                        record["unit"],
                        timestamp,
                        processed_timestamp,
                        record.get("time_diff_seconds"),
                        record.get("day_of_week"),
                        record.get("hour_of_day"),
                        record.get("data_category"),
                        record.get("anomaly", "Normal")
                    )
                )

                # If it's an anomaly, also insert into anomalies table
                if record.get("anomaly") and record.get("anomaly") != "Normal":
                    cursor.execute(
                        f"""
                        INSERT INTO {POSTGRES_TABLE_ANOMALIES}
                        (sensor_id, sensor_type, value, unit, timestamp, processed_timestamp,
                         anomaly, time_diff_seconds, day_of_week, hour_of_day, data_category)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sensor_id, timestamp)
                        DO UPDATE SET
                            processed_timestamp = EXCLUDED.processed_timestamp,
                            anomaly = EXCLUDED.anomaly
                        """,
                        (
                            record["sensor_id"],
                            record["sensor_type"],
                            record["value"],
                            record["unit"],
                            timestamp,
                            processed_timestamp,
                            record["anomaly"],
                            record.get("time_diff_seconds"),
                            record.get("day_of_week"),
                            record.get("hour_of_day"),
                            record.get("data_category")
                        )
                    )

            conn.commit()
            logger.info(f"Batch {batch_id}: Successfully wrote {len(records)} records to TimescaleDB realtime tables")

    except Exception as e:
        logger.error(f"Batch {batch_id}: Error writing to TimescaleDB realtime tables: {str(e)}", exc_info=True)

def write_to_postgres(batch_df, batch_id, table_name):
    """Write data to PostgreSQL/TimescaleDB."""
    try:
        # Convert batch DataFrame to records
        records = [row.asDict() for row in batch_df.collect()]

        if records:
            # Get PostgreSQL connection
            conn = get_postgres_connection()
            cursor = conn.cursor()

            # Insert records based on table type
            if table_name == POSTGRES_TABLE_RAW:
                # RAW table has a different structure (with SERIAL id as primary key)
                for record in records:
                    cursor.execute(
                        f"""
                        INSERT INTO {table_name}
                        (sensor_type, unit, avg_value, max_value, min_value, measurement_count, stored_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            record["sensor_type"],
                            record["unit"],
                            record["avg_value"],
                            record["max_value"],
                            record["min_value"],
                            record["measurement_count"],
                            datetime.now()
                        )
                    )
            else:
                # Time window tables (minute, 10-minute, hourly)
                for record in records:
                    # Convert strings to datetime objects if needed
                    window_start = record["window_start"] if isinstance(record["window_start"], datetime) else datetime.fromisoformat(record["window_start"])
                    window_end = record["window_end"] if isinstance(record["window_end"], datetime) else datetime.fromisoformat(record["window_end"])

                    # Use UPSERT pattern (INSERT ON CONFLICT DO UPDATE)
                    cursor.execute(
                        f"""
                        INSERT INTO {table_name}
                        (window_start, window_end, sensor_type, unit, avg_value, max_value, min_value,
                         measurement_count, stored_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (window_start, sensor_type, unit)
                        DO UPDATE SET
                            window_end = EXCLUDED.window_end,
                            avg_value = (({table_name}.avg_value * {table_name}.measurement_count) +
                                        (EXCLUDED.avg_value * EXCLUDED.measurement_count)) /
                                        ({table_name}.measurement_count + EXCLUDED.measurement_count),
                            max_value = GREATEST({table_name}.max_value, EXCLUDED.max_value),
                            min_value = LEAST({table_name}.min_value, EXCLUDED.min_value),
                            measurement_count = {table_name}.measurement_count + EXCLUDED.measurement_count,
                            stored_at = NOW()
                        """,
                        (
                            window_start,
                            window_end,
                            record["sensor_type"],
                            record["unit"],
                            record["avg_value"],
                            record["max_value"],
                            record["min_value"],
                            record["measurement_count"],
                            datetime.now()
                        )
                    )

            conn.commit()
            logger.info(f"Batch {batch_id}: Successfully wrote {len(records)} records to {table_name}")

    except Exception as e:
        logger.error(f"Batch {batch_id}: Error writing to PostgreSQL (table: {table_name}): {str(e)}", exc_info=True)

def detect_anomalies(df: DataFrame) -> DataFrame:
    """Detect anomalies in sensor data based on thresholds."""
    return df.withColumn(
        "anomaly",
        expr(f"""
            CASE
                WHEN sensor_type = 'temperature' AND value > {TEMPERATURE_HIGH_THRESHOLD} THEN 'High Temperature'
                WHEN sensor_type = 'pressure' AND value < {PRESSURE_LOW_THRESHOLD} THEN 'Low Pressure'
                WHEN sensor_type = 'voltage' AND value < {VOLTAGE_LOW_THRESHOLD} THEN 'Low Voltage'
                WHEN sensor_type = 'voltage' AND value > {VOLTAGE_HIGH_THRESHOLD} THEN 'High Voltage'
                ELSE 'Normal'
            END
        """)
    ).withColumn(
        "severity",
        expr("""
            CASE
                WHEN anomaly = 'Normal' THEN 0
                WHEN anomaly LIKE '%Temperature%' THEN 3
                ELSE 2
            END
        """)
    )

def enrich_data(df: DataFrame) -> DataFrame:
    """Enrich the data with additional information."""
    return df \
        .withColumn("processed_timestamp", current_timestamp()) \
        .withColumn("time_diff_seconds",
                  expr("CAST(UNIX_TIMESTAMP(processed_timestamp) - UNIX_TIMESTAMP(timestamp) AS DOUBLE)")) \
        .withColumn("day_of_week", expr("date_format(timestamp, 'EEEE')")) \
        .withColumn("hour_of_day", expr("hour(timestamp)")) \
        .withColumn("data_category", expr("""
            CASE
                WHEN hour_of_day BETWEEN 7 AND 19 THEN 'Business Hours'
                ELSE 'Off Hours'
            END
        """))

def process_batch(batch_df, batch_id):
    """Process a batch of data and write to TimescaleDB."""
    try:
        # Apply enrichment and anomaly detection
        enriched_df = enrich_data(batch_df)
        anomaly_df = detect_anomalies(enriched_df)

        # Debug: Log information about what's getting processed
        logger.info(f"Batch {batch_id}: Original count: {batch_df.count()}, Enriched: {enriched_df.count()}, Anomaly records: {anomaly_df.filter(col('anomaly') != 'Normal').count()}")

        # Write ALL processed data to TimescaleDB realtime tables
        write_realtime_data_to_postgres(anomaly_df, batch_id)

        # Calculate raw aggregates (basic aggregation by sensor type and unit)
        raw_agg_df = enriched_df \
            .groupBy(
                "sensor_type",
                "unit"
            ) \
            .agg(
                avg("value").alias("avg_value"),
                max("value").alias("max_value"),
                min("value").alias("min_value"),
                count("value").alias("measurement_count")
            )

        # Write raw aggregates to PostgreSQL/TimescaleDB
        write_to_postgres(raw_agg_df, batch_id, POSTGRES_TABLE_RAW)

        # Calculate minute aggregates
        minute_df = enriched_df \
            .groupBy(
                window("timestamp", "1 minute"),
                "sensor_type",
                "unit"
            ) \
            .agg(
                avg("value").alias("avg_value"),
                max("value").alias("max_value"),
                min("value").alias("min_value"),
                count("value").alias("measurement_count")
            ) \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("sensor_type"),
                col("unit"),
                col("avg_value"),
                col("max_value"),
                col("min_value"),
                col("measurement_count")
            )

        # Write minute aggregates to PostgreSQL/TimescaleDB
        write_to_postgres(minute_df, batch_id, POSTGRES_TABLE_MINUTE)

        # Calculate 10-minute aggregates
        ten_min_df = enriched_df \
            .groupBy(
                window("timestamp", "10 minutes"),
                "sensor_type",
                "unit"
            ) \
            .agg(
                avg("value").alias("avg_value"),
                max("value").alias("max_value"),
                min("value").alias("min_value"),
                count("value").alias("measurement_count")
            ) \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("sensor_type"),
                col("unit"),
                col("avg_value"),
                col("max_value"),
                col("min_value"),
                col("measurement_count")
            )

        # Write 10-minute aggregates to PostgreSQL/TimescaleDB
        write_to_postgres(ten_min_df, batch_id, POSTGRES_TABLE_10MIN)

        # Calculate hourly aggregates
        hourly_df = enriched_df \
            .groupBy(
                window("timestamp", "1 hour"),
                "sensor_type",
                "unit"
            ) \
            .agg(
                avg("value").alias("avg_value"),
                max("value").alias("max_value"),
                min("value").alias("min_value"),
                count("value").alias("measurement_count")
            ) \
            .select(
                col("window.start").alias("window_start"),
                col("window.end").alias("window_end"),
                col("sensor_type"),
                col("unit"),
                col("avg_value"),
                col("max_value"),
                col("min_value"),
                col("measurement_count")
            )

        # Write hourly aggregates to PostgreSQL/TimescaleDB
        write_to_postgres(hourly_df, batch_id, POSTGRES_TABLE_HOURLY)

        # Show anomalies if any exist
        anomalies = anomaly_df.filter(col('anomaly') != 'Normal')
        if anomalies.count() > 0:
            logger.warning(f"Batch {batch_id}: Found {anomalies.count()} anomalies")
            anomalies.show(5, truncate=False)

    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {str(e)}", exc_info=True)

def main():
    logger.info("Starting Enhanced Data Processor application with database integration")
    try:
        # Create Spark session
        logger.info("Creating Spark session with database configurations")
        spark = SparkSession.builder \
            .appName("EnhancedDataProcessor") \
            .master("local[*]") \
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer") \
            .config("spark.kryo.registrationRequired", "false") \
            .config("spark.kryoserializer.buffer", "1024k") \
            .config("spark.kryoserializer.buffer.max", "1024m") \
            .config("spark.executor.extraJavaOptions", "-XX:+UseG1GC") \
            .config("spark.driver.extraJavaOptions", "-XX:+UseG1GC") \
            .config("spark.executor.extraClassPath", "/opt/bitnami/spark/jars/*") \
            .config("spark.driver.extraClassPath", "/opt/bitnami/spark/jars/*") \
            .config("spark.sql.shuffle.partitions", "1") \
            .config("spark.default.parallelism", "1") \
            .config("spark.submit.deployMode", "client") \
            .config("spark.driver.bindAddress", "0.0.0.0") \
            .config("spark.io.compression.codec", "lz4") \
            .config("spark.rdd.compress", "true") \
            .config("spark.streaming.stopGracefullyOnShutdown", "true") \
            .config("spark.sql.streaming.schemaInference", "true") \
            .getOrCreate()

        # Test database connection
        try:
            logger.info("Testing PostgreSQL connection...")
            conn = get_postgres_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()
                logger.info(f"PostgreSQL version: {version[0]}")

        except Exception as db_error:
            logger.error(f"Error connecting to database: {str(db_error)}")
            # Continue anyway, as Kafka processing can start and database connections can be retried

        # Log Spark version and configurations
        logger.info(f"Spark version: {spark.version}")

        # Use IP address instead of hostname for Kafka
        # Test different methods to connect to Kafka
        kafka_servers = ["kafka:9092", "host.docker.internal:9092", "localhost:9092"]

        connected = False
        kafka_bootstrap_servers = None
        kafka_topic = "sensor-data"

        for server in kafka_servers:
            try:
                logger.info(f"Attempting to connect to Kafka at {server}")
                # Test connection by creating a temporary consumer
                df_test = spark.readStream \
                    .format("kafka") \
                    .option("kafka.bootstrap.servers", server) \
                    .option("subscribe", "dummy-topic") \
                    .option("failOnDataLoss", "false") \
                    .option("startingOffsets", "latest") \

                # If we reach here without error, connection is possible
                kafka_bootstrap_servers = server
                connected = True
                logger.info(f"Successfully connected to Kafka at {server}")
                break
            except Exception as e:
                logger.warning(f"Failed to connect to Kafka at {server}: {str(e)}")
                continue

        if not connected:
            # Fallback: Try direct connection to Docker's default gateway
            try:
                import socket
                # Try to get Docker's default gateway IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                host_ip = s.getsockname()[0]
                s.close()
                logger.info(f"Using host IP for connection: {host_ip}")
                kafka_bootstrap_servers = f"{host_ip}:9092"
            except Exception:
                # Last resort: use the Docker network address
                kafka_bootstrap_servers = "172.18.0.4:9092"  # Common Docker network address
                logger.warning(f"Falling back to hardcoded Kafka address: {kafka_bootstrap_servers}")

        logger.info(f"Connecting to Kafka at {kafka_bootstrap_servers}, topic: {kafka_topic}")

        # Create streaming DataFrame from Kafka
        df = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", kafka_bootstrap_servers) \
            .option("subscribe", kafka_topic) \
            .option("failOnDataLoss", "false") \
            .option("startingOffsets", "latest") \
            .load()

        logger.info("Successfully created streaming DataFrame from Kafka")

        # Parse JSON from value column
        parsed_df = df.selectExpr("CAST(value AS STRING) as message") \
            .select(from_json(col("message"), schema).alias("data")) \
            .select("data.*")

        # Use foreachBatch to process data in a batch-wise manner
        query = parsed_df.writeStream \
            .foreachBatch(process_batch) \
            .option("checkpointLocation", CHECKPOINT_LOCATION) \
            .start()

        logger.info("Streaming query started with database integration")
        logger.info("================================================================================")
        logger.info("Streaming data to TimescaleDB...")
        logger.info("================================================================================")

        query.awaitTermination()

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        raise
    finally:
        # Close database connections
        if 'postgres_conn' in globals() and postgres_conn and not postgres_conn.closed:
            postgres_conn.close()
            logger.info("PostgreSQL connection closed")

if __name__ == "__main__":
    # Reduce logging verbosity from internal Spark logging
    logging.getLogger("py4j").setLevel(logging.ERROR)
    logging.getLogger("org").setLevel(logging.ERROR)
    logging.getLogger("org.apache.spark").setLevel(logging.ERROR)
    main()