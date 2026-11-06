<!-- title: Data model -->
> This page is generated automatically from the data warehouse documentation (dbt). Changes made here are overwritten: ask the data team to change the text.
{.is-info}

Business documentation of the data warehouse tables used for reporting.

## Sales

Sales transactions.

| Table | Description |
|---|---|
| [fct_sales](/team/dm/fct_sales) | One row per sale. |

## Core

| Table | Description |
|---|---|
| [dim_products](/team/dm/dim_products) | Products "quoted". |
| [Shops](/team/dm/dim_shops) | Every shop we run. |

## Other

| Table | Description |
|---|---|
| [root_model](/team/dm/root_model) | At root. |

## Warehouse Stock

| Table | Description |
|---|---|
| [fct_stock](/team/dm/fct_stock) | Stock. |
