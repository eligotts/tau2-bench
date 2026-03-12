"""Entry point: python -m tau2.tui"""

from __future__ import annotations

import argparse
from pathlib import Path

from tau2.generators.depgraph.loaders import load_graph_contract, load_sampling_request


def main() -> None:
    parser = argparse.ArgumentParser(description="tau2 BFS Sampling Explorer TUI")
    parser.add_argument(
        "--domain",
        type=str,
        help="Domain name (looks in data/tau2/domains/<name>/)",
    )
    parser.add_argument("--contract", type=str, help="Path to graph_contract.yaml")
    parser.add_argument("--request", type=str, help="Path to sampling_request.yaml")
    args = parser.parse_args()

    if args.domain:
        # Resolve from repo convention
        repo_root = Path(__file__).resolve().parents[3]
        domain_dir = repo_root / "data" / "tau2" / "domains" / args.domain
        contract_path = domain_dir / "graph_contract.yaml"
        request_path = domain_dir / "sampling_request.yaml"
    elif args.contract and args.request:
        contract_path = Path(args.contract)
        request_path = Path(args.request)
    else:
        parser.error("Provide --domain or both --contract and --request")
        return

    if not contract_path.exists():
        parser.error(f"Contract not found: {contract_path}")
    if not request_path.exists():
        parser.error(f"Request not found: {request_path}")

    contract = load_graph_contract(contract_path)
    request = load_sampling_request(request_path)

    from tau2.tui.app import BFSExplorerApp

    app = BFSExplorerApp(contract, request)
    app.run()


if __name__ == "__main__":
    main()
