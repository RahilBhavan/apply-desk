"""Real loopback HTTP requests with private scratch files and browser-origin checks."""
import base64
import json
from pathlib import Path
import re
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from apply_desk.web_server import make_server


class WebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'member'
        self.server = make_server(self.root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        with urlopen(self.url) as response:
            self.token = re.search(r'name="apply-desk-token" content="([^"]+)"', response.read().decode()).group(1)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, body=None, **extra):
        headers = {'X-Apply-Desk': self.token, 'Content-Type': 'application/json', **extra}
        request = Request(self.url + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
        with urlopen(request) as response:
            return json.load(response)

    def test_onboard_import_export_and_origin_guards(self):
        self.assertFalse(self.request('/api/state')['initialized'])
        self.request('/api/init', {'profile': {'first_name': 'Alex'},
            'resume': base64.b64encode(b'%PDF-1.4\nsynthetic').decode()})
        csv = 'company,title,apply_url\nExample,Intern,https://jobs.example.com/1\n'
        self.assertEqual(self.request('/api/jobs', {'csv': csv})['added'], 1)
        self.assertEqual(self.request('/api/jobs', {'csv': csv})['added'], 0)
        state = self.request('/api/state')
        self.assertEqual(state['profile']['first_name'], 'Alex')
        batch = self.request('/api/export', {})['batch']
        self.assertTrue((Path(batch) / 'batch.json').is_file())
        for headers in [{'Origin': 'https://evil.example'}, {'Host': 'evil.example'}, {'X-Apply-Desk': 'wrong'}]:
            with self.assertRaises(HTTPError) as error:
                self.request('/api/state', **headers)
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        with self.assertRaises(HTTPError) as error:
            self.request('/api/init', {'profile': {'first_name': 'Other'}, 'resume': 'invalid'})
        error.exception.close()
        self.assertEqual(self.request('/api/state')['profile']['first_name'], 'Alex')


if __name__ == '__main__':
    unittest.main()
