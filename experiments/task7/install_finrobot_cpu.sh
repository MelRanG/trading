#!/usr/bin/env bash
set -euo pipefail
docker run --rm --name quant-task7-install-finrobot-cpu --memory=4g --cpus=2 --user 1000:1000 -e HOME=/work -v /home/ansy/app/quant-diligence/task7-finrobot-env:/venv -v /home/ansy/app/quant-diligence/task7-finrobot-work:/work -w /work quant-research-task6:local sh -c '
/venv/bin/pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
printf "torch==2.8.0+cpu\n" > /work/cpu_constraint.txt
/venv/bin/pip install -c /work/cpu_constraint.txt "pyautogen[retrievechat]==0.2.35" ipython finnhub-python yfinance mplfinance backtrader sec_api pandas PyPDF2 reportlab praw tushare pandas_datareader pdfkit ratelimit nltk
/venv/bin/pip check
/venv/bin/pip freeze > /work/environment.lock
'
