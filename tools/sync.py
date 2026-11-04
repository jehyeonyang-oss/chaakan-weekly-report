"""Local scheduled sync: validate Excel, publish only whitelisted report data."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback
import msvcrt

from report import build
from sources import attach_sources

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
RUNTIME.mkdir(exist_ok=True)


def run(*args):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding='utf-8',
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=120)
    if p.returncode:
        raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout


def atomic_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def publish(paths):
    run('git', 'add', '--', *paths)
    staged = run('git', 'diff', '--cached', '--name-only').strip().splitlines()
    if any(p not in paths for p in staged):
        raise RuntimeError('동기화 대상 외 파일이 staged 상태입니다. 자동 커밋을 중단합니다.')
    if staged:
        run('git', 'commit', '-m', 'Update team report from Excel')
    # Retry a previously failed push even when the workbook did not change.
    run('git', 'push', 'origin', 'main')


def main():
    config = json.loads((ROOT / 'local-config.json').read_text(encoding='utf-8'))
    lock = (RUNTIME / 'sync.lock').open('a+b')
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        lock.close()
        return
    try:
        now = datetime.now().astimezone().isoformat(timespec='seconds')
        file = ROOT / 'docs/data.json'
        old = json.loads(file.read_text(encoding='utf-8')) if file.exists() else {}
        built = build(config, old=old)
        team_errors = built.pop('errors')  # local health only, never published
        data = attach_sources(built, old)
        canonical = json.dumps(data, ensure_ascii=False, sort_keys=True)
        revision = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        changed = old.get('revision') != revision
        if changed:
            data.update(revision=revision, updated_at=now)
            atomic_json(file, data)
        status_file = ROOT / 'docs/status.json'
        ok = {'state': 'ok', 'message': ''}
        previous = json.loads(status_file.read_text(encoding='utf-8')) if status_file.exists() else None
        if previous != ok:
            atomic_json(status_file, ok)
        if '--local-only' not in sys.argv:
            # No force push, no reset or automatic conflict resolution.
            publish(['docs/data.json', 'docs/status.json'])
        atomic_json(RUNTIME / 'health.json', {'state': 'ok', 'checked_at': now, 'changed': changed, 'revision': revision, 'team_errors': team_errors})
        print(json.dumps({'state': 'ok', 'changed': changed, 'revision': revision, 'team_errors': list(team_errors)}, ensure_ascii=False))
    except Exception as exc:
        atomic_json(RUNTIME / 'health.json', {'state': 'error', 'checked_at': datetime.now().astimezone().isoformat(), 'error': str(exc)})
        with (RUNTIME / 'sync.log').open('a', encoding='utf-8') as f:
            f.write(datetime.now().isoformat() + '\n' + traceback.format_exc() + '\n')
        # Keep the last valid data. Publish only a generic error, never local paths or row values.
        status = {'state': 'error', 'message': '엑셀 입력 확인이 필요합니다. 마지막 정상 집계가 표시됩니다.'}
        atomic_json(ROOT / 'docs/status.json', status)
        if '--local-only' not in sys.argv:
            try:
                publish(['docs/status.json'])
            except Exception:
                pass
        raise
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


if __name__ == '__main__':
    main()
