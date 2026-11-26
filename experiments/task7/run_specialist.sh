#!/usr/bin/env bash
set -euo pipefail
engine="$1"
if [ ! -S /tmp/quant-task7.sock ]; then exit 2;fi
work="/home/ansy/app/quant-diligence/task7-$engine-work"
docker run --rm --network=none --name "quant-task7-$engine" --cap-drop=ALL --security-opt no-new-privileges --memory=4g --cpus=2 --pids-limit=256 --user 1000:1000 -e HOME=/work -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONPATH=/original/finrobot_autogen -v "/home/ansy/app/quant-diligence/task7-$engine-env:/venv:ro" -v "$work:/work" -v "/home/ansy/app/quant-diligence/task7-$engine-original:/original:ro" -v /tmp/quant-task7.sock:/relay/model.sock:ro -v /home/ansy/app/trading/experiments/task6:/oldcode:ro -v /home/ansy/app/trading/experiments/task7:/code:ro -w /work quant-research-task6:local sh -c '/venv/bin/python /oldcode/unix_forward.py > /work/forward.log 2>&1 & timeout 750 /venv/bin/python /code/specialist_analysis.py "$1" > /work/analysis.log 2>&1; result=$?; echo "$result" > /work/analysis.exit; exit "$result"' sh "$engine"
