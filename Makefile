.PHONY: install test ingest-smoke ingest-scale-vectors ingest-scale-vectors-partial-graph corpus-stats backfill-triples serve topics graph-stats graph-gexf eval-retrieval suggest-eval-pmids backfill-articles

# Override: `make ingest-scale-vectors MAX=3000`
MAX ?= 2500

install:
	python3 -m pip install -r requirements.txt

test:
	PYTHONPATH=src python3 -m pytest tests/ -q

ingest-smoke:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers 5 --skip-graph

ingest-scale-vectors:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers $(MAX) --skip-graph

ingest-scale-vectors-partial-graph:
	PYTHONPATH=src python3 scripts/ingest.py --reset --max-papers $(MAX) --max-triple-articles 400

corpus-stats:
	PYTHONPATH=src python3 scripts/corpus_stats.py

LIMIT_TRIPLES ?= 400
backfill-triples:
	PYTHONPATH=src python3 scripts/backfill_triples.py --limit $(LIMIT_TRIPLES)

topics:
	PYTHONPATH=src python3 scripts/topics_fit.py --n-topics 8

graph-stats:
	PYTHONPATH=src python3 scripts/graph_export.py

graph-gexf:
	PYTHONPATH=src python3 scripts/graph_export.py --write-gexf data/kg_graph.gexf

serve:
	PYTHONPATH=src python3 scripts/serve.py

eval-retrieval:
	PYTHONPATH=src python3 scripts/eval_retrieval.py

suggest-eval-pmids:
	PYTHONPATH=src python3 scripts/suggest_eval_pmids.py $(ARGS)

backfill-articles:
	PYTHONPATH=src python3 scripts/backfill_articles_manifest.py
