"""Build the point-in-time US scheduled-release calendar used by the news-alignment research.

Sources (all free, cited per row):
  ziplime   ZipLime/us-economic-events (Apache-2.0, Hugging Face): 12 release families 2010-01 -> 2026-11 with the
            agency's own scheduled_at and release_at timestamps (embargo lift), read from the official releases.
  xoomar    XOOMAR/us-economic-release-calendar (public domain): FOMC statements 2021+ (scheduled_at UTC).
  fed       federalreserve.gov/monetarypolicy/fomchistoricalYYYY.htm statement links (monetaryYYYYMMDDa.htm) for
            2011-2020; 2010 dates from the 2010 historical page (no statement links there). Statement times varied
            (12:30 / 14:15 ET before 2013, 14:00 ET after), so FOMC rows carry scheduled_time_et = 14:00 with
            time_source "approx" and the research treats FOMC as an afternoon-wide event, never a minute-exact one.
Only the scheduled time is used by any filter (known in advance). release_at is kept for audit.
Output: research/news/official_calendar_2010_2026.csv (committed; data/news/raw holds the downloaded sources).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "news" / "raw"
OUT = ROOT / "research" / "news" / "official_calendar_2010_2026.csv"
ET = "America/New_York"
HIGH = {"Employment Situation", "Consumer Price Index", "Gross Domestic Product", "Personal Income and Outlays",
        "Advance Monthly Sales for Retail and Food Services", "Producer Price Index"}
FOMC_2010 = ["2010-01-27", "2010-03-16", "2010-04-28", "2010-06-23", "2010-08-10", "2010-09-21", "2010-11-03", "2010-12-14"]
FOMC_2011_2020 = """20110126 20110315 20110427 20110622 20110809 20110921 20111102 20111213 20120125 20120313 20120425 20120620
20120801 20120913 20121024 20121212 20130130 20130320 20130501 20130619 20130731 20130918 20131030 20131218 20140129 20140319
20140430 20140618 20140730 20140917 20141029 20141217 20150128 20150318 20150429 20150617 20150729 20150917 20151028 20151216
20160127 20160316 20160427 20160615 20160727 20160921 20161102 20161214 20170201 20170315 20170503 20170614 20170726 20170920
20171101 20171213 20180131 20180321 20180502 20180613 20180801 20180926 20181108 20181219 20190130 20190320 20190501 20190619
20190731 20190918 20191011 20191030 20191211 20200129 20200303 20200315 20200323 20200331 20200429 20200610 20200729 20200827
20200916 20201105 20201216""".split()


def main():
    z = pd.read_parquet(RAW / "ziplime_releases.parquet")
    sched = pd.to_datetime(z["scheduled_at"], utc=True).fillna(pd.to_datetime(z["release_at"], utc=True))
    rows = pd.DataFrame({
        "scheduled_utc": sched, "release_utc": pd.to_datetime(z["release_at"], utc=True),
        "family": z["release_family"], "title": z["release_name"],
        "impact": z["release_name"].map(lambda t: "high" if t in HIGH else "medium"),
        "time_source": z["scheduled_at"].notna().map({True: "scheduled", False: "release"}), "source": "ziplime"})
    x = pd.read_csv(RAW / "us_release_calendar_xoomar.csv")
    x = x[x["event_name"].str.startswith("FOMC Rate Decision")]
    fomc_new = pd.DataFrame({"scheduled_utc": pd.to_datetime(x["scheduled_at"], utc=True), "release_utc": pd.NaT,
                             "family": "FOMC", "title": "FOMC Statement", "impact": "high", "time_source": "scheduled", "source": "xoomar"})
    old = [pd.Timestamp(d).tz_localize(ET).tz_convert("UTC") + pd.Timedelta(hours=14) for d in FOMC_2010] + \
          [pd.Timestamp(f"{d[:4]}-{d[4:6]}-{d[6:]}").tz_localize(ET).tz_convert("UTC") + pd.Timedelta(hours=14) for d in FOMC_2011_2020]
    fomc_old = pd.DataFrame({"scheduled_utc": old, "release_utc": pd.NaT, "family": "FOMC", "title": "FOMC Statement",
                             "impact": "high", "time_source": "approx", "source": "fed"})
    cal = pd.concat([rows, fomc_new, fomc_old], ignore_index=True)
    cal = cal[cal["scheduled_utc"] < pd.Timestamp(2027, 1, 1, tz="UTC")]
    local = cal["scheduled_utc"].dt.tz_convert(ET)
    cal["date_et"] = local.dt.strftime("%Y-%m-%d")
    cal["minute_et"] = local.dt.hour * 60 + local.dt.minute
    cal = cal.drop_duplicates(["family", "scheduled_utc"]).sort_values(["scheduled_utc", "title"]).reset_index(drop=True)
    cal = cal[["date_et", "minute_et", "scheduled_utc", "release_utc", "family", "title", "impact", "time_source", "source"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    cal.to_csv(OUT, index=False)
    print(len(cal), cal.date_et.min(), cal.date_et.max())
    print(cal.groupby("family").size().to_dict())
    print(cal.groupby([cal.family, cal.minute_et]).size().sort_values(ascending=False).head(12).to_dict())


if __name__ == "__main__":
    main()
