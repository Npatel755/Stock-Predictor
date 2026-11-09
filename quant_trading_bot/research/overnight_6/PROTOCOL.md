# overnight_6 — Sunday split and pre-FOMC drift for the overnight book (pre-registered 2026-11-09; training 2010-2023; 2024-26 sealed)

Champion: overnight_dip_v2 (+11,797 / 490 nights / DD 1,646 on training). Two questions, no parameter tuning:
 S1 v2 on Sunday nights only   S2 v2 on weekday nights only   (is the edge a weekend-gap effect or a general reopen effect?)
 F3 unconditional long MNQ 18:05 -> 09:45 on the night before every FOMC decision day (Lucca-Moench pre-announcement drift; 8/yr; calendar is point-in-time)
 F4 v2 nights UNION pre-FOMC nights (one position per night; v2 rule unchanged on other nights)
Gates: S1/S2 informational (reported with per-night t). F3 is a new sleeve: net > 0, >= 10 of 14 years, t >= 2, 200 same-count random-night placebos >= 190.
F4 replaces v2 only if net > champion, >= 12 positive years, DD <= champion DD, per-night >= champion. Multiplicity: 4 trials (104 in the overnight family).
Promotion at Devin's discretion (Nick 2026-11-09) if the gates hold; 2024-26 never scored.
