from fastapi import FastAPI
from satellite_config import main as simulate_and_log
import pymysql
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import os 
import ssl
from dotenv import load_dotenv
from prometheus_fastapi_instrumentator import Instrumentator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter

load_dotenv()

app = FastAPI()
#PROMETHEUS SETUP
instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)
#JAEGER:
provider = TracerProvider(
    resource=Resource.create({"service.name": "fleetcast"})
)
trace.set_tracer_provider(provider)
jaeger_exporter = JaegerExporter(
    collector_endpoint="http://jaeger-agent.social-network.svc.cluster.local:14268/api/traces",
)

span_processor = BatchSpanProcessor(jaeger_exporter)
provider.add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)


TIDB_HOST = "basic-tidb.tidb-cluster.svc.cluster.local"
TIDB_USER = "root"
TIDB_PASSWORD = ""
TIDB_DATABASE = "satellite_sim"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://orbital.local:8080", "127.0.0.1:3000"],  # adjust as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
scheduler = BackgroundScheduler()

def scheduled_simulation():
    print("Running scheduled simulation")
    simulate_and_log()
    

scheduler.add_job(scheduled_simulation, 'interval', seconds=10)  # Every 10 seconds
scheduler.start()

@app.get("/api/simulate")
def run_simulation():
    simulate_and_log()
    return {"message": "Simulation completed and data logged to TiDB"}

@app.get("/api/dashboard")
def get_dashboard_summary():
    ssl_ca_path = os.path.join(os.path.dirname(__file__), 'tidb-ca.pem')

    conn = pymysql.connect(
  host=TIDB_HOST,
    port=4000,
    user=TIDB_USER,
    password=TIDB_PASSWORD,
    database=TIDB_DATABASE,
    ssl={
        "ca": "/app/tidb-ca.pem",
        "check_hostname": True,
        "verify_mode": ssl.CERT_REQUIRED
    }
)
    cursor = conn.cursor()

    # Total telemetry logs ever recorded
    cursor.execute("SELECT COUNT(*) FROM telemetry")
    total_telemetry = cursor.fetchone()[0]

    # Only use the most recent telemetry per satellite
    cursor.execute("""
        SELECT COUNT(*) FROM telemetry t
        INNER JOIN (
            SELECT satellite_id, MAX(timestamp) AS latest_time
            FROM telemetry
            GROUP BY satellite_id
        ) latest ON t.satellite_id = latest.satellite_id AND t.timestamp = latest.latest_time
        WHERE t.battery_level < 30
    """)
    low_battery = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM telemetry t
        INNER JOIN (
            SELECT satellite_id, MAX(timestamp) AS latest_time
            FROM telemetry
            GROUP BY satellite_id
        ) latest ON t.satellite_id = latest.satellite_id AND t.timestamp = latest.latest_time
        WHERE t.status = 'ERROR'
    """)
    errors = cursor.fetchone()[0]

    # Only count currently active assigned contacts (end time is in future)
    cursor.execute("""
    SELECT COUNT(DISTINCT satellite_id)
    FROM contact_windows
    WHERE assigned = TRUE AND end_time > UTC_TIMESTAMP()
""")
    active_contacts = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return {
        "totalSatellites": 100,
        "activeContacts": active_contacts,
        "lowBattery": low_battery,
        "errorState": errors,
        "totalTelemetry": total_telemetry
    }

@app.get("/api/station/{station_id}")
def get_station_data(station_id: str):
    ssl_ca_path = os.path.join(os.path.dirname(__file__), 'tidb-ca.pem') 

    conn = pymysql.connect(
    host=TIDB_HOST,
    port=4000,
    user=TIDB_USER,
    password=TIDB_PASSWORD,
    database=TIDB_DATABASE,
    ssl={
        "ca": "/app/tidb-ca.pem",
        "check_hostname": True,
        "verify_mode": ssl.CERT_REQUIRED
    }
)
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
    sub.ground_station_id, 
    sub.satellite_id,
    sub.battery_level,
    sub.temperature,
    sub.status,
    sub.timestamp
FROM (
    SELECT 
        cw.ground_station_id, 
        cw.satellite_id,
        t.battery_level,
        t.temperature,
        t.status,
        t.timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY cw.satellite_id 
            ORDER BY t.timestamp DESC
        ) AS rn
    FROM contact_windows cw
    JOIN telemetry t ON cw.satellite_id = t.satellite_id 
                     AND cw.ground_station_id = t.ground_station_id
    WHERE cw.assigned = TRUE 
      AND cw.end_time > UTC_TIMESTAMP()
      AND cw.ground_station_id = %s
) sub
WHERE sub.rn = 1

""", (station_id,))

    
    results = cursor.fetchall()
    station_data = []
    for row in results:
        station_data.append({
            "satellite_id": row[1],
            "battery_level": row[2],
            "temperature": row[3],
            "status": row[4],
            "timestamp": row[5]
        })
    
    cursor.close()
    conn.close()
    return {"station_id": station_id, "satellites": station_data}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}