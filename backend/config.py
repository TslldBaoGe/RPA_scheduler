import os


DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))

TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "execution_history.json")
AGENTS_FILE = os.path.join(DATA_DIR, "agents.json")

CMD_TIMEOUT = 300

MAX_HISTORY_SIZE = 100
