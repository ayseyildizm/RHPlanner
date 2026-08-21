#!/bin/bash
# chain_f1sweep_20260804.sh — Ayşe 2026-08-04: F1 eşiği doygunluk testi.
#
# Plant seviyelerinde dört planlayıcının F1'i 0.05 içinde ve rastgele yürüyüş
# RH-NBV'ye yetişiyor. Şüphe: 2*rho eşleşme toleransı skoru doyuruyor. Test
# için aynı koşular nokta bulutu dökümüyle tekrarlanıyor; F1 sonra çevrimdışı
# başka eşiklerde yeniden hesaplanacak.
#
# 4 koşu, hepsi tek yönelim (psi=0), 1 trial:
#     fruit y000  : RH-NBV, Random   (doygun olduğu düşünülen seviye)
#     all   y000  : RH-NBV, Random   (Random'ın RH'yi geçtiği seviye)
# GradientNBV atlandı (orta sırada, ayrı bir hikâye); PSO atlandı (20 hareketin
# 2-10'unu icra edebiliyor, karşılaştırmayı bozar).
#
# NEW file — run_tree.sh / run_tree_ladder.sh / test_*_node.py'ye dokunulmadı.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
PROG=$LOGS/f1sweep_progress.log
mkdir -p "$LOGS"

say() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$PROG"; }

kill_stack() {
    pkill -9 -f "test_tree_f1dump_node.py" 2>/dev/null
    pkill -9 -f "test_rh_tree_node.py" 2>/dev/null
    pkill -9 -f "test_baseline_tree_node.py" 2>/dev/null
    pkill -INT -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    for _ in $(seq 1 15); do
        pgrep -f "worlds/ur5e_world" >/dev/null || break
        sleep 2
    done
    pkill -9 -f "move_group_gz_ur5e.launch.py" 2>/dev/null
    pkill -9 -f "gz sim" 2>/dev/null
    pkill -9 -f "moveit_ros_move_group" 2>/dev/null
    pkill -9 -f "arm_control_node" 2>/dev/null
    pkill -9 -f "parameter_bridge" 2>/dev/null
    pkill -9 -f "worlds/ur5e_world" 2>/dev/null
    pkill -9 -f "robot_state_publisher" 2>/dev/null
    pkill -9 -f "rviz2" 2>/dev/null
    sleep 4
    rm -f /dev/shm/fastrtps_* /dev/shm/fast_datasharing* 2>/dev/null
    sleep 4
}

start_stack() {  # $1 = OCC
    kill_stack
    nohup bash -c "source /opt/ros/jazzy/setup.bash && \
        source \$HOME/ros2_ws/install/setup.bash && \
        export GZ_SIM_RESOURCE_PATH=\$GZ_SIM_RESOURCE_PATH:\$HOME/ros2_ws/install/ur5e_l515_description/share && \
        export DISPLAY=:0 && \
        HEADLESS=1 OCC=$1 TARGET=tomato exec ros2 launch ur5e_l515_description move_group_gz_ur5e.launch.py" \
        > "$LOGS/stack_f1sweep_$1.log" 2>&1 &
    for _ in $(seq 1 80); do
        if grep -q "serving move_arm_to_pose" "$LOGS/stack_f1sweep_$1.log" 2>/dev/null; then
            if bash -c "source /opt/ros/jazzy/setup.bash && \
                    source \$HOME/ros2_ws/install/setup.bash && \
                    timeout 180 ros2 topic echo --once /camera/color/image_rect_color" \
                    >/dev/null 2>&1; then
                sleep 3; return 0
            fi
            say "WARN: camera stream not up 3 min after arm service ($1) — starting anyway"
            return 0
        fi
        sleep 3
    done
    say "FATAL: stack for $1 not ready in 4 min"
    return 1
}

run_one() {  # $1=OCC $2=planner $3=TOMATO_TARGET $4=ROI_HALF $5=GRID $6=VOXEL $7=F1_THRESH
    local occ=$1 planner=$2 tt=$3 roi=$4 grid=$5 vox=$6 f1t=$7
    local log="$LOGS/f1sweep_${tt}_${planner}.log"
    cd "$RH_DIR"
    for attempt in 1 2 3; do
        say "START $tt $planner (occ=$occ roi=$roi vox=${vox:-default} thr=$f1t) attempt=$attempt"
        timeout 9000 env OCC="$occ" PLANNER="$planner" \
            TARGET=tomato TOMATO_TARGET="$tt" TREE_YAW=0 ROI_HALF="$roi" \
            ${grid:+GRID_SIZE="$grid"} ${vox:+VOXEL_SIZE="$vox"} \
            F1_THRESH="$f1t" NUM_TRIALS=1 EXPERIMENT=C RVIZ=0 \
            ./run_tree_f1dump.sh > "$log" 2>&1 &
        local pid=$!
        # ArmControlClient's recovery path is guarded by `if rclpy.ok()`, which is
        # exactly false in the failure it exists for (arm_control_client.py:97):
        # once the context is down every move burns its full 180 s deadline and
        # the run limps on with unexecuted viewpoints. Abort early on that
        # signature and retry on a fresh stack rather than collect bad data.
        local dead=0
        while kill -0 "$pid" 2>/dev/null; do
            if grep -q "\[f1dump\] wrote" "$log" 2>/dev/null; then
                sleep 15
                pkill -9 -f "test_tree_f1dump_node.py" 2>/dev/null
                break
            fi
            if grep -q "rclpy.ok=False" "$log" 2>/dev/null; then
                dead=1
                say "ABORT $tt $planner — rclpy context down (attempt $attempt)"
                pkill -9 -f "test_tree_f1dump_node.py" 2>/dev/null
                break
            fi
            sleep 15
        done
        wait "$pid"; local rc=$?
        grep -q "\[f1dump\] wrote" "$log" 2>/dev/null && rc=0
        local nto
        nto=$(grep -c "Service call timed out" "$log" 2>/dev/null)
        say "END $tt $planner rc=$rc timeouts=$nto (attempt $attempt)"
        if [ "$dead" = 0 ] && [ "$rc" = 0 ] && [ "${nto:-0}" -le 2 ]; then
            return 0
        fi
        say "RETRY $tt $planner — yığın yeniden kaldırılıyor"
        mv -f "$log" "$log.attempt$attempt" 2>/dev/null
        start_stack "$occ" || return 1
    done
    say "GIVE UP $tt $planner after 3 attempts"
}

# Devam eden bir planlayıcı varsa bitmesini bekle.
while pgrep -f "test_rh_node.py|test_gradient_node.py|test_baseline_node.py" >/dev/null; do sleep 20; done

say "=== F1 SWEEP CHAIN START (fruit+all, y000, rh+random) ==="

start_stack panels_tree_fruit_y000 || exit 1
run_one panels_tree_fruit_y000 rh     fruit 0.105 ""                 ""      0.006
run_one panels_tree_fruit_y000 random fruit 0.105 ""                 ""      0.006

start_stack panels_tree_all_y000 || exit 1
run_one panels_tree_all_y000   rh     all   0.31  "0.38,0.6,0.62"    0.005   0.010
run_one panels_tree_all_y000   random all   0.31  "0.38,0.6,0.62"    0.005   0.010

say "=== F1 SWEEP CHAIN COMPLETE ==="
