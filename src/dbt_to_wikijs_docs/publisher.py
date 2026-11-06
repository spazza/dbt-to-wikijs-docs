"""Publish business documentation of the dbt marts to Wiki.js (2.x).

Reads the artifacts written by `dbt docs generate` (target/manifest.json and,
when present, target/catalog.json), keeps the enabled models under the
marts path (default models/marts/) that are not marked
`meta: {hidden: true}`, and renders one Markdown page per mart plus an index
page, using the business layer in the yml files (`config.meta.business_name` / `business_description`, column
`business_description` and `hidden`), falling back to `description`.

Settings live in the [tool.dbt-to-wikijs-docs] table of the dbt project's
pyproject.toml (see config.py); command line options override them.

Pages are published through the Wiki.js GraphQL API under the path prefix.
Safety rules:
  * every generated page is tagged --tag (default "dbt-generated"); an
    existing page at the same path without that tag was written by hand and
    is never overwritten;
  * a page is only saved when its content changed, so the page history only
    records real documentation changes;
  * nothing is deleted: generated pages that no longer match a mart are
    reported as stale.

Usage (after `dbt docs generate`):
    # review locally, no network
    dbt-to-wikijs-docs --dry-run docs_preview

    # publish (CI step)
    WIKIJS_URL=https://wiki.example.com WIKIJS_API_KEY=... \\
        dbt-to-wikijs-docs

The API key needs read and write access to pages under the path prefix
(Wiki.js: Administration > API Access).
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

from .config import TOOL_NAME, Area, load_config

# --------------------------------------------------------------------------- #
# Reading the dbt artifacts
# --------------------------------------------------------------------------- #


def meta_of(obj):
    """Meta of a node or column: dbt fills both `meta` and `config.meta`."""
    meta = dict((obj.get("config") or {}).get("meta") or {})
    meta.update(obj.get("meta") or {})
    return meta


def ref_name(expression):
    """ "ref('dim_dates')" -> "dim_dates"."""
    match = re.search(r"ref\(\s*['\"]([^'\"]+)['\"]", expression or "")
    return match.group(1) if match else None


def load_project(target_dir, marts_path):
    manifest = json.loads((target_dir / "manifest.json").read_text())
    catalog_path = target_dir / "catalog.json"
    catalog = json.loads(catalog_path.read_text()) if catalog_path.exists() else {"nodes": {}}

    models = {
        node["name"]: node
        for node in manifest["nodes"].values()
        if node["resource_type"] == "model" and node["original_file_path"].replace("\\", "/").startswith(marts_path)
    }

    # generic tests, grouped by the model they are attached to
    tests = defaultdict(list)
    for node in manifest["nodes"].values():
        if node["resource_type"] != "test" or not node.get("test_metadata"):
            continue
        attached = node.get("attached_node")
        if not attached:
            continue
        model_name = attached.split(".")[-1]
        if model_name in models:
            tests[model_name].append(node)

    return manifest, catalog, models, tests


def column_types(catalog, node):
    columns = (catalog.get("nodes", {}).get(node["unique_id"]) or {}).get("columns", {})
    return {name.lower(): col for name, col in columns.items()}


# --------------------------------------------------------------------------- #
# Turning tests into plain language
# --------------------------------------------------------------------------- #


def rule_text(test, models):
    name = test["test_metadata"]["name"]
    kwargs = test["test_metadata"].get("kwargs") or {}
    where = (test.get("config") or {}).get("where")
    if name == "not_null":
        text = "Always filled"
    elif name == "unique":
        text = "Unique"
    elif name == "accepted_values":
        values = kwargs.get("values") or []
        text = "One of: " + ", ".join(str(v) for v in values)
    elif name == "relationships":
        target = ref_name(kwargs.get("to"))
        text = f"Links to {title_of(models.get(target), target)}"
    else:
        return None
    if where:
        text += f" (when {where})"
    return text


def title_of(node, fallback):
    if not node:
        return fallback
    return meta_of(node).get("business_name") or node["name"]


def is_hidden(node):
    return bool(meta_of(node).get("hidden"))


def relationship_edges(models, tests):
    """Visible model -> visible model edges, followed through hidden models.

    Returns {source: [(target, via_column, through_model_or_None)]}.
    """
    direct = defaultdict(list)
    for model_name, model_tests in tests.items():
        for test in model_tests:
            if test["test_metadata"]["name"] != "relationships":
                continue
            target = ref_name((test["test_metadata"].get("kwargs") or {}).get("to"))
            if target in models and target != model_name:
                direct[model_name].append((target, test.get("column_name")))

    edges = defaultdict(list)
    for source, links in direct.items():
        if is_hidden(models[source]):
            continue
        for target, column in links:
            if not is_hidden(models[target]):
                edges[source].append((target, column, None))
                continue
            # one hop through a hidden link table (e.g. a many-to-many bridge)
            for next_target, _ in direct.get(target, []):
                if not is_hidden(models[next_target]) and next_target != source:
                    edges[source].append((next_target, column, target))
    return edges


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #


def cell(text):
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def first_sentence(text, limit=250):
    text = " ".join((text or "").split())
    match = re.match(r"(.+?[.!?])(\s|$)", text)
    sentence = match.group(1) if match else text
    return sentence if len(sentence) <= limit else sentence[: limit - 1] + "…"


def model_description(node):
    return " ".join((meta_of(node).get("business_description") or node.get("description") or "").split())


def page_path(prefix, model_name):
    return f"{prefix}/{model_name}"


def link(prefix, models, name):
    return f"[{title_of(models[name], name)}](/{page_path(prefix, name)})"


def mermaid_id(name):
    return re.sub(r"\W", "_", name)


def mermaid_label(models, name):
    return title_of(models[name], name).replace('"', "'")


def render_model(node, models, tests, edges, incoming, catalog, config):
    name = node["name"]
    prefix = config.path_prefix
    out = [config.banner, model_description(node), ""]

    out += ["## Overview", "", "| | |", "|---|---|"]
    out.append(f"| Table in the data warehouse | `{node['schema']}.{node['alias'] or name}` |")
    for test in tests.get(name, []):
        if test["test_metadata"]["name"] == "unique_combination_of_columns" and not test.get("column_name"):
            cols = (test["test_metadata"].get("kwargs") or {}).get("combination_of_columns") or []
            out.append(f"| Each row is unique by | {', '.join(f'`{c}`' for c in cols)} |")
    out.append("")

    outgoing = edges.get(name, [])
    used_by = incoming.get(name, [])
    if outgoing or used_by:
        out += ["## Connected tables", ""]

        def visible_column(column):
            spec = node["columns"].get(column or "", {})
            return column and not is_hidden(spec)

        for target, column, through in outgoing:
            via = f" through `{column}`" if visible_column(column) else ""
            if through:
                via += f" (via the link table `{through}`)"
            out.append(f"- **{link(prefix, models, target)}**{via}")
        for source, _column, through in used_by:
            via = f" (via the link table `{through}`)" if through else ""
            out.append(f"- Used by **{link(prefix, models, source)}**{via}")
        out += ["", "```mermaid", "graph LR"]
        me = mermaid_id(name)
        out.append(f'  {me}["{mermaid_label(models, name)}"]')
        seen = set()
        for target, _, _ in outgoing:
            if ("out", target) not in seen:
                seen.add(("out", target))
                out.append(f'  {me} --> {mermaid_id(target)}["{mermaid_label(models, target)}"]')
        for source, _, _ in used_by:
            if ("in", source) not in seen:
                seen.add(("in", source))
                out.append(f'  {mermaid_id(source)}["{mermaid_label(models, source)}"] --> {me}')
        out += ["```", ""]

    # columns: database order when the catalog is available, yml order otherwise
    types = column_types(catalog, node)
    documented = {c.lower(): c for c in node.get("columns", {})}
    # database order from the catalog, then any documented column the catalog
    # does not know yet (e.g. a stale catalog), so no documented column is lost
    ordered = sorted(types, key=lambda c: types[c].get("index", 0))
    ordered += [c for c in documented if c not in types]
    rules = defaultdict(list)
    for test in tests.get(name, []):
        column = (test.get("column_name") or "").lower()
        text = rule_text(test, models)
        if column and text:
            rules[column].append(text)

    rows = []
    for column in ordered:
        spec = node["columns"].get(documented.get(column, column), {})
        if is_hidden(spec):
            continue
        description = meta_of(spec).get("business_description") or spec.get("description") or ""
        shown_name = (types.get(column) or {}).get("name") or spec.get("name") or column
        col_type = (types.get(column) or {}).get("type", "")
        rows.append(
            f"| `{cell(shown_name)}` | {cell(' '.join(description.split()))} | {cell(col_type)} | {cell('; '.join(rules.get(column, [])))} |"
        )
    if rows:
        out += ["## Columns", "", "| Column | Description | Type | Rules |", "|---|---|---|---|"]
        out += rows
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def area_of(node, marts_path):
    """Folder right under the marts path (e.g. "core", "sales")."""
    relative = node["original_file_path"].replace("\\", "/")[len(marts_path) :]
    parts = relative.split("/")
    return parts[0] if len(parts) > 1 else "other"


def area_sort_key(areas, area):
    # configured areas in their order, then the rest alphabetically
    known = list(areas)
    return (known.index(area) if area in known else len(known), area)


def table_sort_key(models, kind_order, name):
    kind = next((i for i, prefix_ in enumerate(kind_order) if name.startswith(prefix_)), len(kind_order))
    return (kind, title_of(models[name], name).lower())


def render_index(visible, models, config):
    out = [config.banner, config.index_intro, ""]
    by_area = defaultdict(list)
    for name in visible:
        by_area[area_of(models[name], config.marts_path)].append(name)
    for area in sorted(by_area, key=lambda a: area_sort_key(config.areas, a)):
        section = config.areas.get(area) or Area(area.replace("_", " ").title())
        out += [f"## {section.title}", ""]
        if section.description:
            out += [section.description, ""]
        out += ["| Table | Description |", "|---|---|"]
        for name in sorted(by_area[area], key=lambda n: table_sort_key(models, config.kind_order, n)):
            out.append(
                f"| {link(config.path_prefix, models, name)} | {cell(first_sentence(model_description(models[name])))} |"
            )
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# Wiki.js GraphQL client
# --------------------------------------------------------------------------- #


class WikiJs:
    def __init__(self, url, api_key, user_agent):
        self.endpoint = url.rstrip("/") + "/graphql"
        self.api_key = api_key
        self.user_agent = user_agent

    def call(self, query, variables=None):
        body = json.dumps({"query": query, "variables": variables or {}}).encode()
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                # Cloudflare's Browser Integrity Check rejects urllib's default
                # "Python-urllib/3.x" signature (HTTP 403, error code 1010)
                "User-Agent": self.user_agent,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as error:
            raise SystemExit(f"Wiki.js HTTP {error.code}: {error.read().decode(errors='replace')[:500]}") from None
        if payload.get("errors"):
            raise SystemExit(f"Wiki.js GraphQL error: {payload['errors']}")
        return payload["data"]

    def list_pages(self, locale):
        data = self.call(
            "query ($locale: String) { pages { list(locale: $locale, limit: 100000) { id path tags } } }",
            {"locale": locale},
        )
        return {page["path"]: page for page in data["pages"]["list"]}

    def page_content(self, page_id):
        data = self.call(
            "query ($id: Int!) { pages { single(id: $id) { content title description } } }", {"id": page_id}
        )
        return data["pages"]["single"]

    @staticmethod
    def check(result, action, path):
        status = result["responseResult"]
        if not status["succeeded"]:
            raise SystemExit(f"Wiki.js refused to {action} {path}: {status['message']} ({status['errorCode']})")

    def create(self, path, title, description, content, tags, locale):
        data = self.call(
            """mutation ($content: String!, $description: String!, $path: String!, $title: String!,
                         $tags: [String]!, $locale: String!) {
                 pages { create(content: $content, description: $description, editor: "markdown",
                                isPublished: true, isPrivate: false, locale: $locale, path: $path,
                                tags: $tags, title: $title) {
                   responseResult { succeeded errorCode slug message } } } }""",
            {
                "content": content,
                "description": description,
                "path": path,
                "title": title,
                "tags": tags,
                "locale": locale,
            },
        )
        self.check(data["pages"]["create"], "create", path)

    def update(self, page_id, path, title, description, content, tags):
        data = self.call(
            """mutation ($id: Int!, $content: String!, $description: String!, $title: String!, $tags: [String]!) {
                 pages { update(id: $id, content: $content, description: $description, editor: "markdown",
                                isPublished: true, tags: $tags, title: $title) {
                   responseResult { succeeded errorCode slug message } } } }""",
            {"id": page_id, "content": content, "description": description, "title": title, "tags": tags},
        )
        self.check(data["pages"]["update"], "update", path)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(__doc__ or "").split("\n\n")[0],
        epilog=f"Defaults come from [tool.{TOOL_NAME}] in pyproject.toml; options given here override them.",
    )
    parser.add_argument("--config", type=Path, help="pyproject.toml to read settings from (default: ./pyproject.toml)")
    parser.add_argument("--target-dir", type=Path, help="dbt target directory (default: target)")
    parser.add_argument("--marts-path", help="folder of the documented models (default: models/marts/)")
    parser.add_argument("--path-prefix", help="Wiki.js path of the section (default: data-model)")
    parser.add_argument("--locale", help="Wiki.js locale (default: en)")
    parser.add_argument("--tag", help="tag marking generated pages (default: dbt-generated)")
    parser.add_argument(
        "--dry-run", metavar="DIR", type=Path, help="write the Markdown pages to DIR instead of publishing"
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config = load_config(
        args.config,
        {
            "target_dir": args.target_dir,
            "marts_path": args.marts_path,
            "path_prefix": args.path_prefix,
            "locale": args.locale,
            "tag": args.tag,
        },
    )
    prefix = config.path_prefix

    _, catalog, models, tests = load_project(config.target_dir, config.marts_path)
    visible = [name for name, node in models.items() if not is_hidden(node)]
    edges = relationship_edges(models, tests)
    incoming = defaultdict(list)
    for source, links in edges.items():
        for target, column, through in links:
            incoming[target].append((source, column, through))

    pages = {}
    for name in sorted(visible):
        node = models[name]
        content = render_model(node, models, tests, edges, incoming, catalog, config)
        pages[page_path(prefix, name)] = (title_of(node, name), first_sentence(model_description(node)), content)
    pages[prefix] = (config.index_title, config.index_description, render_index(visible, models, config))

    if args.dry_run:
        for path, (title, _, content) in pages.items():
            file = args.dry_run / f"{path}.md"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(f"<!-- title: {title} -->\n{content}")
        print(f"Wrote {len(pages)} pages to {args.dry_run}/{prefix}")
        return 0

    url, api_key = os.environ.get("WIKIJS_URL") or config.url, os.environ.get("WIKIJS_API_KEY")
    if not url or not api_key:
        raise SystemExit("Set WIKIJS_URL (or `url` in the config) and WIKIJS_API_KEY, or use --dry-run.")
    wiki = WikiJs(url, api_key, config.user_agent)
    existing = wiki.list_pages(config.locale)

    created = updated = unchanged = skipped = 0
    for path, (title, description, content) in pages.items():
        page = existing.get(path)
        tags = [config.tag]
        if page is None:
            wiki.create(path, title, description, content, tags, config.locale)
            created += 1
            print(f"created   {path}")
        elif config.tag not in (page.get("tags") or []):
            skipped += 1
            print(
                f"SKIPPED   {path}: an existing page without the '{config.tag}' tag (written by hand) is never overwritten"
            )
        else:
            current = wiki.page_content(page["id"])
            if (current["content"], current["title"], current["description"]) == (content, title, description):
                unchanged += 1
                continue
            wiki.update(page["id"], path, title, description, content, tags)
            updated += 1
            print(f"updated   {path}")

    stale = sorted(
        path
        for path, page in existing.items()
        if config.tag in (page.get("tags") or []) and path.startswith(prefix + "/") and path not in pages
    )
    for path in stale:
        print(f"STALE     {path}: generated earlier but no longer a mart; delete it in Wiki.js if not needed")

    print(f"Done: {created} created, {updated} updated, {unchanged} unchanged, {skipped} skipped, {len(stale)} stale.")
    return 0
