"""Where the generated pages live in Wiki.js, and links between them."""

from dbt_to_wikijs_docs.dbt import DbtProject


class WikiLinks:
    """Wiki paths of the generated pages under the configured prefix."""

    def __init__(self, prefix: str, project: DbtProject) -> None:
        """Place the pages of `project` under `prefix`."""
        self._prefix = prefix
        self._project = project

    @property
    def index_path(self) -> str:
        """Path of the index page."""
        return self._prefix

    def path_of(self, model_name: str) -> str:
        """Return the path of a model page."""
        return f"{self._prefix}/{model_name}"

    def link_to(self, model_name: str) -> str:
        """Return a Markdown link to a model page, labelled with its business name."""
        return f"[{self._project.title_of(model_name)}](/{self.path_of(model_name)})"
