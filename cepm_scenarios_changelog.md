# CEPM Scenarios Changelog

## Cendiv error

--- >> cendivweights.csv(1) 97 Mb 2 Errors
*** Error 170 in C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260716_WECC_optimized\inputs_case\cendivweights.csv
    Domain violation for element
*** Error 170 in C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260716_WECC_optimized\inputs_case\cendivweights.csv
    Domain violation for element

Unfortunately, it appears that I canno't in fact run planning regions individually (i.e., transreg/WestConnect), so perhpas let's attempt a couple of things:

- Nation-wide run at a state-level resolution.
- WECC run at a z132-level resolution (default).

Of course, this would require us to rethink post-processing.

### Test results

Confusingly, it appears that the cendiv error persists with the interconnect/western run, which I had not anticipated,
so I think I will submit an issue in ReEDS, but the nation-wide state-level resolution run completed without incident
in under 3h, so I think that might be a better solution to our problem especicially since then I think we can simply maintain all data inputs at the state level.