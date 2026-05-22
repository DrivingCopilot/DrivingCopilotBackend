import sqlite3
import os
from datetime import datetime, timedelta

# DB 파일 경로 설정 
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "vehicle_data.db")

def init_db(db_path: str = DB_PATH) -> None:
    # DB 파일 자동 생성
    con = sqlite3.connect(db_path)
    cursor = con.cursor()

    # 1. 실시간 센서 데이터 (vehicle_telemetry)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicle_telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        speed REAL,
        rpm INTEGER,
        fuel REAL,
        battery REAL,
        tire TEXT
    )
    ''')

    # 2. 정비 이력 (maintenance_log)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS maintenance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date DATE,
        mileage INTEGER,
        type TEXT,
        parts TEXT,
        cost REAL
    )
    ''')

    # 3. OBD-II 진단 코드 (dtc_codes)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS dtc_codes (
        code TEXT PRIMARY KEY,
        description TEXT,
        severity TEXT,
        resolved BOOLEAN
    )
    ''')

    # 4. 운행 기록 (trip_history)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trip_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time DATETIME,
        end_time DATETIME,
        distance REAL,
        avg_speed REAL,
        fuel REAL
    )
    ''')

    
    # dtc_codes 확인
    cursor.execute("SELECT COUNT(*) FROM dtc_codes")
    if cursor.fetchone()[0] == 0:
        dtc_data = [
            ("P0301", "Cylinder 1 Misfire Detected", "High", False),
            ("P0420", "Catalyst System Efficiency Below Threshold", "Medium", False),
            ("U0100", "Lost Communication with ECM/PCM", "High", True)
        ]
        cursor.executemany("INSERT INTO dtc_codes (code, description, severity, resolved) VALUES (?, ?, ?, ?)", dtc_data)

    # maintenance_log 확인
    cursor.execute("SELECT COUNT(*) FROM maintenance_log")
    if cursor.fetchone()[0] == 0:
        maintenance_data = [
            ("2025-10-15", 15000, "Regular", "Engine Oil, Oil Filter", 85.0),
            ("2026-03-20", 22000, "Repair", "Brake Pads (Front)", 150.0),
            ("2026-05-10", 25000, "Regular", "Cabin Air Filter, Tire Rotation", 60.0)
        ]
        cursor.executemany("INSERT INTO maintenance_log (date, mileage, type, parts, cost) VALUES (?, ?, ?, ?, ?)", maintenance_data)

    # trip_history 확인
    cursor.execute("SELECT COUNT(*) FROM trip_history")
    if cursor.fetchone()[0] == 0:
        now = datetime.now()
        trip_data = [
            ((now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(days=2, hours=-1)).strftime("%Y-%m-%d %H:%M:%S"), 45.2, 55.0, 3.5),
            ((now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(days=1, hours=-2)).strftime("%Y-%m-%d %H:%M:%S"), 120.5, 75.0, 9.2),
            ((now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"), (now - timedelta(hours=2, minutes=30)).strftime("%Y-%m-%d %H:%M:%S"), 15.0, 30.0, 1.2)
        ]
        cursor.executemany("INSERT INTO trip_history (start_time, end_time, distance, avg_speed, fuel) VALUES (?, ?, ?, ?, ?)", trip_data)

    # vehicle_telemetry 확인
    cursor.execute("SELECT COUNT(*) FROM vehicle_telemetry")
    if cursor.fetchone()[0] == 0:
        now = datetime.now()
        telemetry_data = [
            ((now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"), 60.5, 2000, 45.5, 12.4, '{"FL": 34, "FR": 34, "RL": 35, "RR": 35}'),
            ((now - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"), 65.0, 2100, 45.4, 12.4, '{"FL": 34, "FR": 34, "RL": 35, "RR": 35}'),
            (now.strftime("%Y-%m-%d %H:%M:%S"), 0.0, 800, 45.3, 12.3, '{"FL": 33, "FR": 34, "RL": 35, "RR": 35}')
        ]
        cursor.executemany("INSERT INTO vehicle_telemetry (ts, speed, rpm, fuel, battery, tire) VALUES (?, ?, ?, ?, ?, ?)", telemetry_data)

    con.commit()
    con.close()

if __name__ == "__main__":
    init_db()
    print(f"Database initialized successfully at {DB_PATH}")
