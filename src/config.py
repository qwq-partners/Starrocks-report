"""Configuration loader for the daily practices collector."""

from pathlib import Path

import yaml


def load_yaml(path: str | Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


class Config:
    def __init__(self, config_dir: str | Path = "config"):
        config_dir = Path(config_dir)
        self.app = load_yaml(config_dir / "config.yaml")
        self.keywords = load_yaml(config_dir / "keywords.yaml")
        self.sources = load_yaml(config_dir / "sources.yaml")

    @property
    def all_keywords(self) -> list[str]:
        """Get flattened list of all positive keywords."""
        keywords = []
        for group in ["primary", "secondary", "tertiary", "enterprise"]:
            keywords.extend(self.keywords.get(group, []))
        return keywords

    @property
    def negative_keywords(self) -> list[str]:
        return self.keywords.get("negative", [])

    @property
    def db_path(self) -> str:
        return self.app["storage"]["db_path"]

    @property
    def report_output_dir(self) -> str:
        return self.app["report"]["output_dir"]

    @property
    def lookback_hours(self) -> int:
        return self.app["collection"]["lookback_hours"]

    @property
    def max_items_per_source(self) -> int:
        return self.app["collection"]["max_items_per_source"]

    @property
    def rate_limit_delay(self) -> float:
        return self.app["collection"]["rate_limit_delay"]

    @property
    def llm_model(self) -> str:
        return self.app["enrichment"]["llm_model"]

    @property
    def max_articles_to_summarize(self) -> int:
        return self.app["enrichment"]["max_articles_to_summarize"]
