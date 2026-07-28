# CEPM Scenarios Changelog

## Banning specific technologies

Simply setting `supplycurve = 0` in the cases file doesn't keep wind and solar from being built,
so we had to implement the technology-specific bans via state policies using the `file_replacement`
case input as follows

`inputs_case/techs_banned.csv << inputs/state_policies/techs_banned_no_new_windsolar.csv`

Note that we also banned all CCS techs because the model wants to build them and that seems
optimistic for a 2032 time horizon.
