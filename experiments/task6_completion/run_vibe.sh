#!/usr/bin/env bash
set -euo pipefail
work=/home/ansy/app/quant-diligence/completion-vibe-work
prompt="${1:-prompt.txt}"; stage="${2:-initial}"
if [ -f "$work/$stage.exit" ] && [ "$(cat "$work/$stage.exit")" = "0" ]; then
 cat "$work/$stage.log"; exit 0
fi
if [ ! -S /tmp/quant-task6-completion.sock ]; then
 echo "Research relay is absent; inspect budget/state before restarting it." >&2; exit 2
fi
docker run --rm --network=none --name quant-completion-vibe --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 -e HOME=/work/home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 -e LANGCHAIN_PROVIDER=openai -e LANGCHAIN_MODEL_NAME=gpt-4o -e OPENAI_API_KEY=task6-vibe -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -e VIBE_TRADING_ALLOWED_FILE_ROOTS=/work -e VIBE_TRADING_ALLOWED_RUN_ROOTS=/work -v /home/ansy/app/quant-diligence/vibe-env:/venv:ro -v "$work:/work" -v /tmp/quant-task6-completion.sock:/relay/model.sock:ro -v /home/ansy/app/trading/experiments/task6:/oldcode:ro -w /work quant-research-task6:local sh -c '/venv/bin/python /oldcode/unix_forward.py > /work/forward.log 2>&1 & timeout 650 /venv/bin/vibe-trading -f /work/"$1" --json --max-iter 5 > /work/"$2".log 2>&1; result=$?; echo "$result" > /work/"$2".exit; exit "$result"' sh "$prompt" "$stage"
