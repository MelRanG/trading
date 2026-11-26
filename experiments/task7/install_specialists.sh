#!/usr/bin/env bash
set -euo pipefail
engine="$1"; env="/home/ansy/app/quant-diligence/task7-$engine-env"; work="/home/ansy/app/quant-diligence/task7-$engine-work"
docker run --rm --name "quant-task7-install-$engine" --memory=4g --cpus=2 --user 1000:1000 -e HOME=/work -v "$env:/venv" -v "$work:/work" -v "/home/ansy/app/quant-diligence/task7-$engine-original:/original:ro" -w /work quant-research-task6:local sh -c '
python -m venv /venv
if [ "$1" = tradingagents ]; then
 cp -a /original /work/build-source
 /venv/bin/pip install /work/build-source
else
 /venv/bin/pip install "pyautogen[retrievechat]==0.2.35" ipython finnhub-python yfinance mplfinance backtrader sec_api pandas PyPDF2 reportlab praw tushare pandas_datareader pdfkit ratelimit nltk
fi
/venv/bin/pip check
/venv/bin/pip freeze > /work/environment.lock
' sh "$engine"
