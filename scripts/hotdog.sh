#!/usr/bin/env bash
# HotDog for the operator: one command per task, run on the robot computer.
#
#   hotdog status                    the robot at a glance (patrol, health, battery, sensors)
#   hotdog patrol [route]            start a patrol from the dock (no route: the last one)
#   hotdog return                    walk the route back to the dock and dock
#   hotdog stop                      stop the patrol where the robot is
#   hotdog pause | resume            hold the patrol / go on
#   hotdog estop | release           latched emergency stop / release it (then: hotdog resume)
#   hotdog routes                    the routes of the active site
#   hotdog site [name]               the active site / load another
#   hotdog anchor                    the robot is on its dock: make it the map origin again
#   hotdog teach start               start teaching a route (the robot on its dock)
#   hotdog teach point [dwell_s]     a stop point here (default 5 s)
#   hotdog teach target <name> [thermal] [acoustic] [strips=N] [max=C]   pod's view as a target
#   hotdog teach stop                save the route
#   hotdog dock                      send the M20 to its dock (charge_start)
#   hotdog stand | sit               stand up / sit down
#   hotdog ambient <degC>            today's air temperature for the thermal analysis
#   hotdog schedule on | off | show  scheduled patrols (times and route: the site file)
#   hotdog reports                   where to open the reports
#   hotdog alert-test                a test alert to Telegram and the webhook
#   hotdog logs                      follow the service log
#   hotdog restart                   restart the service
#
# alias: echo "alias hotdog=$HOME/dev/HotDog/scripts/hotdog.sh" >> ~/.bashrc
# (scripts/setup.sh install cli). Env: as hotdog.service (/etc/hotdog/hotdog.env).
set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE="${SERVICE_NAME:-hotdog}"

usage() { sed -n '2,/^set -/p' "$0" | sed -e '$d' -e 's/^# \{0,1\}//'; }
ros() {
    set +e
    # shellcheck disable=SC1091
    source "$HERE/env.sh" > /dev/null
    set -e
}
# a service call that gives up instead of waiting forever for a stack that is not running
call() {
    timeout "${CALL_TIMEOUT:-30}" ros2 service call "$@" | sed -n '/^response:/,$p' \
        || { echo "no answer from $1 (is hotdog running? hotdog status)"; return 1; }
}
trigger() { call "$1" std_srvs/srv/Trigger "{}"; }
latched() {
    timeout 5 ros2 topic echo --once --qos-durability transient_local --qos-reliability reliable "$@"
}
ns() { echo "/${ROBOT_NS:-m20}"; }
# a number as a float literal (8 -> 8.0): float message fields and parameters refuse integers
float() {
    [[ "$1" =~ ^-?[0-9]+(\.[0-9]+)?$ ]] || { echo "not a number: $1" >&2; exit 1; }
    [[ "$1" == *.* ]] && echo "$1" || echo "$1.0"
}

teach() {
    case "${1:-}" in
        start)
            trigger /localization/assume_origin
            trigger /route/start
            ;;
        point)
            local dwell
            dwell=$(float "${2:-5}")
            call /route/mark_stop_point dharma_interfaces/srv/MarkStopPoint "{dwell_sec: $dwell}"
            ;;
        target)
            [[ -n "${2:-}" ]] || { echo "usage: hotdog teach target <name> [thermal] [acoustic] [strips=N] [max=C]"; exit 1; }
            local name=$2 thermal=false acoustic=false strips=0 max=0.0 arg
            shift 2
            for arg in "$@"; do
                case "$arg" in
                    thermal) thermal=true ;;
                    acoustic) acoustic=true ;;
                    strips=*) strips=${arg#strips=} thermal=true ;;
                    max=*)
                        max=$(float "${arg#max=}")
                        thermal=true
                        ;;
                    *) echo "unknown: $arg"; exit 1 ;;
                esac
            done
            [[ $thermal == true || $acoustic == true ]] || thermal=true
            call /inspection/add_target hotdog_interfaces/srv/AddTarget \
                "{name: '$name', thermal: $thermal, acoustic: $acoustic, strips: $strips, max_temp_c: $max}"
            ;;
        stop) trigger /route/stop ;;
        *) echo "usage: hotdog teach start | point [dwell_s] | target <name> ... | stop"; exit 1 ;;
    esac
}

schedule() {
    case "${1:-show}" in
        on | off)
            ros2 param set /patrol_node schedule.enabled "$([[ $1 == on ]] && echo true || echo false)"
            echo "keep it after a restart: patrol_node schedule.enabled in the site file (PARAMS_FILE)"
            ;;
        show)
            local p
            for p in enabled times route; do
                printf '%-8s %s\n' "$p" "$(ros2 param get /patrol_node "schedule.$p" 2>&1 \
                    | sed -E 's/^.* (value is|values are): //')"
            done
            ;;
        *) echo "usage: hotdog schedule on | off | show"; exit 1 ;;
    esac
}

case "${1:-status}" in
    status) ros; ros2 run hotdog status ;;
    patrol)
        ros
        call /patrol/start hotdog_interfaces/srv/StartPatrol "{route: '${2:-}'}"
        ;;
    return) ros; trigger /patrol/return ;;
    stop) ros; trigger /patrol/stop ;;
    pause) ros; trigger /navigation/pause ;;
    resume) ros; trigger /navigation/resume ;;
    estop) ros; trigger /control/estop/engage ;;
    release) ros; trigger /control/estop/release ;;
    routes)
        ros
        site=$(latched /site/status dharma_interfaces/msg/SiteStatus | sed -n 's/^site: //p' | tr -d "'\"")
        dir="${SITES_DIR:-$HOME/.hotdog/sites}/$site/routes"
        echo "site ${site:-?}: $dir"
        find "$dir" -maxdepth 1 -name '*.csv' -printf '  %f  (%TY-%Tm-%Td %TH:%TM, %s bytes)\n' 2> /dev/null | sort
        ;;
    site)
        ros
        if [[ -n "${2:-}" ]]; then
            call /site/load dharma_interfaces/srv/LoadSite "{site: '$2'}"
        else
            latched /site/status dharma_interfaces/msg/SiteStatus
        fi
        ;;
    anchor) ros; trigger /localization/assume_origin ;;
    teach) ros; shift; teach "$@" ;;
    dock) ros; trigger "$(ns)/charge_start" ;;
    stand) ros; trigger "$(ns)/stand_up" ;;
    sit) ros; trigger "$(ns)/sit_down" ;;
    ambient)
        [[ -n "${2:-}" ]] || { echo "usage: hotdog ambient <degC>"; exit 1; }
        celsius=$(float "$2")
        ros; ros2 param set /inspection_node thermal.ambient_c "$celsius"
        ;;
    schedule) ros; shift; schedule "$@" ;;
    reports)
        ros
        ros2 run hotdog status --wait 0.1 | grep -E '^(reports|disk)' || true
        echo "files: ${HOME}/.hotdog/reports/<YYYYMMDD>/"
        ;;
    alert-test) ros; trigger /alerts/test ;;
    logs) journalctl -fu "$SERVICE" ;;
    restart) sudo systemctl restart "$SERVICE" && echo "restarted; hotdog status in a few seconds" ;;
    -h | --help | help) usage ;;
    *) usage; exit 1 ;;
esac
