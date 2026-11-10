# dplus_6 - does gap alignment carry to the trend sleeves of D+ v2? (pre-registered 2026-11-09, training 2010-23 only; derived from dplus_4/5)

Per sleeve (AG_TRD60_D_1c on MNQ, AG_MES_TRD30_D_1c on MES): split routed trades into gap-aligned (side * own-instrument opening gap >= 0,
dplus_4 definition) vs opposed. State is "real" for a sleeve if: aligned per-trade > opposed per-trade, aligned years>0 >= opposed years>0,
and >= 190/200 random same-count subsets of the sleeve's trades have a lower net than the aligned set.
Sizing cells (post-hoc doubling, exact per dplus_5's engine check): S2 = gap-sized Crabel + 2c on aligned 60m trades; S3 = + 2c on aligned MES
trades; mirror controls double the opposed sets instead. Adopt a sleeve's sizing into ag_arch_d_plus_v2_gapsize (as version 1.1.0, same ledger
name is NOT reused - new ledger `..._gapsize_v2`) only if the state is real for that sleeve AND the cell's net / marked DD > dplus_5 S1's 22.5
AND marked DD < $1,453 AND 1-y breach <= 1 % AND beats its mirror control. Otherwise recorded.
