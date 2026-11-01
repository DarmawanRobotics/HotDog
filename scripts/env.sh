# shellcheck shell=bash
# The environment of hotdog.service in an interactive shell (same RMW, domain, robot settings):
#
#   source ~/dev/HotDog/scripts/env.sh       # scripts/hotdog.sh does this for every command
#   ros2 topic list                          # sees the stack, not a vendor stack on another RMW
#   hnode hotdog_patrol patrol_node patrol.yaml [ros args]
#
# hnode runs one node the way robot.launch.py does: package defaults, then PARAMS_FILE, then args.
# Env: HOTDOG_ENV (/etc/hotdog/hotdog.env), ROS_DISTRO (foxy)

HOTDOG_WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HOTDOG_WS
HOTDOG_ENV="${HOTDOG_ENV:-/etc/hotdog/hotdog.env}"
if [[ -r "$HOTDOG_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOTDOG_ENV"
    set +a
fi
export RMW_IMPLEMENTATION="${RMW_IMPLEMENTATION:-rmw_fastrtps_cpp}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-0}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-1}" OMP_NUM_THREADS="${OMP_NUM_THREADS:-1}"

set +u
# shellcheck disable=SC1090
source "/opt/ros/${ROS_DISTRO:-foxy}/setup.bash"
if [[ -f "$HOTDOG_WS/install/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "$HOTDOG_WS/install/setup.bash"
else
    echo "workspace not built yet: $HOTDOG_WS/scripts/setup.sh install build" >&2
fi

hnode() {
    if [[ $# -lt 3 ]]; then
        echo "usage: hnode <package> <executable> <config.yaml> [ros args]" >&2
        return 1
    fi
    local pkg=$1 exe=$2 cfg=$3
    shift 3
    local site=()
    [[ -f "${PARAMS_FILE:-}" ]] && site=(--params-file "$PARAMS_FILE")
    ros2 run "$pkg" "$exe" --ros-args -r __node:="$exe" \
        --params-file "$HOTDOG_WS/install/$pkg/share/$pkg/config/$cfg" "${site[@]}" "$@"
}
