import time

class Alerts:
    def __init__(self):
        self._alerts = []

    def push(self, level, message, plugin=None):
        self._alerts.append({
            "level": level,
            "message": message,
            "plugin": plugin,
            "time": time.time()
        })

    def list(self):
        return self._alerts[-50:]
