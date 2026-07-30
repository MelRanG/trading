from pathlib import Path
import argparse

from quant_harness.v86_control_plane_dashboard import run_server

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    args = parser.parse_args()
    run_server(Path(args.root), host=args.host, port=args.port)
