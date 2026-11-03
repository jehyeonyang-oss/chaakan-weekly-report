"""One-time, user-operated sign-in in a separate temporary browser.

Never runs from the scheduler. Opening this window requires the user's explicit
permission; --allow-browser records that permission for this invocation only.
Only the marketing app's Firebase credential is retained, in gitignored runtime.
"""
import argparse
import json
from pathlib import Path
import re
import time
from urllib.parse import urlparse, parse_qs

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://chaakan-creator-hub.web.app'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-browser', action='store_true')
    args = parser.parse_args()
    if not args.allow_browser:
        parser.error('Explicit permission to open the temporary login window is required.')
    credential = {}

    def capture(response):
        parsed = urlparse(response.url)
        if parsed.hostname != 'identitytoolkit.googleapis.com' or not parsed.path.endswith('/accounts:signInWithIdp') or response.status != 200:
            return
        data = response.json()
        if not re.fullmatch(r'[^@]+@(?:chaakan\.co\.kr|seoul-link\.com)', data.get('email', '')):
            return
        if data.get('refreshToken'):
            credential.update(projectId='chaakan-creator-hub', email=data['email'],
                              apiKey=parse_qs(parsed.query)['key'][0], refreshToken=data['refreshToken'])

    with sync_playwright() as pw:
        # No existing Chrome profile, cookies, window, or debugging port is used.
        browser = pw.chromium.launch(channel='chrome', headless=False)
        context = browser.new_context()
        context.on('response', capture)
        page = context.new_page()
        page.goto(ORIGIN, wait_until='domcontentloaded')
        print('Please sign in to the marketing hub in the temporary window.', flush=True)
        deadline = time.monotonic() + 600
        while not credential and time.monotonic() < deadline:
            page.wait_for_timeout(500)
        if not credential:
            raise RuntimeError('Login was not completed. No credentials saved.')
        target = ROOT / 'runtime' / 'marketing-auth.json'
        target.parent.mkdir(exist_ok=True)
        tmp = target.with_suffix('.tmp')
        tmp.write_text(json.dumps(credential), encoding='utf-8')
        tmp.replace(target)
        browser.close()
    print('Marketing authentication saved locally. No credentials published.')


if __name__ == '__main__':
    main()
