"""Authenticated marketing source -> public report fields only.

The private source and refresh credential live under gitignored runtime/.
No partnership codes, account credentials, captions, or internal notes are exported.
"""
from datetime import datetime, timezone, timedelta
import json
import math
from pathlib import Path
import subprocess
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://chaakan-creator-hub.web.app/'
CACHE_SECONDS = 900
KST = timezone(timedelta(hours=9))
METRICS = ('views', 'likes', 'comments', 'shares', 'saves')


def number(value):
    if value is None or isinstance(value, bool) or value == '':
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else None
    except (TypeError, ValueError):
        return None


def iso(value):
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, KST).isoformat(timespec='seconds')
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(KST).isoformat(timespec='seconds')
    except (ValueError, TypeError):
        return None


def handle(value):
    return str(value or '').strip().lstrip('@').lower()


def post_key(value):
    parsed = urlparse(value or '')
    parts = parsed.path.strip('/').split('/')
    if parsed.hostname not in ('instagram.com', 'www.instagram.com') or len(parts) != 2 or parts[0] not in ('p', 'reel', 'reels'):
        raise ValueError('마케팅 원본 게시물 링크 확인 필요')
    return parts[1]


def snapshot(value):
    value = value or {}
    return {**{key: number(value.get('saved' if key == 'saves' else key)) for key in METRICS},
            'at': iso(value.get('sampleAt') or value.get('at') or value.get('atIso'))}


def windows(record, brandazine=False):
    latest = snapshot(record.get('latest'))
    if brandazine:
        # Match the source's latest view/comment/like precedence. Shared/saved
        # remain Brandazine measurements; an absent API field is never zero.
        ig = record.get('ig') or {}
        for key in ('views', 'comments', 'likes'):
            if key == 'likes' and ig.get('likesHidden'):
                continue
            if number(ig.get(key)) is not None:
                latest[key] = number(ig[key])
        latest['instagram_at'] = iso(ig.get('at'))
    result = {'latest': latest}
    milestones = record.get('milestones') or {}
    for source, target in [('48h', '48h'), ('7d', '7d'), ('14d', '14d')]:
        if source in milestones:
            result[target] = snapshot(milestones[source])
    # 15-day measurements are not relabelled as 14-day measurements.
    return result


def normalize(raw):
    for key in ('people', 'reels', 'brandazineLooks', 'adCreatives'):
        if not isinstance(raw.get(key), list):
            raise ValueError('마케팅 원본 데이터 구조 확인 필요')
    aliases = {}
    for person in raw['people']:
        for username in person.get('usernames') or []:
            aliases[handle(username)] = person
    records = {}
    for kind, rows in [('브랜더진', raw['brandazineLooks']), ('크리에이터', raw['reels'])]:
        for row in rows:
            if kind == '크리에이터' and row.get('eligibility', 'done') != 'done':
                continue
            username = handle(row.get('username'))
            if not username or not row.get('permalink') or not row.get('postDate'):
                raise ValueError('마케팅 원본 게시물의 계정·링크·게시일 누락')
            key = post_key(row['permalink'])
            if key in records:
                # Brandazine is authoritative when its post also exists in the tracker.
                continue
            person = aliases.get(username, {})
            if kind == '브랜더진':
                price = number(row.get('fee'))
                secondary = number(row.get('secondaryFee'))
                content_cost = price + secondary if price is not None and secondary is not None else None
                name = row.get('realName') or username
            else:
                month = row.get('feeMonth') or (row.get('verdict') or {}).get('month') or row['postDate'][:7]
                price = number((person.get('unitFeeByMonth') or {}).get(month))
                if not price:
                    price = number(person.get('unitFee'))
                # The source treats absent/zero unit fees as unpriced, not gifting.
                price = price if price and price > 0 else None
                secondary = None
                content_cost = price
                name = person.get('name') or username
            w = windows(row, kind == '브랜더진')
            latest = w['latest']
            records[key] = {
                'key': 'marketing:' + key, 'id': username, 'name': name,
                'person_id': 'marketing:person:' + str(person['id']) if person else 'marketing:ig:' + username,
                'url': 'https://www.instagram.com/' + username + '/', 'who': '마케팅팀',
                'campaign': kind, 'product': row.get('productName') or row.get('product') or '',
                'country': '한국', 'channel': '인스타그램', 'group': '한국',
                'status': '업로드 완료', 'stage': '⑦', 'free': price == 0 if price is not None else False,
                'price': price, 'secondary_cost': secondary, 'content_cost': content_cost,
                'avg': None, 'exp_ss': None, 'upload': row['postDate'], 'post_url': row['permalink'],
                'measured': latest['at'][:10] if latest.get('at') else None,
                **{metric: latest[metric] for metric in METRICS}, 'windows': w,
                'revenue': None, 'revenue_window': None, 'source': 'live',
            }
    groups = {}
    seen = set()
    for row in raw['adCreatives']:
        if row.get('stale'):
            continue
        if row['id'] in seen:
            raise ValueError('마케팅 광고 ID 중복')
        seen.add(row['id'])
        if not row.get('adName'):
            raise ValueError('마케팅 광고명 누락')
        groups.setdefault((row.get('accountId'), row['adName']), []).append(row)
    ads = []
    for (_, name), rows in groups.items():
        def total(key):
            values = [number(row.get(key)) for row in rows]
            return sum(values) if all(value is not None for value in values) else None
        starts = sorted(row['liveStart'] for row in rows if row.get('liveStart'))
        ends = sorted(row['liveEnd'] for row in rows if row.get('liveEnd'))
        ads.append({
            'key': 'marketing:ad:' + min(str(row['id']) for row in rows),
            'campaign': name, 'channel': '메타 · 파트너콘텐츠',
            'period': (starts[0] if starts else '—') + ' ~ ' + (ends[-1] if ends else '—'),
            'status': f"광고 {len(rows)}개 · 클릭 후 1일", 'ad_count': len(rows),
            **{target: total(source) for source, target in [('spend', 'spend'), ('impressions', 'impressions'),
                ('clicks', 'clicks'), ('conversions', 'purchases'), ('revenue', 'revenue')]},
            'shares': None, 'saves': None, 'total_cost': None,
            'source': 'live', 'url': '',
        })
    ads.sort(key=lambda row: row['spend'] or 0, reverse=True)
    timestamps = [iso(row.get('syncedAt')) for row in raw['adCreatives'] if not row.get('stale')]
    timestamps += [iso(row.get('lastSyncAt')) for row in raw['brandazineLooks']]
    timestamps += [iso(row.get('lastSampleAt')) for row in raw['reels']]
    return {
        'people': sorted(records.values(), key=lambda row: (row['upload'], row['id']), reverse=True),
        'ads': ads, 'source_url': BASE, 'source_state': 'ok', 'source_message': '',
        'source_at': max(filter(None, timestamps), default=None), 'fetched_at': raw['fetchedAt'],
        'period': '원본 전체 기간 누적', 'cost_basis': 'marketing_source',
    }


def marketing_source():
    target = ROOT / 'runtime' / 'marketing-source.json'
    raw = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
    fetched = datetime.fromisoformat(raw['fetchedAt'].replace('Z', '+00:00')) if raw else None
    if fetched is None or (datetime.now(timezone.utc) - fetched).total_seconds() >= CACHE_SECONDS:
        result = subprocess.run(['node', str(ROOT / 'tools' / 'fetch_marketing.cjs')], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=240,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode:
            # Do not expose authentication errors or full source URLs in the report.
            raise RuntimeError('마케팅 원본 수집 실패')
        raw = json.loads(target.read_text(encoding='utf-8'))
    return normalize(raw)
