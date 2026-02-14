# Prometheus Uptime Monitoring with EC2 Auto Discovery and Discord Alerts

A production-ready uptime monitoring system built on AWS that automatically discovers EC2 instances, tracks their availability, and delivers real-time alerts to Discord.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        AWS VPC                          │
│                                                         │
│  ┌──────────────────────┐    ┌───────────────────────┐  │
│  │    Public Subnet     │    │    Private Subnet     │  │
│  │                      │    │                       │  │
│  │  ┌────────────────┐  │    │  ┌─────────────────┐  │  │
│  │  │   Prometheus   │◄─┼────┼──│  Node Exporter  │  │  │
│  │  │   :9090        │  │    │  │  :9100          │  │  │
│  │  │                │  │    └──┴─────────────────┘  │  │
│  │  │  Alertmanager  │  │                             │  │
│  │  │   :9093        │  │    ┌─────────────────────┐  │  │
│  │  │                │  │    │  Node Exporter      │  │  │
│  │  │ Discord Bridge │  │    │  :9100              │  │  │
│  │  │   :9094        │  │    └─────────────────────┘  │  │
│  │  └────────┬───────┘  │                             │  │
│  └───────────┼──────────┘                             │  │
└──────────────┼─────────────────────────────────────────┘
               │
               ▼
          Discord Webhook
```

**Metrics flow:** Node Exporters → Prometheus
**Alerts flow:** Prometheus → Alertmanager → Discord Bridge → Discord

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Monitoring | Prometheus v2.53.0 |
| Metrics Agent | Node Exporter v1.9.1 |
| Alert Manager | Alertmanager v0.29.0 |
| Alert Delivery | Discord Webhook + Python Bridge |
| Infrastructure | AWS EC2, VPC, IAM |
| OS | Ubuntu 22.04 LTS |

---

## Features

- **Automatic EC2 Discovery** — Prometheus detects all EC2 instances tagged with `Role=NodeExporter`, no manual IP configuration required
- **Real-time Alerting** — Discord notifications triggered within 1 minute of instance downtime
- **Private Network Isolation** — Node Exporters run in a private subnet, never exposed to the internet
- **Persistent Services** — All components managed via systemd, auto-restart on failure
- **Resolved Alerts** — Discord notified when an instance recovers

---

## AWS Infrastructure

| Resource | Name | Details |
|----------|------|---------|
| VPC | prometheus-vpc | 10.0.0.0/16 |
| Public Subnet | public-subnet-prometheus | 10.0.1.0/24 |
| Private Subnet | private-subnet-ec2 | 10.0.2.0/24 |
| Internet Gateway | prometheus-igw | Attached to VPC |
| NAT Gateway | prometheus-nat | Outbound access for private subnet |
| IAM Role | PrometheusEC2DiscoveryRole | AmazonEC2ReadOnlyAccess |

### Security Groups

**SG-Prometheus (Public)**
| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | Your IP | SSH Access |
| 9090 | TCP | Your IP | Prometheus Web UI |
| 9093 | TCP | Your IP | Alertmanager Web UI |

**SG-NodeExporters (Private)**
| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | SG-Prometheus | SSH via jump host |
| 9100 | TCP | SG-Prometheus | Metrics scraping |

---

## Project Structure

```
prometheus-monitoring/
├── README.md
├── .gitignore
├── prometheus/
│   ├── prometheus.yml                  # Prometheus config with EC2 Auto Discovery
│   └── alert_rules.yml                 # Alerting rules
├── alertmanager/
│   └── alertmanager.yml                # Alertmanager routing config
├── discord-bridge/
│   └── alertmanager-discord-bridge.py  # Converts Alertmanager format to Discord embeds
└── systemd/
    ├── prometheus.service
    ├── alertmanager.service
    └── alertmanager-discord-bridge.service
```

---

## Setup Guide

### Prerequisites

- AWS account with EC2 access
- Discord server with Webhook URL
- EC2 Key Pair (`.pem` file)
- IAM Role with `AmazonEC2ReadOnlyAccess`

### 1. Tag Node Exporter Instances

All EC2 instances running Node Exporter must have the following tag:

```
Key:   Role
Value: NodeExporter
```

### 2. Install Node Exporter (on each private instance)

```bash
wget https://github.com/prometheus/node_exporter/releases/download/v1.9.1/node_exporter-1.9.1.linux-amd64.tar.gz
tar xvf node_exporter-1.9.1.linux-amd64.tar.gz
sudo mv node_exporter-1.9.1.linux-amd64/node_exporter /usr/local/bin/
sudo systemctl enable --now node_exporter
```

### 3. Install Prometheus (on public instance)

```bash
wget https://github.com/prometheus/prometheus/releases/download/v2.53.0/prometheus-2.53.0.linux-amd64.tar.gz
tar xvf prometheus-2.53.0.linux-amd64.tar.gz
```

Copy `prometheus/prometheus.yml` and `prometheus/alert_rules.yml` to the Prometheus directory, then:

```bash
sudo systemctl enable --now prometheus
```

### 4. Install Alertmanager

```bash
wget https://github.com/prometheus/alertmanager/releases/download/v0.29.0/alertmanager-0.29.0.linux-amd64.tar.gz
tar xvfz alertmanager-0.29.0.linux-amd64.tar.gz
sudo cp alertmanager-0.29.0.linux-amd64/alertmanager /usr/local/bin/
```

### 5. Configure Discord Bridge

Set your Discord Webhook URL as an environment variable:

```bash
export DISCORD_WEBHOOK="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
```

Install dependencies and start the bridge:

```bash
sudo pip3 install flask requests --break-system-packages --ignore-installed
sudo systemctl enable --now alertmanager-discord-bridge
```

### 6. Verify the Setup

```bash
# Check all services are running
sudo systemctl status prometheus
sudo systemctl status alertmanager
sudo systemctl status alertmanager-discord-bridge

# Check all ports are listening
sudo ss -tulpn | grep -E '9090|9093|9094'

# Send a test alert
curl -XPOST http://localhost:9093/api/v2/alerts \
-H "Content-Type: application/json" -d '[{
  "labels": {"alertname":"TestAlert","severity":"critical","instance":"test"},
  "annotations": {"summary":"Test","description":"Monitoring stack is working!"}
}]'
```

---

## Alert Rules

| Alert | Condition | Severity | Trigger |
|-------|-----------|----------|---------|
| InstanceDown | `up == 0` | Critical | 1 minute |
| NodeExporterDown | `up{job="node_exporters"} == 0` | Critical | 1 minute |

---

## Key Design Decisions

**Why a Discord Bridge?**
Alertmanager sends webhooks in its own JSON format, which Discord does not natively support. The Python bridge converts Alertmanager payloads into Discord embeds with color-coded severity levels.

**Why separate cluster port for Alertmanager?**
By default, Alertmanager uses port 9094 for cluster communication — the same port used by the Discord Bridge. The `--cluster.listen-address=127.0.0.1:9095` flag resolves this conflict.

**Why private subnet for Node Exporters?**
Metrics endpoints should never be publicly accessible. Keeping Node Exporters in a private subnet ensures only Prometheus can scrape them.

---

## Security Notes

- Never commit `.pem` files or Webhook URLs to version control
- Store the Discord Webhook URL as an environment variable or in AWS Secrets Manager
- Restrict Security Group rules to specific IPs rather than `0.0.0.0/0`

---

## License

MIT