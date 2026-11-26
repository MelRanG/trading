from types import SimpleNamespace

import pandas as pd

from experiments.task16_economics.worker import compare, summarize, TERMINAL


def test_same_entry_and_causal_liquidation():
    dates = pd.bdate_range("2023-01-02", periods=22)
    history = pd.bdate_range(end=dates[-1], periods=53)
    stock = pd.DataFrame({"open": 10000., "close": 10000., "volume": 200000.}, index=history)
    stock.loc[dates[5], "open"] = 12000
    stock.loc[dates[6], "volume"] = 0
    stock.loc[dates[7], "open"] = 12500
    stock.loc[dates[TERMINAL], "open"] = 12800
    targets = pd.DataFrame({
        "targets": [{"A": .2}] * len(dates), "decision": [False] * len(dates),
        "risk_on": [True] * len(dates),
    }, index=dates)
    targets.loc[dates[0], "decision"] = True
    targets.loc[dates[5], "decision"] = True
    targets.at[dates[5], "targets"] = {}
    bundle = {"targets": targets, "nominal": {"A": stock, "069500.KS": stock.copy()},
              "actions": {"A": {}}, "assets": {"A": SimpleNamespace()}}
    result = compare(bundle, [0])
    for scenario in result:
        values = scenario["arms"]
        assert len({arm["fills"][0]["quantity"] for arm in values.values()}) == 1
        assert values["candidate"]["fills"][-1]["date"] == dates[5].date().isoformat()
        assert values["incumbent"]["fills"][-1]["date"] == dates[5].date().isoformat()
        assert values["hold"]["fills"][-1]["date"] == dates[TERMINAL].date().isoformat()
    assert summarize(result)["economic_judgment"] == "NO_CONFIRMED_INCREMENT"
    stock.loc[dates[5], "volume"] = 0
    delayed = compare(bundle, [0])[0]["arms"]["candidate"]
    assert delayed["fills"][-1]["date"] == dates[7].date().isoformat()
    assert delayed["marks"][5]["pending"] == {"A": 0}
