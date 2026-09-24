"""Option 2 updater: no LLM. Fetches World Bank annual, preserves monthly, writes rule-based summary.
Runs in GitHub Actions (free) + locally with python 3.11, stdlib only.
"""
import json, urllib.request, urllib.error, datetime, os, time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

INDICATORS = {
    "growth": "NY.GDP.MKTP.KD.ZG",
    "gdp": "NY.GDP.MKTP.CD",
    "pcap": "NY.GDP.PCAP.CD",
    "infl": "FP.CPI.TOTL.ZG",
    "fx": "PA.NUS.FCRF",
    "res": "FI.RES.TOTL.CD",
    "remit": "BX.TRF.PWKR.CD.DT",
    "exp": "NE.EXP.GNFS.CD",
    "imp": "NE.IMP.GNFS.CD",
    "ca": "BN.CAB.XOKA.GD.ZS",
    "debt": "DT.DOD.DECT.GN.ZS",
}

def fetch_wb(code, tries=4):
    url = f"https://api.worldbank.org/v2/country/BGD/indicator/{code}?format=json&date=2010:2030&per_page=30"
    last = None
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bd-dashboard/option2"})
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read().decode())
            rows = j[1] if len(j) > 1 and j[1] else []
            d = {int(o["date"]): o["value"] for o in rows}
            if d:
                return d
            last = "empty"
        except Exception as e:
            last = e
            print(f"  retry {a+1}/{tries} {code}: {e}")
            time.sleep(3 + a * 3)
    print(f"  WARN {code} failed after {tries}, using empty ({last})")
    return {}

def main():
    print("Fetching World Bank...")
    raw = {}
    for k, v in INDICATORS.items():
        print(f" {k} {v}...")
        raw[k] = fetch_wb(v)
        time.sleep(1)
    years = sorted({y for d in raw.values() for y, v in d.items() if v is not None and y >= 2010})
    if not years:
        raise SystemExit("WB fetch empty, aborting (keeps old files)")
    years = list(range(2010, max(years) + 1))

    def arr(key, scale=1.0, rnd=2):
        out = []
        for y in years:
            v = raw[key].get(y)
            out.append(None if v is None else round(v / scale, rnd))
        return out

    annual = {
        "updated_utc": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "World Bank WDI",
        "years": years,
        "growth": arr("growth"),
        "gdp": arr("gdp", 1e9),
        "pcap": [None if raw["pcap"].get(y) is None else round(raw["pcap"][y]) for y in years],
        "infl": arr("infl"),
        "fx": arr("fx"),
        "res": arr("res", 1e9),
        "remit": arr("remit", 1e9),
        "exp": arr("exp", 1e9),
        "imp": arr("imp", 1e9),
        "ca": arr("ca"),
        "debt": arr("debt"),
    }
    with open(os.path.join(DATA, "annual.json"), "w", encoding="utf-8") as f:
        json.dump(annual, f, indent=1)
    print(f"Wrote annual.json {years[0]}-{years[-1]}")

    mpath = os.path.join(DATA, "monthly.json")
    if not os.path.exists(mpath):
        raise SystemExit("monthly.json missing - keep your manual file")
    print("Kept monthly.json (manual, 2-min update via BB links)")

    i = len(years) - 1
    ly = years[i]
    g, inf = annual["growth"][i], annual["infl"][i]
    tag = "CRISIS-SLOWDOWN" if (g is not None and g < 4) else ("SLOWDOWN" if (g is not None and g < 5) else "RECOVERY")
    inftag = "HIGH INFLATION" if (inf is not None and inf >= 9) else ("ELEVATED INFLATION" if (inf is not None and inf >= 7) else "INFLATION EASING")
    summary = {
        "updated_utc": annual["updated_utc"],
        "annual_through": ly,
        "badge1": f"{tag} + {inftag} + EXTERNAL SHOCK",
        "note": "Rule-based only. Geopolitics prose stays manual until Option 3 (LLM).",
        "watch": ["growth<4", "infl>=8", "reserves vs 2021 peak", "remit buffer", "trade deficit"],
    }
    with open(os.path.join(DATA, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("Wrote summary.json", summary["badge1"])

if __name__ == "__main__":
    main()
