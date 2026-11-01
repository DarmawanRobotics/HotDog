#!/usr/bin/env bash
# Check or install what the stack needs on a robot computer, a dev machine or in the dev image.
#
#   scripts/setup.sh                       # same as: check
#   scripts/setup.sh check                 # status of every component
#   scripts/setup.sh install               # install the default components that are missing
#   scripts/setup.sh install repos build   # only these
#   scripts/setup.sh install all           # every component, service included
#
# Components: ros tools repos rosdep build service timesync ptp
#   ros      ROS 2 $ROS_DISTRO from packages.ros.org (ros-base)
#   tools    colcon, rosdep, vcstool, git, cmake, tmux, the Python packages of the stack
#   repos    the stack (dharma.repos) and the robot packages (external.repos: m20_ros2,
#            rslidar_sdk) under src/
#   rosdep   the system dependencies of every package under src/ (libpcap, yaml-cpp, ...)
#   build    colcon build of the workspace
#   service  a systemd unit running `ros2 launch hotdog robot.launch.py` at boot
#   timesync chrony: the system clock follows TIME_SERVERS and serves the robot's computers in
#            TIME_ALLOW (scripts/timesync.sh)
#   ptp      the LiDAR (LIDAR_IP or PTP_IFACE) stamps with this computer's clock over PTP
# Env: ROS_DISTRO (the one in /opt/ros, else the one of the Ubuntu release: 20.04 foxy,
#      22.04 humble, 24.04 jazzy), BUILD_WORKERS / BUILD_JOBS (lower them when the build runs
#      out of memory), SERVICE_NAME (hotdog), FORCE=1 (reinstall anyway),
#      TIME_SERVERS, TIME_ALLOW, LIDAR_IP, PTP_IFACE, PTP_TIMESTAMPING (see scripts/timesync.sh)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The ROS 2 distro of this computer: the installed one, else the one of the Ubuntu release.
default_distro() {
    local installed codename
    installed=$(find /opt/ros -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2> /dev/null | sort | tail -n1)
    [[ -n "$installed" ]] && echo "$installed" && return 0
    codename=$(. /etc/os-release 2> /dev/null && echo "${VERSION_CODENAME:-}")
    case "$codename" in
        focal) echo foxy ;;
        noble) echo jazzy ;;
        *) echo humble ;;
    esac
}
ROS_DISTRO="${ROS_DISTRO:-$(default_distro)}"
BUILD_WORKERS="${BUILD_WORKERS:-}"
BUILD_JOBS="${BUILD_JOBS:-}"
BRINGUP_PACKAGE=hotdog
SERVICE_NAME="${SERVICE_NAME:-$BRINGUP_PACKAGE}"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
ENV_FILE="/etc/$SERVICE_NAME/$SERVICE_NAME.env"
BUILD_STAMP="$ROOT/install/.build_commit"

ALL=(ros tools repos rosdep build service timesync ptp)
DEFAULT_INSTALL=(tools repos rosdep build)

SUDO=$([[ "$(id -u)" -eq 0 ]] && echo "" || echo "sudo")
IN_DOCKER=$([[ -f /.dockerenv ]] && echo 1 || echo 0)
if [[ -t 1 ]]; then
    GREEN=$'\e[32m' RED=$'\e[31m' YELLOW=$'\e[33m' BOLD=$'\e[1m' RESET=$'\e[0m'
else
    GREEN="" RED="" YELLOW="" BOLD="" RESET=""
fi

log() { echo "${BOLD}==>${RESET} $*"; }
usage() { sed -n '2,/^set -/p' "$0" | sed -e '$d' -e 's/^# \{0,1\}//'; }
apt_install() {
    $SUDO apt-get update -qq || log "${YELLOW}apt-get update had errors (check the mirrors)${RESET}"
    $SUDO apt-get -o DPkg::Lock::Timeout=180 install -y --no-install-recommends "$@"
}
source_ros() {
    set +u
    # shellcheck disable=SC1090
    source "/opt/ros/$ROS_DISTRO/setup.bash"
    set -u
}

# ---------------------------------------------------------------- components
# Each component has check_<name> (exit 0 = ok, prints one detail line) and install_<name>.

check_ros() {
    [[ -f "/opt/ros/$ROS_DISTRO/setup.bash" ]] && echo "/opt/ros/$ROS_DISTRO" && return 0
    echo "ROS 2 $ROS_DISTRO not found"
    return 1
}
install_ros() {
    apt_install software-properties-common curl gnupg lsb-release locales
    $SUDO add-apt-repository -y universe
    $SUDO curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
        -o /usr/share/keyrings/ros-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo "$UBUNTU_CODENAME") main" \
        | $SUDO tee /etc/apt/sources.list.d/ros2.list > /dev/null
    apt_install "ros-$ROS_DISTRO-ros-base"
}

TOOLS=(colcon rosdep vcs git cmake g++ tmux curl)
check_tools() {
    local missing=() cmd
    for cmd in "${TOOLS[@]}"; do
        command -v "$cmd" > /dev/null || missing+=("$cmd")
    done
    python3 -c 'import loguru, scipy, yaml' 2> /dev/null || missing+=("python3-loguru/scipy/yaml")
    [[ ${#missing[@]} -eq 0 ]] && echo "${TOOLS[*]}" && return 0
    echo "missing: ${missing[*]}"
    return 1
}
install_tools() {
    apt_install python3-colcon-common-extensions python3-rosdep python3-vcstool python3-pip \
        python3-scipy python3-yaml git cmake build-essential tmux curl ca-certificates
    # Ubuntu 20.04 (foxy) has no python3-loguru package
    if ! apt_install python3-loguru; then
        log "${YELLOW}no python3-loguru package: installing loguru with pip${RESET}"
        $SUDO pip3 install loguru
    fi
}

repo_paths() { # the checkout paths of a .repos file
    sed -nE 's/^  ([A-Za-z0-9_./-]+):[[:space:]]*$/\1/p' "$1"
}
check_repos() {
    local missing=() path
    for path in $(repo_paths "$ROOT/dharma.repos") $(repo_paths "$ROOT/external.repos"); do
        [[ -d "$ROOT/src/$path/.git" ]] || missing+=("$path")
    done
    [[ ${#missing[@]} -eq 0 ]] && echo "src/: every repository of dharma.repos, external.repos" \
        && return 0
    echo "not checked out: ${missing[*]}"
    return 1
}
install_repos() {
    command -v vcs > /dev/null || apt_install python3-vcstool
    vcs import --recursive --skip-existing "$ROOT/src" < "$ROOT/dharma.repos"
    vcs import --recursive --skip-existing "$ROOT/src" < "$ROOT/external.repos"
}

# python3-loguru has no rosdep rule on Ubuntu 20.04: the tools component installs loguru.
ROSDEP_SKIP=(--skip-keys python3-loguru)
check_rosdep() {
    check_ros > /dev/null || { echo "needs ROS"; return 1; }
    [[ -d /etc/ros/rosdep/sources.list.d ]] || { echo "rosdep not initialised"; return 1; }
    source_ros
    local report=/tmp/dharma_rosdep.log
    rosdep check --from-paths "$ROOT/src" --ignore-src --rosdistro "$ROS_DISTRO" "${ROSDEP_SKIP[@]}" \
        > "$report" 2>&1 && echo "all system dependencies installed" && return 0
    echo "missing keys, see $report"
    return 1
}
install_rosdep() {
    [[ -d /etc/ros/rosdep/sources.list.d ]] || $SUDO rosdep init
    source_ros
    rosdep update --rosdistro "$ROS_DISTRO" --include-eol-distros # foxy is end of life
    rosdep install --from-paths "$ROOT/src" --ignore-src -r -y --rosdistro "$ROS_DISTRO" \
        "${ROSDEP_SKIP[@]}"
}

check_build() {
    [[ -f "$ROOT/install/setup.bash" ]] || { echo "workspace not built"; return 1; }
    local n built head
    n=$(find "$ROOT/install" -mindepth 1 -maxdepth 1 -type d | wc -l)
    head=$(git -C "$ROOT" rev-parse --short HEAD 2> /dev/null || echo unknown)
    built=$(cat "$BUILD_STAMP" 2> /dev/null || echo unknown)
    [[ "$built" == "$head" ]] || { echo "built from $built, source is $head: rebuild"; return 1; }
    echo "$n packages in install/, built from $head"
}
install_build() {
    source_ros
    local args=(--cmake-args -DCMAKE_BUILD_TYPE=Release)
    [[ -n "$BUILD_WORKERS" ]] && args=(--parallel-workers "$BUILD_WORKERS" "${args[@]}")
    [[ -n "$BUILD_JOBS" ]] && export MAKEFLAGS="-j$BUILD_JOBS"
    (cd "$ROOT" && colcon build "${args[@]}")
    git -C "$ROOT" rev-parse --short HEAD > "$BUILD_STAMP" 2> /dev/null || echo unknown > "$BUILD_STAMP"
}

# The launch arguments of the same names default to these (robot.launch.py).
env_template() {
    printf '%s\n' \
        "# $SERVICE_NAME.service environment (also read by bash): no comments after values" \
        "ROS_DISTRO=$ROS_DISTRO" 'ROS_DOMAIN_ID=0' 'RMW_IMPLEMENTATION=rmw_fastrtps_cpp' \
        'ROBOT_NS=m20' 'ROBOT_DRIVER=m20_bringup' 'ROBOT_IP=10.21.31.103' 'DRIVER_PARAMS=' \
        'LIDAR=rslidar' 'SITE=' "SITES_DIR=$HOME/.hotdog/sites" \
        'OPENBLAS_NUM_THREADS=1' 'OMP_NUM_THREADS=1'
}
service_unit() {
    cat << EOF
[Unit]
Description=HotDog substation patrol robot ($BRINGUP_PACKAGE)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$ROOT
EnvironmentFile=-$ENV_FILE
Environment=PYTHONUNBUFFERED=1
Environment=RCUTILS_COLORIZED_OUTPUT=0
ExecStart=/bin/bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash && source $ROOT/install/setup.bash && exec ros2 launch $BRINGUP_PACKAGE robot.launch.py'
Restart=always
RestartSec=5
# SIGINT to ros2 launch only: it stops every node once; leftovers get SIGKILL after the timeout
KillSignal=SIGINT
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
EOF
}
check_service() {
    [[ "$IN_DOCKER" == "1" ]] && echo "skipped in docker" && return 0
    [[ -f "$SERVICE_FILE" ]] || { echo "$SERVICE_NAME.service not installed"; return 1; }
    service_unit | cmp -s - "$SERVICE_FILE" \
        || { echo "$SERVICE_FILE is outdated (other path or user)"; return 1; }
    systemctl is-enabled "$SERVICE_NAME.service" > /dev/null 2>&1 \
        || { echo "$SERVICE_NAME.service installed but not enabled at boot"; return 1; }
    echo "$SERVICE_NAME.service enabled ($(systemctl is-active "$SERVICE_NAME.service"))"
}
install_service() {
    if [[ ! -f "$ENV_FILE" ]]; then
        env_template | $SUDO install -D -m 640 -g "$(id -gn)" /dev/stdin "$ENV_FILE"
        log "created $ENV_FILE: set ROBOT_IP, SITE and DRIVER_PARAMS (this robot's calibration)"
    fi
    service_unit | $SUDO tee "$SERVICE_FILE" > /dev/null
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable "$SERVICE_NAME.service"
    log "start: sudo systemctl restart $SERVICE_NAME   logs: journalctl -fu $SERVICE_NAME"
}

# One clock for every stamp: the system clock (chrony) and the LiDAR's (PTP), see timesync.sh.
timesync_check() { # timesync_check <part>
    local out
    out=$("$ROOT/scripts/timesync.sh" check "$1") || { echo "${out#*: }"; return 1; }
    echo "${out#*: }"
}
check_timesync() { timesync_check chrony; }
install_timesync() { "$ROOT/scripts/timesync.sh" install chrony; }
check_ptp() { timesync_check ptp; }
install_ptp() { "$ROOT/scripts/timesync.sh" install ptp; }

# ---------------------------------------------------------------- driver

check_one() {
    local name=$1 detail status
    if detail=$("check_$name" 2>&1); then
        status="${GREEN}ok     ${RESET}"
    else
        status="${RED}missing${RESET}"
    fi
    printf '  %-10s %s  %s\n' "$name" "$status" "$(echo "$detail" | tail -n1)"
    [[ "$status" == *ok* ]]
}

do_check() {
    local failed=0 name
    echo "${BOLD}setup ($([[ $IN_DOCKER == 1 ]] && echo docker || echo host), $(uname -m), ROS $ROS_DISTRO)${RESET}"
    for name in "${ALL[@]}"; do
        check_one "$name" || failed=$((failed + 1))
    done
    if [[ $failed -eq 0 ]]; then
        echo "${GREEN}everything is ready${RESET}"
    else
        echo "${YELLOW}$failed component(s) need attention: scripts/setup.sh install <component>${RESET}"
    fi
}

do_install() {
    local targets=("$@") name
    [[ ${#targets[@]} -eq 0 ]] && targets=("${DEFAULT_INSTALL[@]}")
    [[ "${targets[0]}" == "all" ]] && targets=("${ALL[@]}")
    for name in "${targets[@]}"; do
        declare -F "install_$name" > /dev/null || { echo "${RED}unknown component: $name${RESET}"; exit 1; }
        if [[ "${FORCE:-0}" != "1" ]] && "check_$name" > /dev/null 2>&1; then
            echo "  $name: already ok"
            continue
        fi
        log "installing $name"
        "install_$name"
        check_one "$name" || { echo "${RED}$name still not ok after install${RESET}"; exit 1; }
    done
}

case "${1:-check}" in
    check) do_check ;;
    install) shift; do_install "$@" ;;
    -h | --help) usage ;;
    *) usage; exit 1 ;;
esac
