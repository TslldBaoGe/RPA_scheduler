import os


DATA_DIR = os.environ.get("DATA_DIR", "/app/data")

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "execution_history.json")
AGENTS_FILE = os.path.join(DATA_DIR, "agents.json")

CMD_TIMEOUT = 300

MAX_HISTORY_SIZE = 100
