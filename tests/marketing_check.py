"""Reconcile the private source snapshot without checking it into the repository."""
import copy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from marketing import normalize, number, post_key
from sources import attach_sources

raw = json.loads((ROOT / 'runtime/marketing-source.json').read_text(encoding='utf-8'))
live = normalize(raw)
active = [row for row in raw['adCreatives'] if not row.get('stale')]
for source, target in [('spend', 'spend'), ('revenue', 'revenue'), ('conversions', 'purchases'),
                       ('clicks', 'clicks'), ('impressions', 'impressions')]:
    assert sum(row[target] for row in live['ads']) == sum(number(row[source]) for row in active), target
assert sum(row['ad_count'] for row in live['ads']) == len(active)
assert len(live['ads']) == len({(row.get('accountId'), row['adName']) for row in active})
urls = {post_key(row['permalink']) for row in raw['brandazineLooks'] + raw['reels']}
assert len(live['people']) == len(urls)
for row in live['people']:
    if row['campaign'] == '크리에이터':
        original = next(r for r in raw['reels'] if post_key(r['permalink']) == post_key(row['post_url']))
        person = next(p for p in raw['people'] if row['id'] in p.get('usernames', []))
        month = original.get('feeMonth') or (original.get('verdict') or {}).get('month') or original['postDate'][:7]
        assert row['price'] == (person.get('unitFeeByMonth', {}).get(month) or person['unitFee'])
    else:
        original = next(r for r in raw['brandazineLooks'] if post_key(r['permalink']) == post_key(row['post_url']))
        if original.get('fee') is None:
            assert row['price'] is None and row['content_cost'] is None and not row['free']
    if '14d' not in original.get('milestones', {}):
        assert '14d' not in row['windows']

# A post shared between the API tracker and Brandazine appears once.
duplicate = copy.deepcopy(raw)
duplicate['reels'].append(copy.deepcopy(raw['brandazineLooks'][0]))
assert len(normalize(duplicate)['people']) == len(live['people'])
# Stale historical ad documents never inflate totals.
stale = copy.deepcopy(raw)
stale['adCreatives'][0]['stale'] = True
assert sum(row['spend'] for row in normalize(stale)['ads']) == sum(row['spend'] for row in live['ads']) - raw['adCreatives'][0]['spend']

empty = {'slug': 'marketing', 'name': '마케팅', 'people': [], 'ads': []}
old = {'teams': [{'slug': 'marketing', **copy.deepcopy(live)}]}
with patch('sources.marketing_source', side_effect=RuntimeError('offline')):
    fallback = attach_sources({'teams': [copy.deepcopy(empty)]}, old)['teams'][0]
assert fallback['source_state'] == 'error'
assert fallback['people'] == live['people'] and fallback['ads'] == live['ads']
assert fallback['source_at'] == live['source_at']

# Excel/source conflicts must abort the new report, including during an outage.
for offline in (False, True):
    with patch('sources.marketing_source', side_effect=RuntimeError('offline') if offline else None,
               return_value=copy.deepcopy(live)):
        for kind in ('people', 'ads'):
            team = copy.deepcopy(empty)
            team[kind] = [copy.deepcopy(live[kind][0])]
            try:
                attach_sources({'teams': [team]}, old)
            except ValueError:
                pass
            else:
                raise AssertionError('Excel/source duplicate accepted')

public = json.dumps(live, ensure_ascii=False)
for private_field in ['refreshToken', 'idToken', 'partnershipAdCode', 'partnerCode', 'manualNote', 'caption', 'feeSheetTitle']:
    assert private_field not in public, private_field
assert all(row['total_cost'] is None for row in live['ads'])
print(json.dumps({'passed': True, 'posts': len(live['people']), 'people': len({r['person_id'] for r in live['people']}),
                  'ad_records': len(active), 'ad_groups': len(live['ads']),
                  'spend': sum(r['spend'] for r in live['ads']), 'revenue': sum(r['revenue'] for r in live['ads'])}, ensure_ascii=False))
