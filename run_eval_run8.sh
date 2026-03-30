#!/bin/bash
# Resilient eval runner for Run 8 — auto-restarts on hangs

OUTPUT_FILE="eval_results_run8.json"
MAX_STALL_SECONDS=720  # 12 minutes with no CPU activity

while true; do
    echo "[$(date)] Starting eval (--resume)..."
    PYTHONUNBUFFERED=1 python3 eval_harness.py --output "$OUTPUT_FILE" --resume &
    EVAL_PID=$!

    STALL_COUNT=0

    while kill -0 $EVAL_PID 2>/dev/null; do
        sleep 30

        CPU=$(ps -p $EVAL_PID -o %cpu= 2>/dev/null | tr -d ' ')
        TCP=$(lsof -p $EVAL_PID 2>/dev/null | grep -c TCP || echo 0)

        if [ "${CPU:-0}" = "0.0" ] && [ "${TCP:-0}" = "0" ]; then
            STALL_COUNT=$((STALL_COUNT + 30))
            echo "[$(date)] Idle: CPU=${CPU}, TCP=${TCP}, stall=${STALL_COUNT}s"
        else
            if [ $STALL_COUNT -gt 0 ]; then
                echo "[$(date)] Resumed: CPU=${CPU}, TCP=${TCP}"
            fi
            STALL_COUNT=0
        fi

        if [ $STALL_COUNT -ge $MAX_STALL_SECONDS ]; then
            echo "[$(date)] STALL DETECTED — killing PID $EVAL_PID"
            kill -9 $EVAL_PID 2>/dev/null
            wait $EVAL_PID 2>/dev/null
            break
        fi
    done

    # Check if all 10 tasks are complete
    if [ -f "$OUTPUT_FILE" ]; then
        COMPLETE=$(python3 -c "
import json
d = json.loads(open('$OUTPUT_FILE').read())
tr = d.get('task_results', {})
done = sum(1 for v in tr.values() if v.get('harness', {}).get('score') is not None)
print(done)
" 2>/dev/null)
        echo "[$(date)] Tasks complete: ${COMPLETE:-0}/10"
        if [ "${COMPLETE:-0}" -ge 10 ]; then
            echo "[$(date)] All tasks done. Exiting."
            break
        fi
    fi

    echo "[$(date)] Restarting in 5s..."
    sleep 5
done
