#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
: "${TEST_DATABASE_URL:?Set isolated legacy PostgreSQL test URL}"
: "${TASK3_STOCK_TEST_DATABASE_URL:?Set isolated stock test URL}"
: "${TASK4_TEST_DATABASE_URL:?Set isolated review test URL}"
: "${TASK4_SOURCE_KR_URL:?Set read-only Task3 source URL for integration verification}"
task4_python="${TASK4_PYTHON:-.venv/bin/python}"
"$task4_python" -m compileall -q src scripts tests
mkdir -p runtime/task4
PYTHONPATH=src PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "$task4_python" -m pytest -o addopts='' -q \
 tests/test_review_self_improvement.py tests/test_equity_pipeline.py tests/test_investment_pipeline.py \
 tests/test_daily_paper_cycle.py tests/test_paper_execution_runtime.py tests/test_paper_decision_preview.py \
 tests/test_paper_execution_safety_gates.py tests/test_v104_end_to_end_causal_challenger_audit.py \
 tests/test_v104_2_jul30_crash_bridge.py tests/test_v84_dual_paper_parity.py tests/test_v89_forward_governance.py \
 tests/test_v85_operational_hardening.py tests/test_v88_order_reconciliation.py tests/test_v101_risk_execution_agent.py \
 tests/test_v102_market_evidence_agent.py tests/test_v103_review_feedback_agent.py tests/test_news_shadow_runtime.py \
 tests/test_rss_news_shadow.py tests/test_alpha_research_factory.py tests/test_alpha_research_factory_completion.py \
 --junitxml=runtime/task4/regression.xml
