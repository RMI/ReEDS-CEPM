# CEPM Errorlog

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

## df_windofs error

recf.py | 2026-07-17 21:43:10 | ERROR | Traceback (most recent call last):
recf.py | 2026-07-17 21:43:10 | ERROR |   File "C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260717_USA_gas\reeds\input_processing\recf.py", line 559, in <module>
recf.py | 2026-07-17 21:43:10 | ERROR | main(reeds_path=reeds_path, inputs_case=inputs_case)
recf.py | 2026-07-17 21:43:10 | ERROR |   File "C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260717_USA_gas\reeds\input_processing\recf.py", line 423, in main
recf.py | 2026-07-17 21:43:10 | ERROR | [df_windons, df_windofs, df_upv, df_distpv]
recf.py | 2026-07-17 21:43:10 | ERROR | UnboundLocalError
recf.py | 2026-07-17 21:43:10 | ERROR | :
recf.py | 2026-07-17 21:43:10 | ERROR | cannot access local variable 'df_windofs' where it is not associated with a value

LLM provided the following diagnosis:

This error is caused by a switch combination that exposes a bug in the current recf script logic.

Root cause:
1. Your case has offshore wind turned off: switches.csv shows GSw_OfsWind = 0.
2. In recf.py, df_windofs is only created inside if int(sw['GSw_OfsWind']) != 0.
3. Later, recf always tries to concatenate df_windofs regardless of that condition at recf.py.
4. So with GSw_OfsWind = 0, df_windofs was never assigned, causing the UnboundLocalError seen in gamslog.txt.

So this is not a bad input file; it is a code path bug triggered by disabling offshore wind. 

If you want, I can patch recf.py so it safely uses an empty dataframe when offshore wind is off and you can keep your no-renewables configuration.

I've accepted this guidance, and rerun the model.

## GAMS failure

I think this one is just a fluke, and I'm going to attempt to rerun.

*** Error: Error when trying to close network session:
Curl error: Could not resolve hostname.
solve.py | 2026-07-20 15:51:22 | ERROR | Traceback (most recent call last):
solve.py | 2026-07-20 15:51:22 | ERROR |   File "C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260717_USA_gas\reeds\core\solve\solve.py", line 176, in <module>
solve.py | 2026-07-20 15:51:22 | ERROR | main(casepath=casepath, t=t, overwrite=overwrite)
solve.py | 2026-07-20 15:51:22 | ERROR |   File "C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260717_USA_gas\reeds\core\solve\solve.py", line 120, in main
solve.py | 2026-07-20 15:51:22 | ERROR | run_reeds(casepath, t, iteration=iteration)
solve.py | 2026-07-20 15:51:22 | ERROR |   File "C:\Users\jsward\Documents\gridmod\ReEDS\runs\v20260717_USA_gas\reeds\core\solve\solve.py", line 62, in run_reeds
solve.py | 2026-07-20 15:51:22 | ERROR | raise Exception(f'3_solve_oneyear.gms failed with return code {result.returncode}')
solve.py | 2026-07-20 15:51:22 | ERROR | Exception
solve.py | 2026-07-20 15:51:22 | ERROR | :
solve.py | 2026-07-20 15:51:22 | ERROR | 3_solve_oneyear.gms failed with return code 7

It was indeed a fluke.

## Offshore Wind RPS target

I've encountered an error that appears associated with the offshore wind policy targets for NY and CT. From Chat:

"I’ve isolated the primary failure (eq_RPS_OFSWind infeasible RHS); I’m now checking your case switches to confirm which policy switch combo is causing that contradiction.

I’ve confirmed the hard failure is an offshore-wind policy constraint (CT and NY) with zero available offshore capacity; I’ll quickly trace where that equation is activated so I can give you the cleanest switch fix."

I've traced this back to a bug in the `file_replacements`, which replaces the default file rather than the case-specific input, and I've edited the underlying code such that the case-specific version of runfiles.csv is used rather than the one stored in the base repo.

## H2 Infeasibility

What appears to be infeasible:

Many constraints force positive hydrogen production in DE in 2032 (for example: gamslog.txt:29414).
In the 2032 listing, regional hydrogen-demand equations for DE are fixed to zero across many timeslices (for example: v20260730_USA_gas_mvp_2032i0.lst:8800).
So the core issue is a contradictory hydrogen condition in 2032 (DE): model is being pushed to produce H2 while corresponding demand balance appears fixed at zero, yielding no feasible solution and therefore no optimal solution.

If you want, I can now trace exactly which switch/input is creating the positive lower bounds on PRODUCE(H2, electrolyzer, ..., DE, 2032) and give a one-line fix path.

Therefore, I'm going to turn off H2.
