from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
        env_file=_project_root() / ".env",
    )

    ncbi_email: str = ""
    ncbi_api_key: Optional[str] = None

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_temperature: float = 0.0

    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    retrieval_top_k: int = 40
    rerank_top_k: int = 12
    use_cross_encoder_rerank: bool = True
    cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    use_hybrid_retrieval: bool = True
    rrf_k: int = 60

    graph_expand_entities: bool = True
    graph_expand_max_extra_triples: int = 80

    default_ingest_max_papers: int = 2500

    data_dir: Path = Path("data")
    chroma_collection: str = "pubmed_chunks"

    default_pubmed_query: str = (
        '("GLP-1"[Title/Abstract] OR "GLP1"[Title/Abstract] OR semaglutide[Title/Abstract] '
        'OR liraglutide[Title/Abstract] OR tirzepatide[Title/Abstract]) '
        'AND ("type 2 diabetes"[Title/Abstract] OR T2DM[Title/Abstract] OR obesity[Title/Abstract])'
    )

    @property
    def chroma_path(self) -> Path:
        root = _project_root()
        p = self.data_dir if self.data_dir.is_absolute() else root / self.data_dir
        return p / "chroma"

    @property
    def triples_path(self) -> Path:
        root = _project_root()
        p = self.data_dir if self.data_dir.is_absolute() else root / self.data_dir
        return p / "triples.jsonl"

    @property
    def articles_manifest_path(self) -> Path:
        """Merged PMID → title/abstract for topic modeling (see scripts/topics_fit.py)."""
        root = _project_root()
        p = self.data_dir if self.data_dir.is_absolute() else root / self.data_dir
        return p / "articles.jsonl"

    @property
    def topic_model_path(self) -> Path:
        """LDA output from scripts/topics_fit.py; optional enrichment for top_passages."""
        root = _project_root()
        p = self.data_dir if self.data_dir.is_absolute() else root / self.data_dir
        return p / "topic_model.json"


def get_settings() -> Settings:
    return Settings()
