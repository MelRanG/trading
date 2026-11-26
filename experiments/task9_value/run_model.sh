#!/usr/bin/env bash
set -euo pipefail
stage="$1"; scope="$2"; if [ "$stage" = deep2_2023 ]; then printf "Request needs bounded compaction before third deep call\n"; exit 1; fi; work=/home/ansy/app/quant-diligence/task9-value-work
if [ -f "$work/$stage.json" ];then printf 'Frozen output exists: %s\n' "$stage";exit 0;fi
[ -S /tmp/quant-task9-value.sock ]
docker run --rm --network=none --name "quant-value-$stage" --cap-drop=ALL --security-opt no-new-privileges --memory=3g --cpus=2 --pids-limit=256 --user 1000:1000 -e HOME=/work/home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 -e LANGCHAIN_PROVIDER=openai -e LANGCHAIN_MODEL_NAME=gpt-4o -e OPENAI_API_KEY="task6-$scope" -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -v /home/ansy/app/quant-diligence/vibe-env:/venv:ro -v "$work:/work" -v /tmp/quant-task9-value.sock:/relay/model.sock:ro -v /home/ansy/app/trading/experiments/task6:/oldcode:ro -v /home/ansy/app/trading/experiments/task8b:/component:ro -w /work quant-research-task6:local sh -c '/venv/bin/python /oldcode/unix_forward.py > /work/forward.log 2>&1 & /venv/bin/python /component/model_worker.py "$1"' sh "$stage"
