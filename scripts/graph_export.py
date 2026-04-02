#!/usr/bin/env python3
"""Load triples.jsonl, print graph stats, optionally export GEXF for Gephi/Cytoscape."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biomed_rag.config import get_settings
from biomed_rag.knowledge_graph import build_networkx, graph_summary, load_all_triples


def main() -> None:
    p = argparse.ArgumentParser(description="KG stats + GEXF export")
    p.add_argument(
        "--write-gexf",
        type=str,
        default=None,
        metavar="PATH",
        help="Optional: write graph to PATH (e.g. data/kg_graph.gexf)",
    )
    args = p.parse_args()
    settings = get_settings()
    path = settings.triples_path
    if not path.exists():
        print(f"No triples at {path}. Ingest with graph extraction enabled.", file=sys.stderr)
        sys.exit(1)

    triples = load_all_triples(path)
    g = build_networkx(triples)
    summ = graph_summary(g)
    print(json.dumps(summ, indent=2))
    print("Triples (records):", len(triples))

    if args.write_gexf:
        import networkx as nx

        out = Path(args.write_gexf)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        nx.write_gexf(g, out)
        print("Wrote", out)


if __name__ == "__main__":
    main()
