#!/bin/bash
# run_ros2_real.sh — GERÇEK UR5e + D455 üzerinde planner (RH-NBV).
# run_ros2_gz.sh'ın donanım ikizi: TEK fark use_sim_time=false + Gazebo YOK.
#
# ÖN KOŞUL — gerçek robot yığını AYRI terminalde çalışıyor olmalı:
#   source /opt/ros/jazzy/setup.bash && source ~/ros2_ws/install/setup.bash
#   ros2 launch ur5e_l515_description real_ur5e.launch.py robot_ip:=192.168.1.102
#   (teach-pendant'ta External Control programını PLAY et)
# "arm_control ready — serving move_arm_to_pose" görününce çalıştır.
#
# İLK DENEME İÇİN GÜVENLİK: yavaş başla, E-stop elinde olsun.
#   PLANNER=gradient OCC=none NUM_TRIALS=1 ./run_ros2_real.sh
#
# Kullanım (run_ros2_gz.sh ile aynı env knob'ları):
#   ./run_ros2_real.sh
#   PLANNER=gradient ./run_ros2_real.sh
#   RH_K=20 RH_H=2 NUM_TRIALS=4 ./run_ros2_real.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROS2_WS="$HOME/ros2_ws"
CONDA_PYTHON="$HOME/miniconda3/envs/rh_nbv_ros2/bin/python"

PLANNER="${PLANNER:-rh}"
case "$PLANNER" in
    rh|RH)
        PYTHON_SCRIPT="$SCRIPT_DIR/src/viewpoint_planning/src/test_rh_node.py" ;;
    gradient|GradientNBV|gradientnbv)
        PYTHON_SCRIPT="$SCRIPT_DIR/src/viewpoint_planning/src/test_gradient_node.py" ;;
    pso|PSO|random|Random)
        PYTHON_SCRIPT="$SCRIPT_DIR/src/viewpoint_planning/src/test_baseline_node.py"
        export PLANNER="$PLANNER" ;;
    *)
        echo "[ERROR] Unknown PLANNER='$PLANNER'. Use: rh, gradient, pso, random"; exit 1 ;;
esac

# Temiz Jazzy ortamı
unset ROS_DISTRO ROS_VERSION ROS_PYTHON_VERSION
unset AMENT_PREFIX_PATH CMAKE_PREFIX_PATH COLCON_PREFIX_PATH
unset ROS_PACKAGE_PATH PYTHONPATH LD_LIBRARY_PATH

source /opt/ros/jazzy/setup.bash
if [ -f "$ROS2_WS/install/setup.bash" ]; then
    source "$ROS2_WS/install/setup.bash"
else
    echo "[ERROR] $ROS2_WS/install/setup.bash yok. Önce: cd $ROS2_WS && colcon build"; exit 1
fi

ROS2_LD_LIBRARY_PATH="$LD_LIBRARY_PATH"

export PYTHONPATH=\
$SCRIPT_DIR/src/viewpoint_planning/src:\
$SCRIPT_DIR/src/robot/abb_control/src:\
$SCRIPT_DIR/src/common/utils/src:\
/opt/ros/jazzy/lib/python3.12/site-packages:\
$ROS2_WS/install/abb_interfaces/lib/python3.12/site-packages

export LD_LIBRARY_PATH=/opt/ros/jazzy/lib:$ROS2_WS/install/abb_interfaces/lib:$ROS2_WS/install/abb_control/lib
export PYTHONUNBUFFERED=1

# ============================================================
# TEK KRİTİK FARK: gerçek robotta simülasyon saati YOK.
export USE_SIM_TIME=false
# ============================================================

# GERÇEK NESNE = COFFEE MUG (117×70×100 mm). Planner ROI'yi mug MERKEZİNE nişanlar.
# Mug masa üstü 0.85 m, tepe 0.95 → merkez 0.90 (bunny 0.92 değil; mug daha kısa).
# get_target_position()'da mug dalı olmadığından TARGET_POS ile ezilir:
export TARGET_POS="${TARGET_POS:-0.50,-0.30,0.90}"

RVIZ_CONFIG="$SCRIPT_DIR/src/viewpoint_planning/config/viewpoint_planning.rviz"
RVIZ="${RVIZ:-1}"
RVIZ_PID=""
if [ "$RVIZ" = "1" ] && [ -f "$RVIZ_CONFIG" ]; then
    echo "[run_ros2_real.sh] RViz2 başlatılıyor..."
    LD_LIBRARY_PATH="$ROS2_LD_LIBRARY_PATH" rviz2 -d "$RVIZ_CONFIG" &
    RVIZ_PID=$!
fi

echo "[run_ros2_real.sh] GERÇEK ROBOT | Planner: $PLANNER | $(basename $PYTHON_SCRIPT)"
echo "[run_ros2_real.sh] use_sim_time=false — Gazebo YOK, gerçek UR5e+D455 bekleniyor."

"$CONDA_PYTHON" -u \
    "$PYTHON_SCRIPT" \
    --ros-args -p use_sim_time:=false "$@"
STATUS=$?

[ -n "$RVIZ_PID" ] && kill "$RVIZ_PID" 2>/dev/null
exit $STATUS
