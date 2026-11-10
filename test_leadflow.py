import http.client, json, tempfile, threading, unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from leadflow import Store, make_handler
class TestLeadFlow(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/"demo.db")
    def tearDown(self):self.tmp.cleanup()
    def test_duplicate_normalization(self):
        sample={"name":"A","email":"A@EXAMPLE.ORG","source":"Web","budget_usd":600}
        self.assertEqual(self.store.add(sample)[0],201)
        self.assertEqual(self.store.add({**sample,"email":"a@example.org","source":"web"})[0],200)
        self.assertEqual(self.store.health()["leads"],1)
    def test_invalid(self):
        self.assertEqual(self.store.add({"name":"X","email":"bad"})[0],400)
        self.assertEqual(self.store.add({"name":"X","email":"x@example.org","budget_usd":-1})[0],400)
    def test_high_priority(self):
        self.store.add({"name":"X","email":"x@example.org","budget_usd":500})
        self.assertEqual(self.store.health()["pending"],1)
    def test_csv(self):
        self.store.add({"name":"Y","email":"y@example.org"})
        p=Path(self.tmp.name)/"export.csv"
        self.store.export(p)
        self.assertIn("y@example.org",p.read_text())
    def test_real_http(self):
        server=ThreadingHTTPServer(("127.0.0.1",0),make_handler(self.store))
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            conn=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=3)
            payload=json.dumps({"name":"Z","email":"z@example.org","budget_usd":700})
            conn.request("POST","/leads",payload,{"Content-Type":"application/json"})
            response=conn.getresponse();self.assertEqual(response.status,201);response.read()
            conn.request("GET","/health")
            response=conn.getresponse();self.assertEqual(response.status,200)
            self.assertEqual(json.loads(response.read())["leads"],1)
            conn.close()
        finally:server.shutdown();server.server_close()
if __name__=="__main__":unittest.main()
