import os
import sqlite3
import json
from datetime import datetime
import threading

class DBManager:
    def __init__(self, db_file=None):
        if db_file is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(base_dir, '..'))
            resources_dir = os.path.join(project_root, 'resources')
            if not os.path.exists(resources_dir):
                os.makedirs(resources_dir)
            db_file = os.path.join(resources_dir, 'object_paths.db')

        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.lock = threading.Lock()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS foot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                object_id INTEGER,
                object_type TEXT,
                foot_path TEXT
            )
        ''')
        self.conn.commit()

    def insert_log(self, object_id, object_type, foot_path, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now().isoformat(timespec='seconds')
        foot_path_json = json.dumps(foot_path)
        with self.lock:
            self.cursor.execute('''
                INSERT INTO foot_logs (timestamp, object_id, object_type, foot_path)
                VALUES (?, ?, ?, ?)
            ''', (timestamp, object_id, object_type, foot_path_json))
            self.conn.commit()

    def fetch_logs(self):
        self.cursor.execute('SELECT * FROM foot_logs')
        return self.cursor.fetchall()

    def fetch_logs_by_timestamp_range(self, start_ts, end_ts):
        self.cursor.execute('''
            SELECT * FROM foot_logs
            WHERE timestamp >= ? AND timestamp < ?
        ''', (start_ts, end_ts))
        return self.cursor.fetchall()

    def fetch_logs_by_timestamp_and_type(self, start_ts, end_ts, object_type):
        self.cursor.execute('''
            SELECT * FROM foot_logs
            WHERE timestamp >= ? AND timestamp < ? 
              AND object_type = ?
        ''', (start_ts, end_ts, object_type))
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()

def convert_to_timestamp(date_str, time_str):
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
    return dt.isoformat(timespec='seconds')
