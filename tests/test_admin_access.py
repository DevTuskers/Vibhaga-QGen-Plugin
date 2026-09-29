import contextlib
import io
import json
import os
from pathlib import Path
import socket
import ssl
from types import SimpleNamespace
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import urllib.response
from email.message import Message

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
with patch.dict(os.environ, {"VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only"}):
    import _admin_auth as auth
    import publish

PAIR = {"CF_ACCESS_CLIENT_ID": "fake-access-id", "CF_ACCESS_CLIENT_SECRET": "fake-access-secret"}
UID = "11111111-2222-4333-8444-555555555555"


class Recorder:
    def __init__(self, status=200, body=None):
        self.calls = []
        self.status = status
        self.body = body if body is not None else {"ready": True, "questions": []}

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, {k.lower(): v for k, v in headers.items()}, body))
        if "/auth/v1/token?" in url:
            return 200, {}, json.dumps({"access_token": "fake-jwt", "user": {"id": UID}}).encode()
        raw = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
        return self.status, {}, raw

    def publish(self, *args):
        status, _, body = self(*args)
        return status, body


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")))
        self.stack.enter_context(patch.object(auth, "read_env_all", side_effect=AssertionError("credential reads forbidden")))
        self.stack.enter_context(patch.object(auth, "checked_tls_context", return_value=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)))
        self.env = {**auth.fake_env(), **PAIR}
        self.r = Recorder()

    def clients(self, env=None):
        env = self.env if env is None else env
        return (auth.Admin(env, transport=self.r), publish.Api(env, transport=self.r.publish, log=lambda _: None))

    def test_paired_keys_retained_by_env_parser(self):
        with patch.object(auth, "read_env_all", return_value=self.env):
            self.assertEqual(auth.read_env("unused"), self.env)

    def test_pair_is_optional_but_partial_or_invalid_fails_closed(self):
        for key in PAIR:
            for val in ("", " ", "bad\r\nheader"):
                for factory in (lambda e: auth.Admin(e, self.r), lambda e: publish.Api(e, self.r.publish)):
                    with self.subTest(key=key, invalid=repr(val), factory=factory):
                        with self.assertRaises((SystemExit, publish.Refuse)):
                            factory({**self.env, key: val})
            with self.subTest(missing=key):
                env = dict(self.env); del env[key]
                for factory in (lambda: auth.Admin(env, self.r), lambda: publish.Api(env, self.r.publish)):
                    with self.assertRaises((SystemExit, publish.Refuse)):
                        factory()
        for key in PAIR:
            for factory in (lambda e: auth.Admin(e, self.r), lambda e: publish.Api(e, self.r.publish)):
                with self.subTest(single_empty_key=key):
                    with self.assertRaises((SystemExit, publish.Refuse)):
                        factory({**auth.fake_env(), key: ""})
        for factory in (lambda e: auth.Admin(e, self.r), lambda e: publish.Api(e, self.r.publish)):
            with self.assertRaises((SystemExit, publish.Refuse)):
                factory({**auth.fake_env(), **dict.fromkeys(PAIR, "")})
        self.assertEqual(self.r.calls, [])
        a, p = self.clients(auth.fake_env())
        a.token(); a.call("GET", "/v1/admin/uploads"); p.fresh_token("get"); p.get_doc("job")
        self.assertTrue(all(not any(k.startswith("cf-access-") for k in c[2]) for c in self.r.calls))

    def test_headers_scoped_to_admin_not_supabase(self):
        a, p = self.clients()
        a.token(); a.call("POST", "/v1/admin/uploads", {}); a.logout()
        p.fresh_token("get"); p.get_doc("job"); p.put_doc("job", [], None); p.publish("job", [], True); p.logout_global()
        for _, url, h, _ in self.r.calls:
            with self.subTest(url=url):
                if "/v1/admin/" in url:
                    self.assertEqual(h.get("cf-access-client-id"), PAIR["CF_ACCESS_CLIENT_ID"])
                    self.assertEqual(h.get("cf-access-client-secret"), PAIR["CF_ACCESS_CLIENT_SECRET"])
                    self.assertEqual(h["authorization"], "Bearer fake-jwt")
                else:
                    self.assertFalse(any(k.startswith("cf-access-") for k in h))
                    self.assertEqual(h["apikey"], "anon")

    def test_raw_upload_has_only_supplied_headers(self):
        a, _ = self.clients(); a.token()
        supplied = {"Content-Type": "application/pdf", "x-amz-checksum-sha256": "fake-checksum"}
        a.call("PUT", None, b"%PDF-fake", raw_url="https://r2.test/object?X-Amz-Signature=fake", extra_headers=supplied)
        self.assertEqual(self.r.calls[-1][2], {k.lower(): v for k, v in supplied.items()})
        self.assertEqual(self.r.calls[-1][3], b"%PDF-fake")

    def test_extra_headers_cannot_override_guards(self):
        a, _ = self.clients()
        for key in ("Authorization", "aPiKeY", "CF-Access-Client-Id", "cf-access-client-secret", "Host", "Cookie", "Proxy-Authorization"):
            for raw in (None, "https://r2.test/object"):
                with self.subTest(header=key, raw=raw):
                    with self.assertRaises(SystemExit):
                        a.call("PUT", "/v1/admin/uploads", raw_url=raw, extra_headers={key: "injected"})
        self.assertEqual(self.r.calls, [])

    def test_malformed_or_insecure_bases_rejected_before_auth(self):
        bad = ("http://api.test", "https://user:pass@api.test", "https://api.test/v1/admin", "https://api.test/?x=1",
               "https://api.test/#x", "https://api.test?", "https://api.test#", "https://api.test:bad", "https://api.test:",
               "https://api.test:0", "https://api.test:65536", "https://api.test\\evil", " https://api.test", "https://api.test\n", "https:///api.test")
        for base in bad:
            for key in ("NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_SUPABASE_URL"):
                for factory in (lambda e: auth.Admin(e, self.r), lambda e: publish.Api(e, self.r.publish)):
                    with self.subTest(base=repr(base), key=key):
                        with self.assertRaises((SystemExit, publish.Refuse)):
                            factory({**self.env, key: base})
        self.assertEqual(self.r.calls, [])

    def test_admin_path_boundary_and_origin_exact_match(self):
        a, p = self.clients()
        bad = ("/v1/administer", "/v1/admin/../public", "/v1/admin/%2e%2e/public", "/v1/admin/%252e%252e/public",
               "/v1/admin/foo%2f..%2fpublic", "/v1/admin//uploads", "/v1/admin/./uploads", "/v1/admin\\uploads",
               "/v1/admin/uploads#frag", "//evil.test/v1/admin/uploads", "https://evil.test/v1/admin/uploads", "/v1/public")
        for path in bad:
            with self.subTest(path=path):
                with self.assertRaises(SystemExit): a.call("GET", path)
                with self.assertRaises(publish.Refuse): p._json("GET", p.base + path, p._auth(), scope="admin")
        for url in ("https://api.test.evil/v1/admin/uploads", "https://api.test:444/v1/admin/uploads", "https://evil.test/v1/admin/uploads", "http://api.test/v1/admin/uploads"):
            with self.subTest(url=url):
                with self.assertRaises(publish.Refuse): p._json("GET", url, p._auth(), scope="admin")
        self.assertEqual(self.r.calls, [])

    def test_publish_supabase_scope_cannot_send_access_headers(self):
        _, p = self.clients()
        for url, h in ((p.sb + "/v1/admin/uploads", p._auth()), (p.sb + "/auth/v1/logout?scope=global", {**p._auth(), "CF-Access-Client-Secret": "injected"})):
            with self.assertRaises(publish.Refuse): p._json("POST", url, h, scope="supabase")
        self.assertEqual(self.r.calls, [])

    def test_raw_url_must_be_https_without_userinfo_or_fragment(self):
        a, _ = self.clients()
        for url in ("http://r2.test/x", "https://user@r2.test/x", "https://r2.test/x#f", "file:///tmp/x", "https://r2.test/x\n"):
            with self.subTest(url=url):
                with self.assertRaises(SystemExit): a.call("PUT", None, raw_url=url)
        self.assertEqual(self.r.calls, [])

    def test_error_content_is_not_returned_or_logged(self):
        for status in (0, 301, 302, 303, 307, 308, 400, 401, 403, 500):
            for body in (b'<html>fake-access-secret fake-jwt fake-password</html>', {"error": PAIR["CF_ACCESS_CLIENT_SECRET"], "nested": {"token": "fake-jwt"}}):
                self.r.status, self.r.body = status, body
                a, p = self.clients(); a.access = "fake-jwt"; p.token = "fake-jwt"
                for result in (a.call("GET", "/v1/admin/uploads"), p.publish("job", [])):
                    with self.subTest(status=status):
                        self.assertNotIn("fake-access-secret", str(result)); self.assertNotIn("fake-jwt", str(result))

    def test_get_doc_unexpected_success_status_withholds_body(self):
        for status in (201, 202):
            with self.subTest(status=status):
                self.r.status = status; self.r.body = {"error": "fake-access-secret", "nested": {"token": "fake-jwt"}}
                _, api = self.clients()
                with self.assertRaises(publish.Refuse) as caught: api.get_doc("job")
                self.assertEqual(caught.exception.code, 5)
                self.assertIn(f"HTTP {status}", str(caught.exception))
                self.assertNotIn("fake-access-secret", str(caught.exception))
                self.assertNotIn("fake-jwt", str(caught.exception))

    def test_put_doc_unexpected_success_status_withholds_body(self):
        for status in (201, 202):
            with self.subTest(status=status):
                self.r.status = status; self.r.body = {"error": "fake-access-secret", "nested": {"token": "fake-jwt"}}
                _, api = self.clients()
                with self.assertRaises(publish.Refuse) as caught: api.put_doc("job", [], None)
                self.assertEqual(caught.exception.code, 5)
                self.assertIn(f"HTTP {status}", str(caught.exception))
                self.assertNotIn("fake-access-secret", str(caught.exception))
                self.assertNotIn("fake-jwt", str(caught.exception))

    def test_parsed_status_diagnostics_are_strictly_whitelisted(self):
        for (status, sentinel), message in auth.SAFE_ERRORS.items():
            with self.subTest(status=status, sentinel=sentinel):
                self.assertEqual(auth.response_error(status, {"error": message, "nested": "fake-access-secret"}), message)
                self.assertEqual(auth.response_error(201, {"error": message}), "HTTP 201 (response body withheld)")
                self.assertEqual(auth.response_error(status, {"error": message + " fake-access-secret"}), f"HTTP {status} (response body withheld)")
                self.assertEqual(auth.response_error(status, {"error": {"nested": "fake-access-secret"}}), f"HTTP {status} (response body withheld)")

    def test_failed_grant_does_not_echo_error(self):
        def fail(*_): return 401, json.dumps({"error_description": "fake-access-secret fake-password"}).encode()
        p = publish.Api(self.env, transport=fail, log=lambda _: None)
        with self.assertRaises(publish.Refuse) as caught: p.fresh_token("get")
        self.assertEqual(caught.exception.code, 6)
        self.assertNotIn("fake-access-secret", str(caught.exception)); self.assertNotIn("fake-password", str(caught.exception))

    def test_urllib_never_follows_redirects(self):
        for status in (301, 302, 303, 307, 308):
            calls = []
            class FakeHTTPS(urllib.request.HTTPSHandler):
                def https_open(self, req):
                    calls.append(req)
                    h = Message(); h["Location"] = "https://evil.test/stolen"
                    response = urllib.response.addinfourl(io.BytesIO(b"echoed-fake-secret"), h, req.full_url, status if len(calls) == 1 else 200)
                    response.msg = "fake response"
                    return response
            with patch.object(urllib.request, "HTTPSHandler", FakeHTTPS), patch.object(urllib.request, "_opener", None):
                actual, _, _ = auth.urllib_transport("GET", "https://api.test/v1/admin/uploads", {"Authorization": "Bearer fake-jwt", **PAIR}, None)
            with self.subTest(status=status):
                self.assertEqual(actual, status); self.assertEqual(len(calls), 1)

    def test_transport_error_reason_is_discarded(self):
        error = urllib.error.URLError("fake-access-secret")
        class BrokenHTTPS(urllib.request.HTTPSHandler):
            def https_open(self, req): raise error
        with patch.object(urllib.request, "HTTPSHandler", BrokenHTTPS), patch.object(urllib.request, "_opener", None):
            result = auth.urllib_transport("GET", "https://api.test/v1/admin/uploads", {}, None)
        self.assertEqual(result[0], 0); self.assertNotIn("fake-access-secret", str(result))

    def test_api_and_supabase_origins_must_be_distinct(self):
        for api, sb in (("https://api.test", "https://api.test"), ("https://API.TEST", "https://api.test/"),
                        ("https://api.test:443", "https://API.TEST"), ("https://API.TEST:0443/", "https://api.test:443")):
            for cf in ({}, PAIR):
                for factory in (lambda e: auth.Admin(e, self.r), lambda e: publish.Api(e, self.r.publish)):
                    with self.subTest(api=api, sb=sb, access=bool(cf)):
                        with self.assertRaises((SystemExit, publish.Refuse)):
                            factory({**auth.fake_env(), **cf, "NEXT_PUBLIC_API_BASE_URL": api, "NEXT_PUBLIC_SUPABASE_URL": sb})
        self.assertEqual(self.r.calls, [])
        self.clients({**self.env, "NEXT_PUBLIC_SUPABASE_URL": "https://api.test:444"})

    def test_documented_admin_origin_exactly_scoped_with_fake_transport(self):
        base = "https://admin-api.example.test"
        a, p = self.clients({**self.env, "NEXT_PUBLIC_API_BASE_URL": base + "/"})
        a.call("GET", "/v1/admin"); p.get_doc("fake-job")
        self.assertTrue(all(c[1].startswith(base + "/v1/admin") for c in self.r.calls))
        self.assertTrue(all(c[2]["cf-access-client-secret"] == PAIR["CF_ACCESS_CLIENT_SECRET"] for c in self.r.calls))
        a.call("PUT", None, raw_url=base + "/v1/admin/uploads", extra_headers={"Content-Type": "application/pdf"})
        self.assertEqual(self.r.calls[-1][2], {"content-type": "application/pdf"})

    # NOTE (plugin move): test_paper_upload_access_integration and the PaperCleanupTests class were
    # dropped — they exercised paper-prep.py, which is not carried into this plugin (docs/MIGRATION.md).

    def test_empty_raw_url_and_malformed_headers_fail_closed(self):
        a, _ = self.clients()
        with self.assertRaises(SystemExit): a.call("PUT", "/v1/admin/uploads", raw_url="")
        for h in ({"Content-Type": "application/pdf\r\nfake: injected"}, {"CF-Access-Jwt-Assertion": "injected"}, {"Content-Type": "x", "content-type": "y"}):
            with self.assertRaises(SystemExit): a.call("PUT", None, raw_url="https://r2.test/x", extra_headers=h)
        self.assertEqual(self.r.calls, [])

    def test_retry_once_only_for_connection_failure(self):
        a, _ = self.clients(); self.r.status = 0
        a.call("GET", "/v1/admin/uploads")
        self.assertEqual(len(self.r.calls), 2)
        self.assertEqual(self.r.calls[0], self.r.calls[1])
        self.r.calls.clear(); self.r.status = 503
        a.call("GET", "/v1/admin/uploads")
        self.assertEqual(len(self.r.calls), 1)
        self.r.calls.clear(); self.r.status = 0
        a.call("GET", "/v1/admin/uploads", retry_000=False)
        self.assertEqual(len(self.r.calls), 1)

    def test_alternate_actor_keeps_access_pair_separate(self):
        logs = []
        p = publish.Api({**self.env, "OTHER_EMAIL": "other@invalid", "OTHER_PASSWORD": "fake-other-password"},
                        transport=self.r.publish, cred_prefix="OTHER", log=logs.append)
        p.fresh_token("get"); p.get_doc("job")
        self.assertEqual(json.loads(self.r.calls[0][3])["password"], "fake-other-password")
        self.assertEqual(self.r.calls[1][2]["cf-access-client-secret"], PAIR["CF_ACCESS_CLIENT_SECRET"])
        self.assertNotIn("fake-other-password", str(logs)); self.assertNotIn("fake-access-secret", str(logs))

    def test_non_json_success_body_is_not_echoed(self):
        self.r.body = b"<html>fake-access-secret</html>"
        a, p = self.clients()
        self.assertNotIn("fake-access-secret", str(a.call("GET", "/v1/admin/uploads")))
        self.assertNotIn("fake-access-secret", str(p.publish("job", [])))


class TransportTrustTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"VIBHAGA_ADMIN_ENV": "/nonexistent/offline-test-only"}, clear=True))
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")))
        self.stack.enter_context(patch.object(auth, "read_env_all", side_effect=AssertionError("credential reads forbidden")))
        self.default = SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 1}, check_hostname=True, verify_mode=ssl.CERT_REQUIRED)
        self.empty = SimpleNamespace(cert_store_stats=lambda: {"x509_ca": 0}, check_hostname=True, verify_mode=ssl.CERT_REQUIRED)
        self.create = self.stack.enter_context(patch.object(ssl, "create_default_context", return_value=self.default))
        self.paths = self.stack.enter_context(patch.object(ssl, "get_default_verify_paths", return_value=SimpleNamespace(capath=None)))
        self.certifi = SimpleNamespace(where=lambda: "/synthetic/certifi.pem")
        self.stack.enter_context(patch.dict(sys.modules, {"certifi": self.certifi}))
        self.env = {**auth.fake_env(), **PAIR}

    def install_https(self, reply, stack=None):
        calls = []; contexts = []
        class FakeHTTPS(urllib.request.HTTPSHandler):
            def __init__(inner, *args, **kwargs):
                contexts.append(kwargs.get("context")); super().__init__(*args, **kwargs)
            def https_open(inner, req):
                calls.append(req)
                status, raw, headers = reply(req)
                h = Message()
                for k, v in headers.items(): h[k] = v
                response = urllib.response.addinfourl(io.BytesIO(raw), h, req.full_url, status)
                response.msg = "synthetic response"
                return response
        (stack or self.stack).enter_context(patch.object(urllib.request, "HTTPSHandler", FakeHTTPS))
        return calls, contexts

    def test_edge_accepts_honest_user_agent_for_both_actual_clients(self):
        def edge(req):
            h = {k.lower(): v for k, v in req.header_items()}
            if h.get("user-agent", "").startswith("Python-urllib/"):
                return 403, b"error code: 1010", {"Server": "cloudflare"}
            if h.get("user-agent") != "Vibhaga-Onboarding/1.0":
                return 403, b"unknown client", {}
            if "/auth/v1/token?" in req.full_url:
                return 200, json.dumps({"access_token": "fake-jwt", "user": {"id": UID}}).encode(), {}
            return 200, b'{"ready":true,"questions":[]}', {}
        calls, contexts = self.install_https(edge)
        a = auth.Admin(self.env); p = publish.Api(self.env, log=lambda _: None)
        a.token(); self.assertEqual(a.call("GET", "/v1/admin/uploads")[0], 200)
        p.fresh_token("get"); p.get_doc("job")
        self.assertEqual(len(calls), 4)
        self.assertTrue(all(c is self.default for c in contexts))
        for req in calls:
            h = {k.lower(): v for k, v in req.header_items()}
            self.assertEqual(h["user-agent"], "Vibhaga-Onboarding/1.0")
            if "/v1/admin/" in req.full_url:
                self.assertEqual(h["cf-access-client-secret"], PAIR["CF_ACCESS_CLIENT_SECRET"])
                self.assertEqual(h["authorization"], "Bearer fake-jwt")
            else:
                self.assertNotIn("cf-access-client-secret", h)
                self.assertEqual(h["apikey"], "anon")
                self.assertEqual(json.loads(req.data)["password"], self.env["VIBHAGA_ADMIN_PASSWORD"])

    def test_platform_trust_is_preferred(self):
        self.assertIs(auth.checked_tls_context(), self.default)
        self.create.assert_called_once_with()

    def test_missing_default_anchors_use_optional_certifi(self):
        self.create.side_effect = [self.empty, self.default]
        self.assertIs(auth.checked_tls_context(), self.default)
        self.assertEqual(self.create.call_args_list[-1].kwargs, {"cafile": "/synthetic/certifi.pem"})

    def test_missing_all_anchors_fail_safely_before_auth(self):
        self.create.return_value = self.empty
        with patch.dict(sys.modules, {"certifi": None}), patch.object(urllib.request, "build_opener") as opener:
            for client in (auth.Admin(self.env), publish.Api(self.env, log=lambda _: None)):
                with self.assertRaises((SystemExit, publish.Refuse)) as caught:
                    client.token() if isinstance(client, auth.Admin) else client.fresh_token("get")
                self.assertIn("TLS trust configuration", str(caught.exception))
                self.assertIn("SSL_CERT_FILE", str(caught.exception))
            opener.assert_not_called()

    def test_unusable_certifi_bundle_fails_closed(self):
        for fallback in (self.empty, OSError("fake-access-secret")):
            with self.subTest(fallback=type(fallback).__name__):
                self.create.side_effect = [self.empty, fallback]
                with self.assertRaises(auth.TLSConfigurationError) as caught: auth.checked_tls_context()
                self.assertNotIn("fake-access-secret", str(caught.exception))

    def test_explicit_invalid_ca_settings_never_fall_back(self):
        with tempfile.TemporaryDirectory(prefix="offline-trust-") as td:
            for config in ({"SSL_CERT_FILE": "/nonexistent/fake-access-secret"}, {"SSL_CERT_FILE": ""},
                           {"SSL_CERT_DIR": "/nonexistent/fake-access-secret"}, {"SSL_CERT_DIR": ""},
                           {"SSL_CERT_FILE": td}, {"SSL_CERT_DIR": td}):
                with self.subTest(keys=tuple(config)), patch.dict(os.environ, config), patch.object(urllib.request, "build_opener") as opener:
                    result = auth.urllib_transport("POST", "https://sb.test/auth/v1/token?grant_type=password", {}, b"fake-password")
                    self.assertEqual(result[0], 0)
                    diagnostic = auth.response_json(result[0], result[2])["error"]
                    self.assertIn("TLS trust configuration", diagnostic)
                    self.assertNotIn("fake-access-secret", diagnostic)
                    opener.assert_not_called()
            self.create.assert_not_called()

    def test_explicit_ca_file_is_used_without_platform_or_certifi_fallback(self):
        with tempfile.TemporaryDirectory(prefix="offline-trust-") as td:
            ca = Path(td) / "synthetic-ca.pem"; ca.write_text("synthetic")
            with patch.dict(os.environ, {"SSL_CERT_FILE": str(ca)}):
                self.assertIs(auth.checked_tls_context(), self.default)
                self.create.assert_called_once_with(cafile=str(ca), capath=None)
                self.create.reset_mock(); self.create.side_effect = ssl.SSLError("fake-access-secret")
                with self.assertRaises(auth.TLSConfigurationError) as caught: auth.checked_tls_context()
                self.assertNotIn("fake-access-secret", str(caught.exception))
                self.assertEqual(self.create.call_count, 1)

    def test_lazy_hashed_capath_is_not_mistaken_for_missing_trust(self):
        with tempfile.TemporaryDirectory(prefix="offline-trust-") as td:
            (Path(td) / "0123abcd.0").write_text("synthetic lazy CA")
            self.create.return_value = self.empty
            for explicit in (False, True):
                self.create.reset_mock()
                self.paths.return_value = SimpleNamespace(capath=td)
                with patch.dict(os.environ, {"SSL_CERT_DIR": td} if explicit else {}):
                    self.assertIs(auth.checked_tls_context(), self.empty)
                    self.assertEqual(self.create.call_count, 1)
                    if explicit: self.create.assert_called_once_with(cafile=None, capath=td)

    def test_empty_default_capath_uses_fallback(self):
        with tempfile.TemporaryDirectory(prefix="offline-trust-") as td:
            self.paths.return_value = SimpleNamespace(capath=td)
            self.create.side_effect = [self.empty, self.default]
            self.assertIs(auth.checked_tls_context(), self.default)
            self.assertEqual(self.create.call_count, 2)

    def test_certificate_failure_is_safe_and_never_retried(self):
        for wrapped in (False, True):
            with self.subTest(wrapped=wrapped):
                error = ssl.SSLCertVerificationError(1, "fake-access-secret fake-password")
                def broken(req): raise urllib.error.URLError(error) if wrapped else error
                with contextlib.ExitStack() as local:
                    calls, _ = self.install_https(broken, stack=local)
                    a = auth.Admin(self.env)
                    st, js = a.call("GET", "/v1/admin/uploads")
                    self.assertEqual(st, 0); self.assertEqual(len(calls), 1)
                    self.assertIn("TLS certificate verification failed", js["error"])
                    self.assertNotIn("fake-access-secret", str(js))
                    for grant in (a.token, lambda: publish.Api(self.env, log=lambda _: None).fresh_token("get")):
                        with self.assertRaises((SystemExit, publish.Refuse)) as caught: grant()
                        self.assertIn("TLS certificate verification failed", str(caught.exception))
                        self.assertNotIn("fake-password", str(caught.exception))
                    with self.assertRaises(publish.Refuse) as caught: publish.Api(self.env).publish("job", [])
                    self.assertIn("TLS certificate verification failed", str(caught.exception))
                    self.assertEqual(len(calls), 4)

    def test_cloudflare_1010_reaches_public_errors_without_reflection(self):
        calls, _ = self.install_https(lambda _: (403, b"error code: 1010\n", {"Server": "cloudflare", "Secret": "fake-access-secret"}))
        a = auth.Admin(self.env); p = publish.Api(self.env, log=lambda _: None)
        self.assertIn("Cloudflare error 1010", a.call("GET", "/v1/admin/uploads")[1]["error"])
        self.assertIn("Cloudflare error 1010", p.publish("job", [])[1]["error"])
        for grant in (a.token, lambda: p.fresh_token("get")):
            with self.assertRaises((SystemExit, publish.Refuse)) as caught: grant()
            self.assertIn("Cloudflare error 1010", str(caught.exception))
            self.assertNotIn("fake-access-secret", str(caught.exception))
        self.assertEqual(len(calls), 4)

    def test_unexpected_success_status_at_grant_never_echoes_upstream_error(self):
        self.install_https(lambda _: (201, b'{"error":"fake-access-secret"}', {}))
        for grant in (auth.Admin(self.env).token, lambda: publish.Api(self.env).fresh_token("get")):
            with self.assertRaises((SystemExit, publish.Refuse)) as caught: grant()
            self.assertNotIn("fake-access-secret", str(caught.exception))
            self.assertIn("HTTP 201", str(caught.exception))

    def test_unknown_403_and_reflected_marker_remain_withheld(self):
        for raw in (b"fake-access-secret", b"error code: 10100", b"error code: 1010 fake-access-secret",
                    b"<html>error code: 1010 fake-access-secret</html>", b"error code: 1010" + b" " * 5000,
                    b"\x00vibhaga:tls-config", b'{"error":"fake-access-secret"}'):
            with self.subTest(length=len(raw)), contextlib.ExitStack() as local:
                self.install_https(lambda _: (403, raw, {}), stack=local)
                result = auth.Admin(self.env).call("GET", "/v1/admin/uploads")
                self.assertEqual(result, (403, {"error": "HTTP 403 (response body withheld)"}))

    def test_error_body_read_is_bounded_and_closed(self):
        class BoundedBody(io.BytesIO):
            sizes = []
            def read(inner, size=-1):
                self.assertGreater(size, 0); self.assertLessEqual(size, 256)
                inner.sizes.append(size); return super().read(size)
        body = BoundedBody(b"error code: 1010")
        error = urllib.error.HTTPError("https://api.test", 403, "fake-access-secret", {}, body)
        with patch.object(urllib.request.OpenerDirector, "open", side_effect=error):
            st, _, raw = auth.urllib_transport("GET", "https://api.test/v1/admin/uploads", {}, None)
        self.assertIn("Cloudflare error 1010", auth.response_json(st, raw)["error"])
        self.assertEqual(len(body.sizes), 1); self.assertTrue(body.closed)


class PublishGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")))
        self.stack.enter_context(patch.object(auth, "read_env_all", side_effect=AssertionError("credential reads forbidden")))
        self.stack.enter_context(patch.object(publish.time, "sleep"))
        self.td = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="access-guardrails-")))
        self.scope = {"grade": 8, "subject": "Mathematics", "medium": "sinhala"}
        self.doc = {"paper": {"paper_id": UID, "paper_metadata": self.scope}, "questions": [
            {"question_id": f"00000000-0000-4000-8000-{n:012d}", "question_number": n, "sort_order": n - 1,
             "question_text": f"Synthetic Q{n}", "ingestion_metadata": {"needs_human_review": True},
             "answers": [{"answer_id": f"10000000-0000-4000-8000-{n:012d}", "approach": "fake", "final_answer_latex": "$1$"}]}
            for n in range(1, 4)]}
        self.staged = self.td / "synthetic-staged.json"; self.ids = self.td / "synthetic-ids.json"
        self.logs = []; self.headers = []; self.t77_calls = []

    def run_fake(self, fake=None, scope=None, accept=0, dry=False, t77_status=0, t77=None, ids=None):
        self.staged.write_text(json.dumps(self.doc))
        self.fake = fake or publish.FakeAdmin(self.doc)
        def transport(m, u, h, b):
            self.headers.append((u, {k.lower(): v for k, v in h.items()}))
            return self.fake(m, u, h, b)
        self.api = publish.Api({**publish.FAKE_ENV, **PAIR}, transport=transport, log=self.logs.append)
        def check(path, ids):
            self.t77_calls.append((path, ids, len(self.fake.publishes)))
            return t77_status
        try:
            return publish.run_publish(self.api, "fake-job", self.staged, self.scope if scope is None else scope,
                                       accept, ids, None, self.ids, dry, t77 or check, log=self.logs.append)
        except publish.Refuse as e:
            self.logs.append(str(e)); return e.code
        finally:
            publish.finish(self.api, log=self.logs.append)

    def test_api_valid_drafts_remain_exportable_and_repairable(self):
        for draft in ({"question_id": UID, "question_text": "Draft no number"},
                      {"question_id": "draft-1", "question_number": 1, "question_text": "Draft temporary id"},
                      {"question_id": "fake-access-secret", "question_number": "fake-access-secret", "question_text": "Draft arbitrary label"}):
            with self.subTest(draft=draft):
                fake = publish.FakeAdmin({"paper": self.doc["paper"], "questions": [draft]}); logs = []
                api = publish.Api(publish.FAKE_ENV, fake, log=logs.append)
                out = self.td / "draft.json"
                try:
                    self.assertEqual(publish.cmd_get(api, "job", out, log=logs.append), 0)
                    self.assertEqual(json.loads(out.read_text())["questions"], [draft])
                    repaired = {**draft, "question_text": "Repaired draft text"}
                    out.write_text(json.dumps({"questions": [repaired]}))
                    self.assertEqual(publish.cmd_put(api, "job", out, self.scope, False, False, log=logs.append), 0)
                    self.assertEqual(fake.doc["questions"][0], {**repaired, "sort_order": 0})
                    self.assertNotIn("fake-access-secret", str(logs))
                finally:
                    publish.finish(api, log=logs.append)

    def test_publishing_subset_preserves_unrelated_api_valid_drafts(self):
        drafts = [{"question_id": UID, "question_text": "Draft no number"},
                  {"question_id": "draft-1", "question_number": 1, "question_text": "Draft temporary id"},
                  {"question_id": "fake-access-secret", "question_number": "fake-access-secret", "question_text": "Unrelated draft"}]
        self.doc["questions"].extend(drafts)
        selected = self.td / "selected.json"; selected.write_text(json.dumps([self.doc["questions"][0]["question_id"]]))
        self.assertEqual(self.run_fake(ids=selected), 0)
        self.assertEqual(self.fake.publishes, [[self.doc["questions"][0]["question_id"]]])
        self.assertEqual(self.fake.doc["questions"][-3:], drafts)
        self.assertNotIn("fake-access-secret", str(self.logs))

    def test_publication_validation_applies_to_selected_drafts_only(self):
        for draft in ({"question_id": UID, "question_text": "Draft no number"},
                      {"question_id": "draft-1", "question_number": 1, "question_text": "Draft temporary id"},
                      {"question_id": UID, "question_number": "fake-access-secret", "question_text": "Draft arbitrary label"}):
            with self.subTest(draft=draft):
                self.logs.clear(); self.doc["questions"] = [draft]
                self.assertEqual(self.run_fake(), 3)
                self.assertEqual(self.fake.publishes, [])
                self.assertNotIn("fake-access-secret", str(self.logs))

    def test_draft_repair_refusals_never_echo_arbitrary_labels(self):
        draft = {"question_id": "draft-1", "question_number": "fake-access-secret", "question_text": "Draft", "published": True}
        with self.assertRaises(publish.Refuse) as caught: publish.merge_questions([draft], [], True, False)
        self.assertNotIn("fake-access-secret", str(caught.exception))
        self.staged.write_text(json.dumps(self.doc))
        response = json.loads(json.dumps(self.doc)); response["questions"][0]["question_number"] = "fake-access-secret"
        response["questions"][0]["ingestion_metadata"]["needs_human_review"] = False
        recorder = Recorder(body={"ready": True, **response}); logs = []
        def transport(method, url, headers, body):
            if method == "GET": return 200, json.dumps({"ready": True, **self.doc}).encode()
            return recorder.publish(method, url, headers, body)
        api = publish.Api(auth.fake_env(), transport, log=logs.append)
        with self.assertRaises(publish.Refuse) as caught:
            publish.cmd_put(api, "job", self.staged, self.scope, False, False, log=logs.append)
        self.assertNotIn("fake-access-secret", str(caught.exception)); self.assertNotIn("fake-access-secret", str(logs))

    def test_success_counters_and_lists_refuse_secret_reflection_before_logging(self):
        for dry, fields in ((True, ("signatures_at_risk", "unchanged_count", "questions")),
                            (False, ("published", "sub_questions", "answers", "sub_answers", "reflagged", "unchanged"))):
            for field in fields:
                for value in ("fake-access-secret", True, -1, None, 1.5, ["fake-access-secret"], {"nested": "fake-access-secret"}):
                    with self.subTest(dry=dry, field=field, value=value):
                        self.logs.clear()
                        class Reflect(publish.FakeAdmin):
                            def __call__(inner, method, url, headers, body):
                                status, raw = super().__call__(method, url, headers, body)
                                if url.endswith("/publish") and bool(json.loads(body).get("dry_run")) == dry:
                                    js = json.loads(raw); js[field] = value; raw = json.dumps(js).encode()
                                return status, raw
                        rc = self.run_fake(Reflect(self.doc))
                        self.assertNotIn("fake-access-secret", str(self.logs))
                        self.assertEqual(rc, 4 if dry else 5)
                        self.assertIn("malformed publish response (body withheld)", self.logs)

    def test_server_scope_reflection_is_not_logged_on_mismatch(self):
        fake = publish.FakeAdmin(self.doc); fake.doc["paper"]["paper_metadata"]["subject"] = "fake-access-secret"
        self.assertEqual(self.run_fake(fake), 3)
        self.assertNotIn("fake-access-secret", str(self.logs))

    def test_get_put_stats_reflection_refused_without_stripping_staged_content(self):
        self.staged.write_text(json.dumps(self.doc))
        for command in ("get", "put"):
            for field in ("stats", "question_number"):
                with self.subTest(command=command, field=field):
                    logs = []; response = json.loads(json.dumps(self.doc))
                    if field == "stats": response["stats"] = {"questions": "fake-access-secret"}
                    else: response["questions"][0]["question_number"] = "fake-access-secret"
                    recorder = Recorder(body={"ready": True, **response})
                    def transport(method, url, headers, body):
                        if command == "put" and method == "GET": return 200, json.dumps({"ready": True, **self.doc}).encode()
                        return recorder.publish(method, url, headers, body)
                    api = publish.Api({**auth.fake_env(), **PAIR}, transport, log=logs.append)
                    def run():
                        if command == "get": return publish.cmd_get(api, "job", self.td / "output.json", log=logs.append)
                        return publish.cmd_put(api, "job", self.staged, self.scope, False, False, log=logs.append)
                    if field == "stats":
                        with self.assertRaises(publish.Refuse): run()
                    else:
                        self.assertEqual(run(), 0)
                    self.assertNotIn("fake-access-secret", str(logs))
        logs = []; response = json.loads(json.dumps(self.doc)); response["questions"][0]["question_text"] = "verbatim staged content"
        response["stats"] = {"questions": 3, "extra_server_field": "fake-access-secret"}
        response["paper"]["paper_metadata"]["subject"] = "fake-access-secret"
        recorder = Recorder(body={"ready": True, **response}); api = publish.Api(auth.fake_env(), recorder.publish, log=logs.append)
        out = self.td / "verbatim.json"
        self.assertEqual(publish.cmd_get(api, "job", out, log=logs.append), 0)
        self.assertEqual(json.loads(out.read_text()), response)
        self.assertNotIn("fake-access-secret", str(logs))

    def test_six_guardrails_and_fresh_grants_with_access(self):
        fake = publish.FakeAdmin(self.doc, flake_first=True)
        observed = []
        fake.on_publish = lambda _: observed.append(json.loads(self.ids.read_text()))
        self.assertEqual(self.run_fake(fake), 0)
        ids = [q["question_id"] for q in self.doc["questions"]]
        self.assertTrue(observed); self.assertEqual(observed[0]["question_ids"], ids)
        self.assertEqual(len(observed[0]["questions"][0]["answer_ids"]), 1)
        self.assertEqual(fake.publishes, [[i] for i in ids])
        self.assertEqual(fake.grants, 3); self.assertEqual(fake.logouts, 1)
        self.assertTrue(fake.calls[-1][1].endswith("/auth/v1/logout?scope=global"))
        self.assertEqual(self.t77_calls, [(self.staged, ids, 3)])
        self.assertTrue(all(q["ingestion_metadata"]["needs_human_review"] is True for q in fake.doc["questions"]))
        self.assertEqual(sum("FROM auth.sessions" in s or "FROM auth.refresh_tokens" in s for s in self.logs), 2)
        for url, h in self.headers:
            self.assertEqual("cf-access-client-secret" in h, "/v1/admin/" in url)
        for secret in (*PAIR.values(), "tok1", "tok2", "tok3"):
            self.assertNotIn(secret, str(self.logs))

    def test_scope_mismatch_refused(self):
        self.assertEqual(self.run_fake(scope={**self.scope, "grade": 7}), 3)
        self.assertEqual(self.fake.publishes, [])

    def test_unflagged_refused(self):
        self.doc["questions"][0]["ingestion_metadata"]["needs_human_review"] = False
        self.assertEqual(self.run_fake(), 3); self.assertEqual(self.fake.publishes, [])

    def test_dry_run_unexpected_success_status_withholds_body(self):
        for status in (201, 202):
            with self.subTest(status=status):
                self.logs.clear()
                class UnexpectedStatus(publish.FakeAdmin):
                    def __call__(inner, method, url, headers, body):
                        if url.endswith("/publish") and json.loads(body).get("dry_run"):
                            return status, b'{"error":"fake-access-secret","token":"fake-jwt"}'
                        return super().__call__(method, url, headers, body)
                self.assertEqual(self.run_fake(UnexpectedStatus(self.doc)), 4)
                self.assertIn(f"HTTP {status}", str(self.logs))
                self.assertNotIn("fake-access-secret", str(self.logs)); self.assertNotIn("fake-jwt", str(self.logs))
                self.assertEqual(self.fake.publishes, []); self.assertEqual(self.fake.logouts, 1)
                self.assertEqual(self.t77_calls, [])

    def test_signatures_zero_requires_explicit_acceptance(self):
        self.assertEqual(self.run_fake(accept=None), 4); self.assertEqual(self.fake.publishes, [])
        self.assertEqual(self.run_fake(accept=1), 4); self.assertEqual(self.fake.publishes, [])
        self.assertEqual(self.run_fake(dry=True), 0); self.assertEqual(self.fake.publishes, [])

    def test_t77_mismatch_fails_run(self):
        self.assertEqual(self.run_fake(t77_status=1), 1); self.assertEqual(len(self.t77_calls), 1)

    def test_publish_stops_on_access_denial_without_retry(self):
        self.assertEqual(self.run_fake(publish.FakeAdmin(self.doc, fail_publish_at=2, fail_status=403)), 5)
        self.assertEqual(len(self.fake.publishes), 2); self.assertTrue(self.ids.exists()); self.assertEqual(self.t77_calls, [])
        self.assertEqual(self.fake.logouts, 1)

    def test_w7_self_test_28_checks_with_only_synthetic_inputs(self):
        docs = publish.HERE.parent.parent.parent
        run = docs / "question-onboarding" / "runs" / "2026-09-07-run11-g8-nwp-2024"
        doc = {"paper": self.doc["paper"], "questions": []}
        for n in range(1, 6):
            q = json.loads(json.dumps(self.doc["questions"][0]))
            q.update(question_id=f"00000000-0000-4000-8000-{n:012d}", question_number=n, sort_order=n - 1)
            q["answers"][0]["answer_id"] = f"10000000-0000-4000-8000-{n:012d}"
            doc["questions"].append(q)
        subs = [{"paper_slug": f"2024-nwp-g8-2nd-term-maths-paper-{sub}-sinhala", "scope": self.scope,
                 "job_id": f"synthetic-{sub}", "source_questions": count, "totals": {"published": count},
                 "questions": [{"n": n, "question_id": UID, "disposition": "published"} for n in range(1, count + 1)]}
                for sub, count in (("I", 5), ("II", 15))]
        fixtures = {run / "questions-I.json": json.dumps(doc), run / "manifest.json": json.dumps({"sub_papers": subs})}
        fixtures.update({docs / "question-onboarding" / "coverage" / f"2026-09-07-{sp['paper_slug']}.json": json.dumps(sp) for sp in subs})
        read_text, exists, glob = Path.read_text, Path.exists, Path.glob
        def synthetic_read(path, *args, **kwargs):
            if path in fixtures: return fixtures[path]
            self.assertTrue(path.is_relative_to(self.td), "non-synthetic input forbidden")
            return read_text(path, *args, **kwargs)
        def synthetic_exists(path):
            if path in fixtures: return True
            if path.is_relative_to(run): return False
            return exists(path)
        def synthetic_glob(path, pattern):
            if path == run: return iter(())
            self.assertTrue(path.is_relative_to(self.td), "non-synthetic input forbidden")
            return glob(path, pattern)
        with patch.dict(os.environ, {"RUN11_STAGED": "/nonexistent/offline-test-only"}), \
             patch.object(Path, "read_text", synthetic_read), patch.object(Path, "exists", synthetic_exists), \
             patch.object(Path, "glob", synthetic_glob), patch.object(publish.tempfile, "mkdtemp", return_value=str(self.td)), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            result = publish.self_test()
        self.assertEqual(result, 0, output.getvalue())
        self.assertIn("28/28 checks passed", output.getvalue())

    def test_publish_loop_does_not_retry_deterministic_tls_failures(self):
        for sentinel in (auth.TLS_CONFIG, auth.TLS_VERIFY):
            with self.subTest(sentinel=sentinel):
                self.logs.clear()
                class BrokenTLS(publish.FakeAdmin):
                    def __call__(inner, *args):
                        status, raw = super().__call__(*args)
                        return (status, sentinel) if status == 0 else (status, raw)
                fake = BrokenTLS(self.doc, fail_publish_at=1, fail_status=0)
                self.assertEqual(self.run_fake(fake), 5)
                self.assertEqual(len(fake.publishes), 1)
                self.assertNotIn("retrying once", str(self.logs))
                self.assertIn("TLS", str(self.logs))
                self.assertEqual(fake.logouts, 1)
                self.assertEqual(self.t77_calls, [])
                self.assertTrue(self.ids.exists())

    def test_tls_logout_failure_still_prints_revocation_sql(self):
        for sentinel in (auth.TLS_CONFIG, auth.TLS_VERIFY):
            logs = []; calls = []
            def transport(*args): calls.append(args); return 0, sentinel
            api = publish.Api(publish.FAKE_ENV, transport=transport, log=logs.append)
            api.token = "fake-jwt"; api.user_id = UID
            publish.finish(api, log=logs.append)
            self.assertEqual(len(calls), 1); self.assertIsNone(api.token)
            self.assertIn("HTTP 0", str(logs))
            self.assertIn("FROM auth.sessions", str(logs))
            self.assertIn("FROM auth.refresh_tokens", str(logs))

    def test_real_t77_with_in_memory_fake_psql(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("offline_t77", publish.HERE / "t77-staged-vs-published.py")
        t77 = importlib.util.module_from_spec(spec); spec.loader.exec_module(t77)
        rows = [{"question_id": q["question_id"], "question_number": q["question_number"], "question_text": q["question_text"],
                 "question_text_sinhala": None, "diagram_dsl": None, "needs_human_review": True,
                 "answers": [{**a, "diagram_dsl": None} for a in q["answers"]], "parts": None} for q in self.doc["questions"]]
        def runner(path, ids):
            with patch.dict(os.environ, {"DATABASE_URL": "postgres://fake.invalid/fake"}), patch.object(sys, "argv", ["t77", str(path), "--ids", json.dumps(ids)]), \
                 patch.object(t77.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, json.dumps(rows), "")) as fake_psql, \
                 contextlib.redirect_stdout(io.StringIO()) as out, io.StringIO(json.dumps(self.doc)) as staged, \
                 patch.object(t77, "open", return_value=staged, create=True):
                with self.assertRaises(SystemExit) as exited: t77.main()
                rc = exited.exception.code
            self.assertEqual(fake_psql.call_args.args[0][0], "psql")
            self.logs.append(out.getvalue()); return rc
        self.assertEqual(self.run_fake(t77=runner), 0)
        self.assertIn("0 mismatch(es)", str(self.logs))
        rows[0]["question_text"] = "planted mismatch"
        self.assertEqual(self.run_fake(t77=runner), 1)
        self.assertIn("MISMATCH", str(self.logs))


if __name__ == "__main__":
    unittest.main()
