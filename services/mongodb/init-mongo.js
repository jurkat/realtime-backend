// MongoDB Initialization Script
// Creates the required database and collections for Time Series data

// Switch to sensor_data database
db = db.getSiblingDB('sensor_data');

// Create a user for the database with appropriate permissions
db.createUser({
  user: 'mongo',
  pwd: 'password',
  roles: [
    {
      role: 'readWrite',
      db: 'sensor_data'
    }
  ]
});

// Create a Time Series Collection for real-time sensor data
// timeField: The field containing the timestamp
// metaField: The field containing metadata for grouping (in our case sensor_id)
// granularity: The granularity of the data (minutes, for better performance)
db.createCollection("realtime_measurements", {
  timeseries: {
    timeField: "timestamp",
    metaField: "sensor_id",
    granularity: "minutes"
  }
});

// Create a collection for anomalies
db.createCollection("anomalies");

// Create indexes for better performance
db.realtime_measurements.createIndex({ "sensor_id": 1, "timestamp": 1 });
db.realtime_measurements.createIndex({ "sensor_type": 1, "timestamp": 1 });
db.anomalies.createIndex({ "sensor_id": 1, "timestamp": 1 });
db.anomalies.createIndex({ "anomaly": 1, "timestamp": 1 });

// Confirmation message
print("MongoDB with Time Series collections initialized successfully!");