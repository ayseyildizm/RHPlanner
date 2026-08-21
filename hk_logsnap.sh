#!/bin/bash
# hk_logsnap.sh — run_ladder4.sh always writes the planner output to the same
# path (results/_explogs/run_l4_<occ>_<planner>.log), so each new config
# OVERWRITES the previous one's log.  Today's H3K10x3 log was already lost
# that way.  The per-move failure reasons (OMPL goal-infeasible vs controller
# tolerance abort) only exist in those logs, and they are now part of the
# analysis -- so keep a per-config copy.
#
# Follows the chain log: whichever tag most recently STARTed owns the live log.
# Snapshots every 60 s to results/_explogs/hk2_live_<tag>.log (planner) and
# hk2_stack_<tag>.log (move_group/controller), so a kill loses at most a minute.
set -u
LOGS=/home/ayse/Desktop/RecedingHorizon/results/_explogs
CHAIN=$LOGS/hk_ablation_chain2_20260728.log
while true; do
    tag=$(grep -oE "START [A-Za-z0-9]+ " "$CHAIN" 2>/dev/null | tail -1 | awk '{print $2}')
    if [ -n "${tag:-}" ]; then
        [ -f "$LOGS/run_l4_panels3_rh.log" ] && cp -f "$LOGS/run_l4_panels3_rh.log" "$LOGS/hk2_live_${tag}.log"
        [ -f "$LOGS/stack_l4_panels3.log" ] && cp -f "$LOGS/stack_l4_panels3.log" "$LOGS/hk2_stack_${tag}.log"
    fi
    sleep 60
done
