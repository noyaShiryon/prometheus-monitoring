#!/usr/bin/env python3
from flask import Flask, request
import requests

app = Flask(__name__)

DISCORD_WEBHOOK = "https://discord.com/api/webhooks/<YOUR-WEBHOOK-KEY>"

def format_alert_for_discord(alert):
    status = alert.get('status', 'unknown')
    labels = alert.get('labels', {})
    annotations = alert.get('annotations', {})
    severity = labels.get('severity', 'info')
    colors = {'critical': 15158332, 'warning': 16776960, 'info': 3447003}
    color = colors.get(severity, 3447003)
    embed = {
        "title": f"🚨 {labels.get('alertname', 'Unknown Alert')}",
        "description": annotations.get('description', annotations.get('summary', 'No description')),
        "color": color,
        "fields": [
            {"name": "Status", "value": status.upper(), "inline": True},
            {"name": "Severity", "value": severity.upper(), "inline": True}
        ]
    }
    if 'instance' in labels:
        embed['fields'].append({"name": "Instance", "value": labels['instance'], "inline": False})
    return embed

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        alerts = data.get('alerts', [])
        if not alerts:
            return 'No alerts', 200
        embeds = [format_alert_for_discord(a) for a in alerts]
        for i in range(0, len(embeds), 10):
            response = requests.post(DISCORD_WEBHOOK, json={"embeds": embeds[i:i+10]})
            if response.status_code not in [200, 204]:
                return f'Discord error: {response.status_code}', 500
        return 'OK', 200
    except Exception as e:
        return str(e), 500

@app.route('/health', methods=['GET'])
def health():
    return 'OK', 200

if __name__ == '__main__':
    print(f"Starting bridge on port 9094")
    app.run(host='0.0.0.0', port=9094)
