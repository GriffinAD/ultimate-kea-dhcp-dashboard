from lib.plugin_api import DashboardPlugin
import json
from pathlib import Path
from .actions import webhook_action

class Plugin(DashboardPlugin):
    def setup(self, context):
        self.context = context
        self.rules_path = Path(__file__).parent / "rules.json"
        self.rules = self._load_rules()
        context.subscribe("*", self.handle_event)

        context.register_route("/api/automation/rules", self.get_rules)
        context.register_route("/api/automation/rules/add", self.add_rule, methods=["POST"])
        context.register_route("/api/automation/rules/delete", self.delete_rule, methods=["POST"])

    def _load_rules(self):
        try:
            return json.loads(self.rules_path.read_text())
        except Exception:
            return []

    def _save_rules(self):
        self.rules_path.write_text(json.dumps(self.rules, indent=2))

    def handle_event(self, event):
        for rule in self.rules:
            if rule.get("event") == event.type:
                for action in rule.get("actions", []):
                    self.execute(action, event)

    def execute(self, action, event):
        atype = action.get("type")
        if atype == "log":
            print(f"[AUTOMATION] {event.type}: {event.payload}")
        elif atype == "webhook":
            webhook_action(action, event)

    def get_rules(self, handler=None):
        return self.rules

    def add_rule(self, handler):
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        self.rules.append(data)
        self._save_rules()
        return {"status": "ok"}

    def delete_rule(self, handler):
        length = int(handler.headers.get('Content-Length', 0))
        data = json.loads(handler.rfile.read(length))
        index = data.get("index")
        if isinstance(index, int) and 0 <= index < len(self.rules):
            self.rules.pop(index)
            self._save_rules()
        return {"status": "ok"}
