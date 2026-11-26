#!/usr/bin/env bash
set -euo pipefail
engine="$1"
stage="${2:-initial}"
case "$stage" in initial) args="";; feedback) args="--feedback";; followup) args="--attempt 1";; model) args="--model-proposal";; *) exit 2;; esac
case "$engine" in quanta|rd) ;; *) exit 2;; esac
work="/home/ansy/app/quant-diligence/task6-$engine-work"
docker run --rm --network=none --name "quant-$engine-native" --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 \
 -e HOME=/work/home -e PATH=/venv/bin:/usr/local/bin:/usr/bin:/bin -e PYTHONDONTWRITEBYTECODE=1 \
 -e OPENAI_API_KEY="task6-$engine" -e OPENAI_BASE_URL=http://127.0.0.1:18080/v1 -e OPENAI_API_BASE=http://127.0.0.1:18080/v1 \
 -e CHAT_MODEL=gpt-4o -e CHAT_STREAM=false -e MAX_RETRY=1 -e RETRY_WAIT_SECONDS=1 \
 -e FACTOR_CoSTEER_DATA_FOLDER=/work/data -e FACTOR_CoSTEER_DATA_FOLDER_DEBUG=/work/data -e FACTOR_CoSTEER_PYTHON_BIN=/venv/bin/python \
 -v "/home/ansy/app/quant-diligence/task6-$engine-env:/venv:ro" -v "$work:/work" \
 -v /home/ansy/app/trading/runtime/task6/relay:/relay:ro -v /home/ansy/app/trading/experiments/task6:/code:ro -w /work quant-research-task6:local \
 sh -c '/venv/bin/python /code/unix_forward.py > /work/model_forward.log 2>&1 & forward=$!; timeout 700 /venv/bin/python /code/native_factor_stage.py "$1" $2 > /work/native_"$3".log 2>&1; result=$?; echo "$result" > /work/native_"$3".exit; kill "$forward"; exit "$result"' sh "$engine" "$args" "$stage"
