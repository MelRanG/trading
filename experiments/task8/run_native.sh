#!/usr/bin/env bash
# Pinned existing Vibe environment; no credentials, DB, broker or network mount.
set -euo pipefail
kind="${1:?earnings or portfolio}";work=/home/ansy/app/quant-diligence/task8-vibe-work
case "$kind" in
 earnings) script=/work/component.py;artifact=earnings_component.json ;;
 portfolio) script=/code/native_portfolio.py;artifact=native_portfolio.json ;;
 *) exit 2 ;;
esac
if [ -f "$work/$artifact" ]; then printf 'Frozen native artifact already exists: %s\n' "$artifact";exit 0;fi
if [ "$kind" = earnings ] && [ ! -S /tmp/quant-task8.sock ];then printf 'Start the bounded Task8 model relay before fresh inference.\n';exit 2;fi
args=(--rm --network=none --cap-drop=ALL --security-opt no-new-privileges --memory=3g --cpus=2 --pids-limit=256 --user 1000:1000 -e HOME=/work/home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 -v /home/ansy/app/quant-diligence/vibe-env:/venv:ro -v "$work:/work" -v /home/ansy/app/trading/runtime/task8:/evidence:ro -v /home/ansy/app/trading/experiments/task8:/code:ro -w /work)
if [ "$kind" = earnings ];then
 args+=(-e LANGCHAIN_PROVIDER=openai -e LANGCHAIN_MODEL_NAME=gpt-4o -e OPENAI_API_KEY=task6-vibe -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -v /tmp/quant-task8.sock:/relay/model.sock:ro -v /home/ansy/app/trading/experiments/task6:/oldcode:ro)
 docker run "${args[@]}" quant-research-task6:local sh -c '/venv/bin/python /oldcode/unix_forward.py > /work/forward.log 2>&1 & /venv/bin/python /work/component.py'
else
 docker run "${args[@]}" quant-research-task6:local /venv/bin/python "$script"
fi
