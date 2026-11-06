# dbt-to-wikijs-docs

Publish business documentation of dbt models to Wiki.js (2.x), from the
artifacts written by `dbt docs generate`. Standard library only.

## Install in a dbt project

```bash
# as a dev dependency of the dbt project
uv add --dev "dbt-to-wikijs-docs @ git+ssh://git@ssh.andreaconsonni.dev:2222/acc/dbt-to-wikijs-docs.git@v0.1.0"

# or run it without installing (e.g. in CI)
uvx --from "git+ssh://git@ssh.andreaconsonni.dev:2222/acc/dbt-to-wikijs-docs.git@v0.1.0" dbt-to-wikijs-docs --help
```

## Usage

Run from the dbt project root, after `dbt docs generate`:

```bash
# review locally, no network
dbt-to-wikijs-docs --dry-run docs_preview

# publish
WIKIJS_URL=https://wiki.example.com WIKIJS_API_KEY=... dbt-to-wikijs-docs
```

`python -m dbt_to_wikijs_docs` works too.

## Configuration

Settings are read from `[tool.dbt-to-wikijs-docs]` in the dbt project's
`pyproject.toml` (or the file given with `--config`). Every key is optional;
unknown keys are an error.

```toml
[tool.dbt-to-wikijs-docs]
target-dir = "target"                 # dbt artifacts
marts-path = "models/marts/"          # only models under this folder are published
url = "https://wiki.example.com"      # WIKIJS_URL env var takes precedence
path-prefix = "data-model"            # Wiki.js section path
locale = "en"
tag = "dbt-generated"                 # marks generated pages; untagged pages are never overwritten
user-agent = "dbt-to-wikijs-docs"
banner = "> Generated from dbt, do not edit.\n{.is-info}\n"
index-title = "Data model"
index-description = "Business documentation of the data warehouse tables."
index-intro = "Business documentation of the data warehouse tables used for reporting."
kind-order = ["fct_", "dim_"]         # table order inside each index section

# index sections: one per folder under marts-path, shown in this order;
# folders not listed come after, titled from the folder name
[tool.dbt-to-wikijs-docs.areas]
core = { title = "Core", description = "Shared tables used across all reports." }
sales = { title = "Sales", description = "Sales transactions." }
orders = "Orders"                     # title only
```

Command line options override the file: `--config`, `--target-dir`,
`--marts-path`, `--path-prefix`, `--locale`, `--tag`, `--dry-run DIR`.
The API key is only read from `WIKIJS_API_KEY`.

## Development

```bash
uv sync
uv run pytest
uv run ruff check
```
