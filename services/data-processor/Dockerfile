# Production Dockerfile for the Data Processor service
FROM bitnami/spark:3.4.2

USER root

# Install wget to download JARs
RUN apt-get update && apt-get install -y wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Download Kafka Connector JARs
RUN mkdir -p /opt/bitnami/spark/jars && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.4.2/spark-sql-kafka-0-10_2.12-3.4.2.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.1/kafka-clients-2.8.1.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.4.2/spark-token-provider-kafka-0-10_2.12-3.4.2.jar

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create directory for shared workspace
RUN mkdir -p /opt/bitnami/spark/shared-workspace

# Set environment variables for consistent class loading
ENV SPARK_CLASSPATH="/opt/bitnami/spark/jars/*"
ENV PYTHONPATH="${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip:${PYTHONPATH}"

# Default command - running in client mode
CMD ["spark-submit", \
     "--master", "spark://spark-master:7077", \
     "--deploy-mode", "client", \
     "--conf", "spark.serializer=org.apache.spark.serializer.KryoSerializer", \
     "--conf", "spark.kryo.registrationRequired=false", \
     "--conf", "spark.kryoserializer.buffer=1024k", \
     "--conf", "spark.kryoserializer.buffer.max=1024m", \
     "--conf", "spark.executor.extraClassPath=/opt/bitnami/spark/jars/*", \
     "--conf", "spark.driver.extraClassPath=/opt/bitnami/spark/jars/*", \
     "--conf", "spark.sql.streaming.forceDeleteTempCheckpointLocation=true", \
     "--conf", "spark.driver.bindAddress=0.0.0.0", \
     "/app/app.py"]