import logging
import sys
import json
import os
from datetime import datetime, timedelta

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

# File paths for simulating database storage
MONGO_DATA_FILE = "/opt/bitnami/spark/shared-workspace/mongo_realtime_data.txt"
POSTGRES_DATA_FILE = "/opt/bitnami/spark/shared-workspace/postgres_historical_data.txt"

# Database structure simulation
MONGO_COLLECTION = "realtime_measurements"
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

def clear_data_files():
    """Clear existing data files on startup."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(MONGO_DATA_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(POSTGRES_DATA_FILE), exist_ok=True)
        
        # Clear MongoDB simulation file
        with open(MONGO_DATA_FILE, "w") as f:
            f.write("")  # Write empty string to clear the file
        
        # Clear PostgreSQL simulation file
        with open(POSTGRES_DATA_FILE, "w") as f:
            f.write("")  # Write empty string to clear the file
        
        logger.info("Data files cleared on startup")
    except Exception as e:
        logger.error(f"Error clearing data files: {str(e)}", exc_info=True)

def write_to_mongo_file(batch_df, batch_id):
    """Write a batch of data to a text file simulating MongoDB for real-time data."""
    try:
        # Convert batch DataFrame to JSON format
        mongo_documents = [row.asDict() for row in batch_df.collect()]
        if mongo_documents:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(MONGO_DATA_FILE), exist_ok=True)
            
            # Append to MongoDB simulation file
            with open(MONGO_DATA_FILE, "a") as f:
                for doc in mongo_documents:
                    # Convert timestamps to strings for JSON serialization
                    if "timestamp" in doc and doc["timestamp"] is not None:
                        doc["timestamp"] = doc["timestamp"].isoformat() if hasattr(doc["timestamp"], "isoformat") else str(doc["timestamp"])
                    
                    if "processed_timestamp" in doc and doc["processed_timestamp"] is not None:
                        doc["processed_timestamp"] = doc["processed_timestamp"].isoformat() if hasattr(doc["processed_timestamp"], "isoformat") else str(doc["processed_timestamp"])
                    
                    # Add processing timestamp as string
                    doc["processing_time"] = datetime.now().isoformat()
                    
                    # Add collection information and write JSON document
                    collection_doc = {"collection": MONGO_COLLECTION, "data": doc}
                    f.write(json.dumps(collection_doc) + "\n")
                    
            logger.info(f"Batch {batch_id}: Successfully wrote {len(mongo_documents)} documents to MongoDB simulation file")
    except Exception as e:
        logger.error(f"Batch {batch_id}: Error writing to MongoDB simulation file: {str(e)}", exc_info=True)

def write_to_postgres_file(batch_df, batch_id, table_name=POSTGRES_TABLE_RAW):
    """Write a batch of data to a text file simulating PostgreSQL for historical data."""
    try:
        # Convert batch DataFrame to records
        postgres_records = [row.asDict() for row in batch_df.collect()]
        if postgres_records:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(POSTGRES_DATA_FILE), exist_ok=True)
            
            # Append to PostgreSQL simulation file
            with open(POSTGRES_DATA_FILE, "a") as f:
                for record in postgres_records:
                    # Add processing timestamp
                    record["stored_at"] = datetime.now().isoformat()
                    
                    # Convert datetime objects to ISO format strings for JSON serialization
                    for key, value in record.items():
                        if isinstance(value, datetime):
                            record[key] = value.isoformat()
                    
                    # Format: TABLE_NAME: {JSON data}
                    # This puts the table name directly as prefix text before the JSON
                    f.write(f"{table_name}: {json.dumps(record)}\n")
                    
            logger.info(f"Batch {batch_id}: Successfully wrote {len(postgres_records)} records to {table_name} table")
    except Exception as e:
        logger.error(f"Batch {batch_id}: Error writing to PostgreSQL simulation file (table: {table_name}): {str(e)}", exc_info=True)

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
    """Process a batch of data and write to both MongoDB and PostgreSQL simulation files."""
    try:
        # Apply enrichment and anomaly detection
        enriched_df = enrich_data(batch_df)
        anomaly_df = detect_anomalies(enriched_df)
        
        # Debug: Log information about what's getting processed
        logger.info(f"Batch {batch_id}: Original count: {batch_df.count()}, Enriched: {enriched_df.count()}, Anomaly records: {anomaly_df.filter(col('anomaly') != 'Normal').count()}")
        
        # Write ALL processed data to MongoDB simulation, not just anomalies
        write_to_mongo_file(anomaly_df, batch_id)
        
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
            
        # Write raw aggregates to PostgreSQL simulation
        write_to_postgres_file(raw_agg_df, batch_id, POSTGRES_TABLE_RAW)
        
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
        
        # Write minute aggregates to PostgreSQL simulation
        write_to_postgres_file(minute_df, batch_id, POSTGRES_TABLE_MINUTE)
        
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
        
        # Write 10-minute aggregates to PostgreSQL simulation
        write_to_postgres_file(ten_min_df, batch_id, POSTGRES_TABLE_10MIN)
        
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
        
        # Write hourly aggregates to PostgreSQL simulation
        write_to_postgres_file(hourly_df, batch_id, POSTGRES_TABLE_HOURLY)
        
        # Print some data to console for debugging
        logger.info(f"Batch {batch_id}: Processed {batch_df.count()} records")
        
        # Show anomalies if any exist
        anomalies = anomaly_df.filter(col('anomaly') != 'Normal')
        if anomalies.count() > 0:
            logger.warning(f"Batch {batch_id}: Found {anomalies.count()} anomalies")
            anomalies.show(5, truncate=False)
        
    except Exception as e:
        logger.error(f"Error processing batch {batch_id}: {str(e)}", exc_info=True)

def main():
    logger.info("Starting Enhanced Data Processor application")
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
        
        # Clear data files on startup
        clear_data_files()
        
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
        # This avoids serialization issues with multiple streaming queries
        query = parsed_df.writeStream \
            .foreachBatch(process_batch) \
            .option("checkpointLocation", CHECKPOINT_LOCATION) \
            .start()
        
        logger.info("Streaming query started")
        
        # Wait for streaming query to terminate
        logger.info("================================================================================")
        logger.info("Streaming Results:")
        logger.info("================================================================================")
        
        query.awaitTermination()
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # Reduce logging verbosity from internal Spark logging
    logging.getLogger("py4j").setLevel(logging.ERROR)
    logging.getLogger("org").setLevel(logging.ERROR)
    logging.getLogger("org.apache.spark").setLevel(logging.ERROR)
    main()