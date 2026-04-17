import time

class PluginHealth:
    def __init__(self):
        self._data = {}

    def set(self, plugin_id, status, message=None):
        self._data[plugin_id] = {
            "status": status,
            "message": message,
            "updated": time.time()
        }

    def all(self):
        return self._data
