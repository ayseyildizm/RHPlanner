#!/bin/bash
# chain_mug_panels6.sh — Ayşe 2026-08-03: "bitince digerine gecmeyelim, durduralim,
# panels6 icin random-gradient-pso-rh calistirmak istiyorum, mug senaryosunda".
#
# 1. Koşmakta olan bunny/panels2 RH işinin bitmesini bekler (completion marker).
# 2. ROS shutdown'da asılı kalabilen planner node'unu temizler.
# 3. Ladder'ı mug + panels6 + random/gradient/pso/rh (1 trial) ile yeniden başlatır.
#
# Eski ladder parent'ı (bunny sweep, panels3..panels8 kuyruğu) bu script
# kurulurken ayrıca öldürüldü — kendiliğinden panels3'e geçmesin diye.
#
# NEW file — run_ladder4.sh / run_ros2_gz.sh'a dokunulmadı.
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
WATCH=$LOGS/run_l4_panels2_rh.log
CHAIN=$LOGS/chain_mug_panels6.log

say() { echo "[$(date '+%m-%d %H:%M:%S')] $*" >> "$CHAIN"; }

say "=== CHAIN START — bunny/panels2 rh bitişini bekliyorum ==="

# 1) Completion marker'ı bekle. 12 saat üst sınır (run_one'ın 45000s cap'i zaten
#    daha erken keser); marker gelmezse node ölünce de devam ederiz.
for _ in $(seq 1 2880); do
    grep -q "All trials complete" "$WATCH" 2>/dev/null && { say "marker gördüm"; break; }
    pgrep -f "test_rh_node.py" >/dev/null || { say "planner node yok (bitti/öldü) — devam"; break; }
    sleep 15
done

# 2) Marker sonrası asılı kalan node'u temizle (run_one'ın watchdog'unun işi).
sleep 20
pkill -9 -f "test_rh_node.py" 2>/dev/null
pkill -9 -f "test_gradient_node.py" 2>/dev/null
pkill -9 -f "test_baseline_node.py" 2>/dev/null
sleep 5
say "panels2 rh kapandı — mug/panels6 ladder'ı başlatıyorum"

# 3) Yeni ladder. start_stack zaten kill_stack ile eski gz/move_group yığınını
#    söküp OCC=panels6 TARGET=mug ile yenisini kaldırıyor.
cd "$RH_DIR"
setsid nohup env L4_OCCS="panels6" L4_PLANNERS="random gradient pso rh" \
    L4_TRIALS=1 L4_TARGET=mug \
    ./run_ladder4.sh > "$LOGS/mug_panels6_4planner_20260803.log" 2>&1 < /dev/null &
say "LADDER PID=$! (occ=panels6, planners=random gradient pso rh, trials=1, target=mug)"
say "=== CHAIN HANDOFF COMPLETE ==="
