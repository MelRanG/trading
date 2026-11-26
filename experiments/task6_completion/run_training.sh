#!/usr/bin/env bash
set -euo pipefail
work=/home/ansy/app/quant-diligence/completion-rd-work
while [ ! -f "$work/model.py" ]; do sleep 1; done
docker run --rm --network=none --name quant-completion-rd-training --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 -e HOME=/work -e PYTHONDONTWRITEBYTECODE=1 -e OMP_NUM_THREADS=2 -v /home/ansy/app/quant-diligence/task6-rd-env:/venv:ro -v "$work:/work" -v "$work:/candidate:ro" -v /home/ansy/app/trading/runtime/task6/worker_train_us:/train:ro -v /home/ansy/app/trading/runtime/task6/evaluator_validation:/validation:ro -v /home/ansy/app/trading/experiments/task6_completion:/code:ro -w /work quant-research-task6:local /venv/bin/python /code/train_rd.py > "$work/training.log" 2>&1
