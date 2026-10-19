"""L03 private report arithmetic tests, not F21/F22 or permission tests."""
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec
import pytest
spec=spec_from_file_location('private_report',Path(__file__).parent/'_report.py')
m=module_from_spec(spec)
import sys
sys.modules[spec.name]=m
spec.loader.exec_module(m)

@pytest.mark.parametrize('gross,days,expected',[
 (60000,20,90000), (0,20,0), (1,7,4), (1,20,2), (1,0,None), (100,30,100), (100,60,50)
])
def test_monthly_average_uses_gross_and_last_rounding(gross,days,expected):
    assert m.average_per_30_days(gross,days)==expected

@pytest.mark.parametrize('gross,days',[(True,20),(10,-1),('10',20),(1,1.5)])
def test_invalid_report_numbers_rejected(gross,days):
    with pytest.raises(ValueError):m.average_per_30_days(gross,days)

def test_report_sentence_has_no_risk_or_transfer_claim():
    summary=SimpleNamespace(transaction_count=2,consumption_gross_fen=60000,
           consumption_refund_fen=20000,consumption_net_fen=40000,comparison=None)
    text=m.plain_summary(summary)
    assert '600元' in text and '200元' in text and '400元' in text
    assert '盗刷' not in text and '冻结' not in text and '收益' not in text

def test_report_spoken_empty():
    summary=SimpleNamespace(transaction_count=0)
    assert m.plain_summary(summary)=='查询范围内没有交易记录。'

def test_report_net_inconsistent_is_not_spoken():
    summary=SimpleNamespace(transaction_count=1,consumption_gross_fen=100,
           consumption_refund_fen=20,consumption_net_fen=100,comparison=None)
    with pytest.raises(ValueError,match='invalid_net_equation'):m.plain_summary(summary)
