from dataclasses import dataclass
from datetime import datetime, timedelta
from app.modules.bills import _anomalies as m
import pytest

@dataclass(frozen=True)
class T:
    transaction_id:str
    account_id:str='a1'
    occurred_at:datetime=datetime.fromisoformat('2026-09-10T23:00:00+08:00')
    amount_fen:int=100
    nature:str='consumption'
    direction:str='outflow'
    counterparty_id:str|None='shop1'

def t(id='x',date='2026-09-10T23:00:00+08:00',amount=100, merchant='shop1',nature='consumption'):
    return T(id,occurred_at=datetime.fromisoformat(date),amount_fen=amount,counterparty_id=merchant,nature=nature)

@pytest.mark.parametrize('amt,history,expected',[
 (200,[100,100],True), (100,[100,100],False),(500,[100]*9+[1000],True),
 (100,[100,500],False),(100,[],None)])
def test_rule1(amt,history,expected):
    previous=[t(f'p{i}',date='2026-08-10T12:00:00+08:00',amount=n) for i,n in enumerate(history)]
    result,findings=m.check_single(t(amount=amt),previous,lookback_complete=True,family_transfer=False)
    assert result[0].matched is expected

def test_unknown_family_does_not_infer_from_name():
    row=t(nature='transfer',merchant='new')
    checks,findings=m.check_single(row,[t('h',date='2026-08-01T12:00:00+08:00')],lookback_complete=True)
    assert checks[0].status=='insufficient_data'
    assert checks[1].matched is True

def test_family_transfer_excluded_from_rule1():
    c,f=m.check_single(t(nature='transfer',amount=9999),[t('h',date='2026-08-01T12:00:00+08:00')],lookback_complete=True,family_transfer=True)
    assert c[0].matched is False and not any(x.rule_id==1 for x in f)

def test_rule2_new_merchant_needs_large_amount():
    hist=[t('h',date='2026-08-01T12:00:00+08:00',merchant='known',amount=100)]
    c,_=m.check_single(t(merchant='new',amount=10),hist,lookback_complete=True)
    assert c[1].matched is False
    c,_=m.check_single(t(merchant='new',amount=500),hist,lookback_complete=True)
    assert c[1].matched is True

def test_missing_counterparty_does_not_guess_name():
    c,_=m.check_single(t(merchant=None),[t('h',date='2026-08-01T12:00:00+08:00')],lookback_complete=True)
    assert c[1].status=='insufficient_data'


def test_previous_inflow_is_a_known_counterparty_without_becoming_spending_baseline():
    prior = T("inflow", occurred_at=datetime.fromisoformat("2026-08-10T12:00:00+08:00"),
              amount_fen=100000, nature="transfer", direction="inflow", counterparty_id="known")
    checks, findings = m.check_single(t(merchant="known", nature="transfer", amount=100),
                                     [prior], lookback_complete=True)
    assert checks[1].status == "evaluated" and checks[1].matched is False
    assert not any(finding.rule_id == 2 for finding in findings)
    assert checks[0].status == "insufficient_data"


def test_scan_without_merchant_identity_is_insufficient_even_after_three_months():
    rows = [t(str(month), date=f"2026-{month:02}-10T12:00:00+08:00", merchant=None)
            for month in (7, 8, 9)]
    checks, findings = m.check_scan(rows, complete=True)
    assert checks[0].status == "insufficient_data" and checks[0].matched is None
    assert findings == ()

@pytest.mark.parametrize('when,expect',[
 ('2026-09-10T21:59:59+08:00',False),('2026-09-10T22:00:00+08:00',True),
 ('2026-09-11T05:59:59.999999+08:00',True),('2026-09-11T06:00:00+08:00',False),
 ('2026-09-11T06:00:01+08:00',False),('2026-09-10T14:00:00+00:00',True)])
def test_rule3_boundaries(when,expect):
    c,_=m.check_single(t(date=when),[t('h',date='2026-08-01T12:00:00+08:00')],lookback_complete=True)
    assert c[2].matched is expect
    assert c[2].status == 'evaluated'

def test_rule4_three_and_missing_month():
    valid=[t('a',date='2026-07-10T12:00:00+08:00',amount=3900),t('b',date='2026-08-13T12:00:00+08:00',amount=3900),t('c',date='2026-09-09T12:00:00+08:00',amount=3900)]
    assert len(m.periodic_groups(valid,complete=True))==1
    assert not m.periodic_groups([valid[0],valid[2],t('d',date='2026-10-09T12:00:00+08:00',amount=3900)],complete=True)

def test_rule4_anchored_not_drifting():
    rows=[t('a',date='2026-07-10T12:00:00+08:00'),t('b',date='2026-08-13T12:00:00+08:00'),t('c',date='2026-09-16T12:00:00+08:00')]
    assert not m.periodic_groups(rows,complete=True)

def test_rule4_end_of_month():
    rows=[t('a',date='2026-01-31T12:00:00+08:00'),t('b',date='2026-02-28T12:00:00+08:00'),t('c',date='2026-03-31T12:00:00+08:00')]
    assert len(m.periodic_groups(rows,complete=True))==1

def test_rule4_same_month_does_not_count_as_three_months():
    rows=[t(str(i),date=f'2026-07-{d:02}T12:00:00+08:00') for i,d in enumerate([10,11,12])]
    assert not m.periodic_groups(rows,complete=True)

def test_rule4_strict_merchant_and_amount():
    rows=[t('a',date='2026-07-10T12:00:00+08:00'),t('b',date='2026-08-10T12:00:00+08:00',merchant='different'),t('c',date='2026-09-10T12:00:00+08:00',amount=110)]
    assert not m.periodic_groups(rows,complete=True)

def test_scan_only_rule4_and_incomplete_returns_insufficient():
    rows=[t('a',date='2026-07-10T12:00:00+08:00'),t('b',date='2026-08-10T12:00:00+08:00'),t('c',date='2026-09-10T12:00:00+08:00')]
    checks,findings=m.check_scan(rows,complete=True)
    assert len(checks)==1 and checks[0].rule_id==4 and findings[0].rule_id==4
    checks,findings=m.check_scan(rows,complete=False)
    assert checks[0].status=='insufficient_data' and not findings
