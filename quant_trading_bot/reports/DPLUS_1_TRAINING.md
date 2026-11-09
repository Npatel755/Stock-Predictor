# dplus_1 — robustness of the Architecture D+ challenger inside training (2010–23 only)

Protocol: research/dplus_1/PROTOCOL.md (pre-registered). Script: scripts/dplus_1_pilot.py → reports/DPLUS_1_TRAINING.json. Fixed engine, no deployed
parameter changed. 2024–26 not loaded.

| gate | result | pass |
|---|---|---|
| marked DD of ag_arch_d_plus alone (stops assumed hit) | **$1,768** (2023-04-13), 0 touches of $2k / $2.5k | yes |
| Crabel min_range plateau (10 / 20 vs 15) | 97.8 % / 99.4 % of the net at 15; all six values +7.8–8.2k, closed DD 412–453 | yes |
| expanding-window prospective min_range (2013–23) | picks 15 → 25, prospective +8,324 vs fixed-15 +8,186 (ratio 1.02) | yes |

Ablation under the strict router (full: +20,723 / 1,968 trades / closed DD 1,654 / marked 1,768 / 12 of 14 years):

| drop | net | trades | closed DD | marked DD | $2k touches | years + |
|---|---:|---:|---:|---:|---:|---:|
| Crabel 15m | 14,934 | 1,764 | 2,529 | 2,679 | 2 | 11 |
| **MNQ 30m trend** | **17,576** | 1,398 | **783** | **882** | 0 | 12 |
| MNQ 60m trend | 15,328 | 1,419 | 966 | 1,080 | 0 | 12 |
| MES 30m trend | 18,615 | 1,790 | 1,589 | 1,702 | 0 | 12 |

Reading: the min_range knob is a plateau, not a spike (the Crabel sleeve's edge is the open-drive itself; min_range only trims trades). The Crabel sleeve
is what holds the drawdown down (dropping it doubles the DD). The MNQ 30m trend sleeve adds +3,147 of net but **more than doubles the drawdown**
(783 → 1,654 closed, 882 → 1,768 marked): it is the same EWMA-trend family as the 60m sleeve, enters first under the router and blocks the 60m's
decisions. Pre-registered follow-up: dplus_2 (derived; D+ without the 30m trend sleeve, with count-matched random-removal placebos). Verdict this round:
all gates pass → ag_arch_d_plus stays a challenger ledger, staging-eligible on marked DD; nothing changed on paper.
