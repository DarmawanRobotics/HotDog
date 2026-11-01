# hotdog_alerts

Alerts from HotDog to the people who act on them, while the robot patrols: a Telegram group
of the substation crew and, for a control room or a ticket system, a JSON webhook.

| Event                                                   | Severity          | With                                    |
| ------------------------------------------------------- | ----------------- | --------------------------------------- |
| a finding at or above `findings.min_severity` (warning) | the finding's     | the thermal image or the sound map      |
| a patrol that failed                                    | critical          | why, findings per severity, report link |
| a patrol that came back to the dock on its own          | warning           | why (battery, duration, blocked)        |
| a patrol stopped by an operator                         | attention         |                                         |
| a finished patrol (`patrol_done`)                       | its worst finding | findings per severity, report link      |
| health ERROR (again after `health_repeat_min`)          | critical          | the issues                              |

```
🔴 CRITICAL at bay1_disconnector
HotDog 01 · site gi_cawang
bay1_ds_clamps (s): 112.4 °C, +38.0 °C over the other phases
bay1_ds_insulator: floating partial discharge, 44.0 dB
Report to the substation now.
```

The same finding (point, target, check, region or discharge type) is announced again only
after `findings.repeat_hours` (12 h) unless it got worse. `language: id` writes the alerts in
Bahasa Indonesia.

## Node

`alert_node` (`ros2 launch hotdog_alerts alerts.launch.py`, started by
`ros2 launch hotdog robot.launch.py`, `alerts:=false` or `ALERTS=false` to leave it out):

| Interface           | Type                                 |                                                    |
| ------------------- | ------------------------------------ | -------------------------------------------------- |
| `inspection/report` | `hotdog_interfaces/InspectionReport` | the findings of a point (its `report.json`)        |
| `patrol/status`     | `hotdog_interfaces/PatrolStatus`     | a patrol that ended after this node started        |
| `health/status`     | `dharma_interfaces/HealthStatus`     | level ERROR                                        |
| `alerts/test`       | `std_srvs/Trigger`                   | send a test alert to every channel (commissioning) |

**Never lost, never twice.** Every alert is written to `spool_dir` first and sent from there
every `retry_sec`, oldest first, each channel once: a substation without uplink for an hour
gets its alerts when the link is back, after a restart too. Alerts older than `max_age_hours`
or beyond `max_queued` are dropped (and logged).

## Set up

**Telegram:** create a bot with [@BotFather](https://t.me/BotFather), add it to the crew's
group, send a message in the group, then read the group's id (a negative number) from
`https://api.telegram.org/bot<token>/getUpdates`.

```bash
sudoedit /etc/hotdog/hotdog.env          # TELEGRAM_BOT_TOKEN=123456:ABC...
sudoedit /etc/hotdog/site.yaml           # alert_node: telegram.chat_ids, robot_name, report_url
sudo systemctl restart hotdog
ros2 service call /alerts/test std_srvs/srv/Trigger
```

```yaml
alert_node:
  ros__parameters:
    robot_name: HotDog 01 - GI Cawang
    language: id
    report_url: http://10.21.31.50:8088/ # how operators reach the report server
    telegram:
      chat_ids: ["-1001234567890"]
```

**Webhook:** `webhook.url`, and `HOTDOG_WEBHOOK_TOKEN` in the env file for an
`Authorization: Bearer` header. One POST per alert:

```json
{
  "robot": "HotDog 01",
  "kind": "finding",
  "severity": "critical",
  "title": "...",
  "text": "...",
  "link": "",
  "image": "/home/robot/.hotdog/reports/20261101/090200_bay1/bay1_ds_clamps_thermal.jpg",
  "data": { "site": "gi", "point": "bay1", "target": "bay1_ds_clamps", "findings": [] }
}
```

The robot computer needs outbound HTTPS to `api.telegram.org` (or the webhook); a proxy in
`HTTPS_PROXY` of the env file is used.

## Parameters

[config/alerts.yaml](config/alerts.yaml); every one with its range:
`ros2 param describe /alert_node <name>`. Secrets are never parameters.

## Test

```bash
colcon test --packages-select hotdog_alerts && colcon test-result --verbose
```

`test/unit`: findings at or above the minimum with their image, repeats, Bahasa Indonesia,
patrol and health alerts, links, the spool (age, size, broken files), Telegram (photo and
text, HTML escaping) and the webhook against a local stand-in, retried after a failure.
`test/ros`: the node against a stand-in webhook (a critical finding, a failed patrol but not
one that ended before the start, health ERROR, `alerts/test`).
