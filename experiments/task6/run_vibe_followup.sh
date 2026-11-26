#!/usr/bin/env bash
set -euo pipefail
work=/home/ansy/app/quant-diligence/task6-vibe-work
docker run --rm --network=none --name quant-vibe-followup --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 \
 -e HOME=/work/research-home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 \
 -e LANGCHAIN_PROVIDER=openai -e LANGCHAIN_MODEL_NAME=gpt-4o -e OPENAI_API_KEY=task6-vibe -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -e OPENAI_MODEL=gpt-4o \
 -e VIBE_TRADING_ALLOWED_FILE_ROOTS=/data -e VIBE_TRADING_ALLOWED_RUN_ROOTS=/work \
 -v /home/ansy/app/quant-diligence/vibe-env:/venv:ro -v "$work:/work" -v /home/ansy/app/trading/runtime/task6/worker_train_us:/data:ro \
 -v /home/ansy/app/trading/runtime/task6/relay:/relay:ro -v /home/ansy/app/trading/experiments/task6:/transport:ro -w /work quant-research-task6:local \
 sh -c '/venv/bin/python /transport/unix_forward.py > /work/followup_forward.log 2>&1 & forward=$!; timeout 550 /venv/bin/vibe-trading -f /work/followup_prompt.txt --json --max-iter 3 > /work/followup_ai.log 2>&1; result=$?; echo "$result" > /work/followup_ai.exit; kill "$forward"; exit "$result"'
