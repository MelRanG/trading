#!/usr/bin/env bash
set -euo pipefail
engine="$1"; script="$2"
work="/home/ansy/app/quant-diligence/completion-$engine-work"
env="/home/ansy/app/quant-diligence/task6-$engine-env"
if [ ! -S /tmp/quant-task6-completion.sock ]; then
 echo "Research relay is absent; inspect budget/state before restarting it." >&2; exit 2
fi
docker run --rm --network=none --name "quant-completion-$engine" --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 \
 -e HOME=/work/home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 -e OPENAI_API_KEY="task6-$engine" -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -e OPENAI_API_BASE=http://127.0.0.1:18080/v1 -e CHAT_MODEL=gpt-4o -e CHAT_STREAM=false -e MAX_RETRY=1 -e RETRY_WAIT_SECONDS=1 \
 -v "$env:/venv:ro" -v "$work:/work" -v /tmp/quant-task6-completion.sock:/relay/model.sock:ro -v /home/ansy/app/trading/experiments/task6:/oldcode:ro -v /home/ansy/app/trading/experiments/task6_completion:/code:ro -w /work quant-research-task6:local \
 sh -c '/venv/bin/python /oldcode/unix_forward.py > /work/forward.log 2>&1 & timeout 1700 /venv/bin/python /code/"$1" > /work/run.log 2>&1; result=$?; echo "$result" > /work/run.exit; exit "$result"' sh "$script"
