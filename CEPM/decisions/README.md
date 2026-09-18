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

1. Copy `0000-decision-template.md` to a new file with the next number.
2. Fill in all relevant sections.
3. Where appropriate Open a pull request with the ADR and any related implementation changes.
4. If the decision changes later, add a new ADR instead of rewriting history.

## Status values

Common status values:

- Proposed
- Accepted
- Superseded
- Deprecated

## Relationship to changelog

Almost all decisions should show up, linked, in  [`CEPM/batch-log.md`](CEPM/batch-log.md).