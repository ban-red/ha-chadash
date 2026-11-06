"""The summary parser against a real Cha Dash hub, as Home Assistant reads it.

Skipped unless CHADASH_CONTRACT_URL names a hub that hasn't been set up:
CI starts the published image on the Demo Home (.github/workflows/ci.yml).
The test claims it with first-run setup, makes an inbox.read API token, and
reads GET /api/summary with it, as the integration does. Standard library
only: python3 -m unittest discover -s tests.
"""

import http.cookiejar
import importlib.util
import json
import os
import pathlib
import sys
import unittest
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("summary", pathlib.Path(__file__).parent.parent / "custom_components" / "chadash" / "summary.py")
summary = importlib.util.module_from_spec(spec)
sys.modules["summary"] = summary
spec.loader.exec_module(summary)

URL = os.environ.get("CHADASH_CONTRACT_URL", "").rstrip("/")


def request(opener, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL + path, data=data, method=method, headers={"Accept": "application/json", "Content-Type": "application/json", **(headers or {})})
    try:
        with opener.open(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read() or b"null")


@unittest.skipUnless(URL, "set CHADASH_CONTRACT_URL to a hub that hasn't been set up")
class ContractTest(unittest.TestCase):
    def test_summary_from_a_real_hub(self):
        session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, body = request(session, "POST", "/api/setup", {"username": "owner", "password": "correct horse battery staple"})
        self.assertEqual(status, 201, body)
        status, body = request(session, "POST", "/api/tokens", {"name": "home assistant contract", "scopes": ["inbox.read"], "expires_in_days": 1})
        self.assertEqual(status, 201, body)
        token = body["secret"]

        # As the integration reads it: the token only, no cookie.
        bare = urllib.request.build_opener()
        status, body = request(bare, "GET", "/api/summary", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(status, 200, body)
        s = summary.parse(body)
        self.assertIn(s.health, summary.HEALTHS)
        self.assertEqual(s.open, s.down + s.attention)
        self.assertLessEqual(len(s.top), 5)
        # The Demo Home always has something open. Updates are null where the
        # hub has no Update Center (the demo), which the sensor leaves out.
        self.assertGreater(s.open, 0)
        if s.updates_available is not None:
            self.assertGreaterEqual(s.updates_available, 0)

        # A wrong token is refused, which the integration turns into reauth.
        status, _ = request(bare, "GET", "/api/summary", headers={"Authorization": "Bearer cdt_wrong"})
        self.assertIn(status, (401, 403))


if __name__ == "__main__":
    unittest.main()
