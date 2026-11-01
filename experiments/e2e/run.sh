#!/usr/bin/env bash
# End-to-end runs on the real nodes: ./run.sh <workspace> [runs] (ROS sourced by the caller).
# Each run starts robot_bringup sim.launch.py, drives the route with drive_route.py, stops.
ws=${1:?usage: run.sh <workspace with the stack built> [runs]}
runs=${2:-5}
here=$(cd "$(dirname "$0")" && pwd)
logs=$(mktemp -d)
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}
# shellcheck disable=SC1091
source "$ws/install/setup.bash"
for run in $(seq "$runs"); do
  rm -rf /tmp/dharma_sim/sites/mall_loop ~/.dharma/last_route
  ros2 launch robot_bringup sim.launch.py params_file:="$here/sim_params.yaml" \
    > "$logs/launch_$run.log" 2>&1 &
  launch=$!
  sleep 20
  timeout 270 python3 "$here/drive_route.py" --run "$run" > "$logs/drive_$run.log" 2>&1
  echo "run $run: exit $? ($(tail -1 "$logs/drive_$run.log" | cut -c1-200))"
  kill -TERM "$launch"  # background jobs of a script ignore SIGINT
  wait "$launch"
done
echo "logs in $logs"
