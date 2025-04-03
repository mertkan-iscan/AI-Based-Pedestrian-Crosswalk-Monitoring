import json

from database.DBManager import DBManager, convert_to_timestamp

if __name__ == '__main__':
    db = DBManager()

    #path_data = [[320, 480], [322, 482], [330, 485]]
    #db.insert_log(object_id=1, object_type="person", foot_path=path_data)

    print("All logs:")
    for row in db.fetch_logs():
        record_id, record_ts, record_obj_id, record_obj_type, record_foot_path = row
        coords_list = json.loads(record_foot_path)
        print(f"ID={record_id}, time={record_ts}, obj={record_obj_id}, type={record_obj_type}, coords={coords_list}")

    start_timestamp = convert_to_timestamp("2025-03-20", "00:00:00")
    end_timestamp = convert_to_timestamp("2025-03-21", "00:00:00")

    print(f"\nLogs between {start_timestamp} and {end_timestamp} for object_type='person':")
    for row in db.fetch_logs_by_timestamp_and_type(start_timestamp, end_timestamp, "person"):
        record_id, record_ts, record_obj_id, record_obj_type, record_foot_path = row
        coords_list = json.loads(record_foot_path)
        print(f"ID={record_id}, time={record_ts}, obj={record_obj_id}, type={record_obj_type}, coords={coords_list}")

    db.close()