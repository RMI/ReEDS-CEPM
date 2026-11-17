# Decision Record 20260929: State regions

Status: APPROVED

## Context and Problem Statement

ReEDS has several options for regions of analysis that may or may not break regions out on state lines. However, our forecast of data center demand doesn't get any more granular than the state-level. Presently, if ReEDS includes any portion of a state in its run and includes forecasted data center demand, it will apply the entire state's data center to demand to that portion. To address this, we need to either maek our data center forecasts more flexible or enforce state region boundaries in our CEPM runs.

## Decision Outcome

Going forward, we'll set regions for CEPM runs at state outlines. States can be subdivided into multiple regions, each included state must be whole and its outline must be intact.

## Caveats, issues, or further investigation or analysis to do.

- State outlines and electric system outlines don't necessarily overlap (e.g.,) one state may be in multiple interconnections or RTOs.
- If needed, we could weight the state-level DC projections by load and apply to a more granular region set like z90. At this point, we don't think that step is needed.

## Checklist

- [X] I linked to any analysis I did here.
- [ ] I included a link to this doc in my batch-log entry.