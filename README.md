# dbt-to-wikijs-docs: Use your dbt documentation in your wiki too

dbt-to-wikijs-docs publishes the documentation of your dbt models to Wiki.js (2.x). It reads the artifacts written by `dbt docs generate` and turns each mart into a wiki page, with its description, columns, and connected tables. In addition, an index page is added for navigating the generated content.

[Wiki.js](https://js.wiki) is an open-source wiki where teams keep their documentation. In many cases, business users read it too. dbt docs, instead, is a separate documentation site built for the data team. The idea of this repository is to make documentation management lightweight, reusing some content of the data documentation in business-oriented documentation.

**Why use it**

- Single source of truth: the yml files contain the documentation, and the wiki follows them on every run.
- Readable for the business: business names and a diagram of related tables, instead of SQL and lineage.
- Safe: it only touches its own pages and never overwrites hand-written ones.
- Easy to adopt: one command in CI.

## Requirements

- Python 3.10 or later, in the environment where dbt runs.
- Wiki.js 2.x, with an API key (Administration > API Access) that can read and write pages under the path prefix, and delete them if you use`--delete-stale` or `--delete-all`.

## Install in a dbt project

As a dependency of the dbt project:
```bash
uv add --dev "dbt-to-wikijs-docs @ git+ssh://git@ssh.andreaconsonni.dev:2222/acc/dbt-to-wikijs-docs.git@v0.1.0"
```

Or run directly without installing (e.g. in CI):
```
uvx --from "git+ssh://git@ssh.andreaconsonni.dev:2222/acc/dbt-to-wikijs-docs.git@v0.1.0" dbt-to-wikijs-docs --help
```

## Usage

**Prerequisites:**
Run `dbt docs generate` first, then run the tool from the dbt project root. If you change your dbt models, re-run `dbt docs generate` before publishing: the tool reads the `target` folder of your dbt project, so otherwise you will publish stale documentation.

**Local preview:**
```bash
dbt-to-wikijs-docs --dry-run docs_preview
```

**Publish**
```
export WIKIJS_URL=<your-wikijs-url>
export WIKIJS_API_KEY=<your-wikijs-api-key>

dbt-to-wikijs-docs
```

`python -m dbt_to_wikijs_docs` works too.

**Delete and Clean**

Only generated pages are ever deleted. Hand-written pages and pages outside the section are never touched. When a model is removed or hidden, its page is kept and reported as `STALE` on every publish.

Delete stale pages:
```bash
dbt-to-wikijs-docs --delete-stale
```
Clear all pages: delete every generated page of the section to clean the wiki. It does not read the dbt artifacts, and publishing again recreates the pages.

```bash
dbt-to-wikijs-docs --delete-all
```
## Documenting models for the wiki

Pages use the dbt yml files. Optional `meta` keys add a business layer on top of the technical descriptions:

```yaml
models:
  - name: fct_sales
    description: One row per order line.     # used when no business_description
    config:
      meta:
        business_name: Sales                 # page title (default: model name)
        business_description: Every item sold, one row per order line.
    columns:
      - name: shop_id
        description: Shop of the sale.
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_shops')
              field: shop_id
      - name: load_id
        config:
          meta:
            hidden: true                     # not shown on the page
```

- `hidden: true` on a model keeps it out of the wiki.
- Tests become plain-language rules: `not_null`, `unique`, `accepted_values` and `relationships`, with their `where` condition if any. 
- `relationships` tests also build the "Connected tables" section and its diagram. A link to a hidden model (e.g. a bridge table) is followed to the visible tables behind it.
- Each folder under `marts-path` becomes a section of the index page.

## Configuration

Settings are read from `[tool.dbt-to-wikijs-docs]` in the dbt project's `pyproject.toml` (or the file given with `--config`). Every key is optional; unknown keys are an error.

```toml
[tool.dbt-to-wikijs-docs]
target-dir = "target"                 # dbt artifacts
marts-path = "models/marts/"          # only models under this folder are published
url = "https://wiki.example.com"      # WIKIJS_URL env var takes precedence
path-prefix = "data-model"            # Wiki.js section path
locale = "en"
tag = "dbt-generated"                 # marks generated pages; untagged pages are never overwritten
delete-stale = false                  # delete the pages of models that no longer exist
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
## Use as a library

```python
from dbt_to_wikijs_docs import Config, DocumentationSite, WikiJsClient, WikiJsPublisher

config = Config.load()
pages = DocumentationSite.from_artifacts(config).pages()

client = WikiJsClient(url, api_key, user_agent=config.user_agent)
report = WikiJsPublisher(
    client, prefix=config.path_prefix, tag=config.tag, locale=config.locale
).publish(pages)

print(report.summary())
```

