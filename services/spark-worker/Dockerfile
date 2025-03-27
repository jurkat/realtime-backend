# Custom Spark Worker Dockerfile to ensure compatibility with data-processor
FROM bitnami/spark:3.4.2

USER root

# Install wget to download JARs
RUN apt-get update && apt-get install -y wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Download the same Kafka Connector JARs as in data-processor
RUN mkdir -p /opt/bitnami/spark/jars && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.4.2/spark-sql-kafka-0-10_2.12-3.4.2.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/2.8.1/kafka-clients-2.8.1.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar && \
    wget -P /opt/bitnami/spark/jars https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.4.2/spark-token-provider-kafka-0-10_2.12-3.4.2.jar

# Create directory for shared workspace
RUN mkdir -p /opt/bitnami/spark/shared-workspace

# Set environment variables for consistent class loading
ENV SPARK_CLASSPATH="/opt/bitnami/spark/jars/*"
ENV PYTHONPATH="${SPARK_HOME}/python:${SPARK_HOME}/python/lib/py4j-0.10.9.7-src.zip:${PYTHONPATH}"

# Set Spark serializer to KryoSerializer for better compatibility and worker properties
ENV SPARK_WORKER_OPTS="-Dspark.serializer=org.apache.spark.serializer.KryoSerializer -Dspark.kryo.registrationRequired=false"

# Default to worker mode with a small customization to include our configurations
CMD ["bash", "-c", "cd /opt/bitnami/spark && bin/spark-class org.apache.spark.deploy.worker.Worker spark://spark-master:7077"]