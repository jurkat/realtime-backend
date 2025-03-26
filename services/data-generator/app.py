from confluent_kafka import Producer
import json
import random
import time
import os
from datetime import datetime

# Configuration from environment variables
GENERATION_INTERVAL = int(os.getenv('GENERATION_INTERVAL', 1))  # Interval between data generation in seconds
KAFKA_BROKER = os.getenv('KAFKA_BROKER', 'localhost:9092')  # Kafka broker address
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'sensor-data')  # Kafka topic to send sensor data

# Sensor configuration
SENSOR_IDS = [f"sensor-{i:03d}" for i in range(1, 11)]
SENSOR_TYPES = ["temperature", "pressure", "voltage"]

# Kafka Producer Configuration
producer = Producer({'bootstrap.servers': KAFKA_BROKER})

def delivery_report(err, msg):
    """Callback for Kafka delivery reports"""
    if err is not None:
        print(f"Delivery failed for record {msg.key()}: {err}")
    else:
        print(f"Record successfully produced to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")

def generate_sensor_data():
    """Generate simulated sensor data"""
    sensor_id = random.choice(SENSOR_IDS)
    sensor_type = random.choice(SENSOR_TYPES)
    
    # Value ranges for different sensor types
    if sensor_type == "temperature":
        value = round(random.uniform(10.0, 40.0), 2)
        unit = "°C"
    elif sensor_type == "pressure":
        value = round(random.uniform(900.0, 1100.0), 2)
        unit = "hPa"
    else:  # voltage
        value = round(random.uniform(215.0, 245.0), 2)
        unit = "V"
    
    timestamp = datetime.now().isoformat()
    
    return {
        "sensor_id": sensor_id,
        "sensor_type": sensor_type,
        "value": value,
        "unit": unit,
        "timestamp": timestamp
    }

def main():
    """Main function to generate sensor data and send it to Kafka."""
    print("Data generator started. Press Ctrl+C to stop.")
    
    while True:
        try:
            # Generate sensor data
            sensor_data = generate_sensor_data()
            print(f"Generated data: {sensor_data}")
            
            # Send data to Kafka
            producer.produce(
                KAFKA_TOPIC,
                key=sensor_data["sensor_id"],
                value=json.dumps(sensor_data),
                callback=delivery_report
            )
            producer.flush()  # Ensure the message is sent
            
            # Wait for next interval
            time.sleep(GENERATION_INTERVAL)
        
        except KeyboardInterrupt:
            print("\nStopping generator.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)  # Short pause before retry

if __name__ == "__main__":
    main()
