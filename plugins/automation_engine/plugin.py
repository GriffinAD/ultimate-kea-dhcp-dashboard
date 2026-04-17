from lib.plugin_api import DashboardPlugin

class Plugin(DashboardPlugin):
    def setup(self, context):
        self.context = context
        self.rules = []
        context.subscribe("*", self.handle_event)

    def handle_event(self, event):
        for rule in self.rules:
            if rule.get("event") == event.type:
                for action in rule.get("actions", []):
                    self.execute(action, event)

    def execute(self, action, event):
        if action.get("type") == "log":
            print(f"[AUTOMATION] {event.type}: {event.payload}")

    def register_rule(self, rule):
        self.rules.append(rule)
