#!/bin/bash
# run_random_full_mug.sh — Ayşe 2026-08-04: "random icin bastan sona kos sirayla
# tek trial".
#
# Random baseline, mug hedefi, tüm tıkanma merdiveni sırayla, her aşama 1 trial:
#   none → panels1 → panels2 → panels3 → panels4 → panels5 → panels6 → panels8
#
# run_ladder4.sh her aşamada Gazebo yığınını OCC=<stage> TARGET=mug ile yeniden
# kaldırıyor; burada sadece env veriliyor. Mevcut dosyaların hiçbirine
# dokunulmadı — NEW file.
#
# Not: mug + panels6 kapalı kutu (duvarlar z 0.797-0.987 + alt/üst kapak), kupa
# z 0.850-0.950 → tamamen mühürlü. O aşamanın F1=0 çıkması beklenen sonuç,
# hata değil; merdiven bütünlüğü için yine de koşuluyor.
# panels8 dünyası şu an lshape-BUNNY sürümü (lshape-mug varyantı .bak'ta).
set -u
RH_DIR=/home/ayse/Desktop/RecedingHorizon
LOGS=$RH_DIR/results/_explogs
mkdir -p "$LOGS"

cd "$RH_DIR"
exec env L4_PLANNERS="random" \
         L4_TRIALS=1 \
         L4_TARGET=mug \
         L4_OCCS="none panels1 panels2 panels3 panels4 panels5 panels6 panels8" \
    ./run_ladder4.sh
