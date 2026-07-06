"""
producer.py
-----------
PURPOSE
Reads the water-leak sensor CSV row by row and streams each row as a JSON
event into the Kafka topic `urban-sensor-events`. This simulates a live
city sensor network for the rest of the pipeline to consume.

CSV COLUMN NOTES
The actual CSV columns are:
  Timestamp, Sensor_ID, Pressure (bar), Flow Rate (L/s),
  Temperature (°C), Leak Status, Burst Status

There is no "Pipe Section" or "Anomaly Score" column, so we derive them:
  - pipe_section : mapped from sensor number  (S001 → Zone-A, S010 → Zone-J)
  - anomaly_score: 1.0 if leak OR burst, 0.0 otherwise (simple heuristic)
  - sensor_id    : read from "Sensor_ID" (underscore, not space)

RUN
cd data-producer
py producer.py
(run this from inside data-producer/, since the CSV path below is relative)
"""

import csv
import json
import time
from kafka import KafkaProducer

# Map the sensor number (1-10) to a zone label so the pipeline has
# meaningful grouping keys instead of an empty string.
_SENSOR_ZONE: dict[str, str] = {
    "S001": "Zone-A", "S002": "Zone-B", "S003": "Zone-C",
    "S004": "Zone-D", "S005": "Zone-E", "S006": "Zone-F",
    "S007": "Zone-G", "S008": "Zone-H", "S009": "Zone-I",
    "S010": "Zone-J",
}


def _derive_zone(sensor_id: str) -> str:
    """Return the zone label for a sensor, with a safe fallback."""
    return _SENSOR_ZONE.get(sensor_id, f"Zone-{sensor_id}")


producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

csv_file_path = '../data/water_leak_detection_1000_rows.csv'
topic_name = 'urban-sensor-events'

print(f"Starting to stream sensor logs to Kafka topic: {topic_name}...")

try:
    with open(csv_file_path, mode='r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            sensor_id  = row.get("Sensor_ID", "")
            leak_status  = int(row.get("Leak Status", 0))
            burst_status = int(row.get("Burst Status", 0))

            # anomaly_score is set to 0.0 (neutral placeholder) -- risk_scoring.py
            # no longer uses it so that validating the formula against burst_status
            # labels is a genuine predictive test, not a circular one.
            anomaly_score = 0.0

            payload = {
                "timestamp":    row.get("Timestamp", ""),
                "sensor_id":    sensor_id,
                "pipe_section": _derive_zone(sensor_id),
                "pressure":     float(row.get("Pressure (bar)", 0.0)),
                "flow_rate":    float(row.get("Flow Rate (L/s)", 0.0)),
                "temperature":  float(row.get("Temperature (°C)", 0.0)),
                "leak_status":  leak_status,
                "burst_status": burst_status,
                "anomaly_score": anomaly_score,
            }

            producer.send(topic_name, value=payload)

            status = "BURST" if burst_status == 1 else ("LEAK" if leak_status == 1 else "NORMAL")
            print(f"Sent: {payload['pipe_section']} | Sensor: {sensor_id} "
                  f"| Pressure: {payload['pressure']:.2f} bar | {status}")

            time.sleep(0.5)

except FileNotFoundError:
    print(f"Error: Could not find {csv_file_path}. Make sure it is in the /data folder.")
except Exception as e:
    print(f"An error occurred: {e}")

