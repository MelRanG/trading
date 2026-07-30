#!/bin/sh
set -eu
mkdir -p data/runtime reports
if [ "${V85_RUN_ON_START:-false}" = "true" ]; then
  python scripts/run_v85_operating_day.py || true
fi
if [ "${V89_GOVERNANCE_CHECK_ON_START:-true}" = "true" ]; then
  python scripts/run_v89_forward_governance.py || true
fi
exec python scripts/serve_v86_control_plane.py --host 0.0.0.0 --port 8788
