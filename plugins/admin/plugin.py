from lib.plugin_api import DashboardPlugin, PluginEvent
import json
import time


class Plugin(DashboardPlugin):

    def setup(self, context):
        super().setup(context)

        self.events = []

        context.register_route("/api/plugins/admin/status", self.get_status)
        context.register_route("/api/plugins/admin/plugins", self.get_plugins)
        context.register_route("/api/plugins/admin/events", self.get_events)
        context.register_route("/api/plugins/admin/stream", self.stream_events)

        context.subscribe("*", self.capture_event)

        context.register_dashboard_card(
            "admin_overview",
            "System Overview",
            render=self.render_card,
            order=0
        )

        self.set_healthy("Admin ready")

    def capture_event(self, event: PluginEvent):
        self.events.append({
            "type": event.type,
            "source": event.source,
            "severity": event.severity,
            "timestamp": event.timestamp
        })
        self.events = self.events[-100:]

    def get_status(self, handler=None):
        pm = self.context.get_service("plugin_manager")
        return {
            "plugins": pm.describe_plugins() if pm else [],
            "events": len(self.events)
        }

    def get_plugins(self, handler=None):
        pm = self.context.get_service("plugin_manager")
        return pm.describe_plugins() if pm else []

    def get_events(self, handler=None):
        return self.events

    def stream_events(self, handler):
        handler.send_response(200)
        handler.send_header("Content-type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.end_headers()

        try:
            last_index = 0
            while True:
                if last_index < len(self.events):
                    event = self.events[last_index]
                    payload = f"data: {json.dumps(event)}\n\n"
                    handler.wfile.write(payload.encode("utf-8"))
                    handler.wfile.flush()
                    last_index += 1
                else:
                    time.sleep(1)
        except Exception:
            return {"_plugin_handled": True}

    def render_card(self):
        return """
        <div>
            <h3>Plugins</h3>
            <ul id='plugin-list'></ul>

            <h3>Live Events</h3>
            <ul id='event-list'></ul>

            <h3>Automation Rule Editor</h3>

            <button onclick="loadRules()">Load</button>
            <button onclick="saveRules()">Save</button>

            <h4>Quick Builder</h4>
            <input id="rule-id" placeholder="Rule ID"><br>
            <input id="rule-event" placeholder="Event type"><br>
            <input id="rule-path" placeholder="Condition path"><br>
            <input id="rule-value" placeholder="Value"><br>
            <input id="rule-action" placeholder="Action type"><br>
            <input id="rule-url" placeholder="Webhook URL"><br>
            <button onclick="addRule()">Add Rule</button>

            <h4>Rules JSON</h4>
            <textarea id="rules-json" style="width:100%;height:200px;"></textarea>

            <h4>Test Rule</h4>
            <button onclick="testRule()">Test</button>
            <pre id="test-output"></pre>

            <script>
                let rules = [];

                async function loadRules() {
                    const res = await fetch('/api/plugins/automation/rules');
                    const data = await res.json();
                    rules = data.rules || [];
                    render();
                }

                function render() {
                    document.getElementById('rules-json').value = JSON.stringify(rules, null, 2);
                }

                function addRule() {
                    const rule = {
                        id: document.getElementById('rule-id').value,
                        when: document.getElementById('rule-event').value,
                        if: [{
                            path: document.getElementById('rule-path').value,
                            op: 'eq',
                            value: document.getElementById('rule-value').value
                        }],
                        actions: [{
                            type: document.getElementById('rule-action').value,
                            url: document.getElementById('rule-url').value
                        }]
                    };
                    rules.push(rule);
                    render();
                }

                async function saveRules() {
                    await fetch('/api/plugins/automation/rules', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ rules })
                    });
                    alert('Saved');
                }

                async function testRule() {
                    if (!rules.length) return;
                    const res = await fetch('/api/plugins/automation/test', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ rule: rules[0] })
                    });
                    const data = await res.json();
                    document.getElementById('test-output').textContent = JSON.stringify(data, null, 2);
                }

                async function loadPlugins() {
                    const res = await fetch('/api/plugins/admin/plugins');
                    const data = await res.json();
                    const el = document.getElementById('plugin-list');
                    el.innerHTML = '';
                    data.forEach(p => {
                        const status = p.health?.status || 'unknown';
                        const icon = status === 'healthy' ? '🟢' : status === 'degraded' ? '🟡' : status === 'failed' ? '🔴' : '⚪';
                        el.innerHTML += `<li>${icon} ${p.id}</li>`;
                    });
                }

                function startStream() {
                    const eventList = document.getElementById('event-list');
                    const evtSource = new EventSource('/api/plugins/admin/stream');

                    evtSource.onmessage = function(event) {
                        const data = JSON.parse(event.data);
                        const item = document.createElement('li');
                        item.textContent = `${data.type} (${data.severity})`;
                        eventList.prepend(item);
                        if (eventList.children.length > 10) {
                            eventList.removeChild(eventList.lastChild);
                        }
                    };
                }

                loadPlugins();
                startStream();
            </script>
        </div>
        """

    def stop(self):
        super().stop()
