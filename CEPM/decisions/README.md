# Decision record

This directory contains decision records for the CEPM project. They're roughly based on the Architectural Decision Record concept.

## What is a decision record?

A decision record is a short Markdown document that captures an important model decision, why it was made, and its consequences.

## Naming convention

Use numeric prefixes so records stay in chronological order:

- `20260903-short-title.md`
- `20260903.1-short-title.md`
- `20260904-short-title.md`
- ...

## Process

1. Copy `202XXXXX-decision-template.md` to `YYYYMMDD-short-title.md`.
2. Fill in all relevant sections.
3. Where appropriate Open a pull request with the ADR and any related implementation changes.
4. If the decision changes later, add a new ADR instead of rewriting history.

## Status values

Use one of the values on the template's STATUS line:

- Not active
- Under investigation
- In progress
- Complete

## Relationship to changelog

Almost all decisions should show up, linked, in  [`CEPM/batch-log.md`](../batch-log.md).