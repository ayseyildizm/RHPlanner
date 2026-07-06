# RH-NBV: UR5e + RealSense D455 — ROS 2 Jazzy

## Repositories
- recedinghorizon-ros2 — planner + experiment scripts
- ur5e-l515-ros2 — ROS 2 packages

## Installation (fresh machine)

### 1. ROS 2 apt dependencies
sudo apt update
sudo apt install -y ros-jazzy-ur ros-jazzy-ur-simulation-gz ros-jazzy-ur-moveit-config ros-jazzy-realsense2-description ros-jazzy-ros-gz ros-jazzy-moveit

### 2. Clone repositories
git clone https://github.com/ays3gul/ur5e-l515-ros2.git ~/ros2_ws/src
git clone https://github.com/ays3gul/recedinghorizon-ros2.git ~/Desktop/RecedingHorizon

### 3. Build the colcon workspace
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build
source install/setup.bash

### 4. Create the conda environment
conda env create -f ~/Desktop/RecedingHorizon/environment.yml
conda activate rh_nbv_ros2

## Running

### Terminal 1 — simulation + robot stack
source /opt/ros/jazzy/setup.bash
source ~/ros2_ws/install/setup.bash
export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:$HOME/ros2_ws/install/ur5e_l515_description/share
ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py

### Terminal 2 — planner (wait for "arm_control_node ready" first)
cd ~/Desktop/RecedingHorizon
PLANNER=pso OCC=none EXPERIMENT=D ./run_ros2_gz.sh

## Options
- PLANNER: rh, gradient, pso, random
- OCC: none, frontal, half_box, tunnel, well, panels

## Camera workspace (side views)
The camera box wraps around the bunny in -Y so side views are searchable
(fair_comparison_config.camera_bounds_for_start). Knobs:
- CAM_HW="x,y,z"        — symmetric halfwidths (default 0.35,0.10,0.22)
- CAM_WRAP_Y=0.60       — extra -Y extension past the bunny; 0 = old frontal-only box
- CAM_MIN_STANDOFF=0.50 — min camera-target distance, enforced by ALL planners.
  Must stay above the Gazebo D455 near clip (0.40 m) + bunny half-extent:
  closer than the clip the object vanishes from depth AND color images.
Unreachable poses in the wrapped box fail move_arm_to_pose and are pruned at
runtime by the reach-bounds tightening in viewpoint_planning.run_rh().

## OCC=panels1..4 — staged occlusion scenarios (make_panel_world.py)
Build once, then just switch the OCC label — the launch file picks the world
(ur5e_world_panels<N>.sdf) and the planners pick the F1-occluder manifest
(panels_occluders_stage<N>.json) from the label automatically:
    python3 make_panel_world.py --stages-all
    OCC=panels2 ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py
    OCC=panels2 PLANNER=gradient ./run_ros2_gz.sh
Stages (walls 14.4 cm tall, bottom-anchored → top 5.1 cm of bunny/ears always
visible; walls span each face edge-to-edge and TOUCH at the corners):
    panels1 = side wall | panels2 = +front (L) | panels3 = +other side (U) |
    panels4 = +back (4 walls, top open)
    --side right (default) = easier series (arm can barely reach +X anyway);
    --side left = harder series (blocks the arm-reachable -X side)
Wall height knob: --wall-height 0.144. Other modes: --box N (sealed box,
1..6 faces, --box 6 fully closed), --az 0,60,300 (ring; 0=front/+Y, 90=+X);
these write the single ur5e_world_panels.sdf, run them with bare OCC=panels.
Then RESTART the Gazebo stack and run with any OCC label starting with
"panels" — use the stage as suffix so results dirs are distinct:
    OCC=panels3 ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py
    OCC=panels3 PLANNER=gradient ./run_ros2_gz.sh
The script writes the world to src + install dirs (no colcon rebuild) and the
panel AABBs to src/simulation_environment/panels_occluders.json, which the
planners load to exclude panel voxels from F1 scoring.
