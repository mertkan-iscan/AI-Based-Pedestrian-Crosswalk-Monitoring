import queue
import threading
import concurrent.futures

from utils.ConfigManager import ConfigManager

task_queue = queue.Queue()

global_paths = {}
global_paths_lock = threading.Lock()

config_manager = ConfigManager()
record_paths = config_manager.get_database_config().get("record_paths")


def process_task(task, db_manager):
    task_type, object_id, data = task

    if task_type == 'update':

        with global_paths_lock:
            if object_id not in global_paths:
                global_paths[object_id] = []
            global_paths[object_id].append(data)

    elif task_type == 'disappear':
        with global_paths_lock:
            final_path = global_paths.pop(object_id, [])
            #print(f"[Task Processor] Removing object {object_id} from global_paths. Final path: {final_path}")

        if final_path and record_paths:
            db_manager.insert_log(object_id=object_id, object_type="person", foot_path=final_path)
            #print(f"[DB Writer] Object {object_id} disappeared. Final path written to DB: {final_path}")

        #elif not record_paths:
            #print(f"[DB Writer] Database recording is disabled. Path not recorded for object {object_id}.")
        #else:
            #print(f"[DB Writer] Object {object_id} disappeared. No path recorded (empty path).")


def dynamic_task_processor(db_manager, pool_size=4):
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
        while True:
            task = task_queue.get()
            if task is None:
                task_queue.task_done()
                break
            executor.submit(process_task, task, db_manager)
            task_queue.task_done()
