#!/bin/bash
# run_hsv_test.sh — D455'i laptopa tak, kırmızı HSV segmentasyonunu canlı ayarla.
# Robot/launch GEREKMEZ: planner topic'i yayında değilse realsense node'unu
# kendisi başlatır, çıkışta kapatır.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"

unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
unset ROS_PACKAGE_PATH PYTHONPATH LD_LIBRARY_PATH
source /opt/ros/jazzy/setup.bash

TOPIC="${HSV_TOPIC:-/camera/color/image_rect_color}"

CAM_PID=""
if ! timeout 5 ros2 topic list 2>/dev/null | grep -qx "$TOPIC"; then
    if ! lsusb | grep -qi "intel"; then
        echo "[hsv_test] D455 USB'de görünmüyor — USB 3 porta tak (lsusb'de 'Intel' çıkmalı)."
        exit 1
    fi
    echo "[hsv_test] Kamera node'u başlatılıyor (topic: $TOPIC)..."
    ros2 run realsense2_camera realsense2_camera_node --ros-args \
        -r __ns:=/camera -r __node:=camera \
        -p rgb_camera.color_profile:=848x480x30 \
        -r "~/color/image_raw:=$TOPIC" >/dev/null 2>&1 &
    CAM_PID=$!
    trap '[ -n "$CAM_PID" ] && kill $CAM_PID 2>/dev/null' EXIT
    sleep 4
fi

export PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages
export LD_LIBRARY_PATH=/opt/ros/jazzy/lib
export PYTHONUNBUFFERED=1
export HSV_TOPIC="$TOPIC"

"$CONDA_PYTHON" -u "$SCRIPT_DIR/hsv_test.py"
