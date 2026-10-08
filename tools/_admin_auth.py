#!/usr/bin/env python3
"""
Shared auth + HTTP for the tools that write through the admin API (W1 `paper-prep.py`, W7 `publish.py`) under decision 0014.

- Credentials come ONLY from `Vibhaga-Admin/.env.local` (`VIBHAGA_ADMIN_EMAIL`, `VIBHAGA_ADMIN_PASSWORD`, `NEXT_PUBLIC_SUPABASE_URL`,
  `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_BASE_URL`) — the actor's own identity
  (`question-onboarding/2026-08-08-agent-identities-and-access.md` §3). Nothing here prints a secret.
- `token()` is a Supabase password grant; callers re-obtain it at the start of every stage (run 10's expired mid-run).
- `logout()` is `POST /auth/v1/logout?scope=global` — the client-side sign-out. It is NOT the proof of revocation; the caller
  prints the SQL the orchestrator runs (`auth.sessions`, `auth.refresh_tokens` for the user id) — TRAPS T4.
- Every HTTP call goes through an injectable `transport(method, url, headers, body) -> (status, headers, body_bytes)` so a
  `--self-test` never touches the network.
"""
import json
import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

def _find_env():
    """`Vibhaga-Admin/.env.local` under the umbrella — found by walking up, so the tool works from a worktree too;
    `VIBHAGA_ADMIN_ENV` overrides."""
    if os.environ.get("VIBHAGA_ADMIN_ENV"):
        return Path(os.environ["VIBHAGA_ADMIN_ENV"])
    for parent in Path(__file__).resolve().parents:
        cand = parent / "Vibhaga-Admin" / ".env.local"
        if cand.exists():
            return cand
    return Path("Vibhaga-Admin/.env.local")


ENV_PATH = _find_env()
NEEDED = ("VIBHAGA_ADMIN_EMAIL", "VIBHAGA_ADMIN_PASSWORD", "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY",
          "NEXT_PUBLIC_API_BASE_URL")


def read_env_all(path=ENV_PATH):
    """Every KEY=value in the file (values never printed by any caller)."""
    env = {}
    if not Path(path).exists():
        raise SystemExit(f"{path} not found — the actor's credentials live there and nowhere else")
    for line in Path(path).read_text().splitlines():
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
        if m:
            env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return env


def read_env(path=ENV_PATH):
    env = read_env_all(path)
    missing = [k for k in NEEDED if not env.get(k)]
    if missing:
        raise SystemExit(f"{path} is missing {', '.join(missing)}")
    access_headers(env)
    return {k: env[k] for k in (*NEEDED, *ACCESS_KEYS) if k in env}


ACCESS_KEYS = ("CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET")
GUARDED_HEADERS = {"authorization", "apikey", "host", "cookie", "proxy-authorization"}


def access_headers(env):
    values = [env.get(k, "") for k in ACCESS_KEYS]
    if all(k not in env for k in ACCESS_KEYS):
        return {}
    if not all(isinstance(v, str) and re.fullmatch(r"[!-~]+", v) for v in values):
        raise SystemExit("CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET must both be configured with valid values")
    return dict(zip(("CF-Access-Client-Id", "CF-Access-Client-Secret"), values))


def checked_url(url, base=False):
    try:
        if not isinstance(url, str) or not re.fullmatch(r"[!-~]+", url) or "\\" in url or "#" in url:
            raise ValueError
        p = urllib.parse.urlsplit(url)
        if p.scheme != "https" or not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]+)?", p.netloc):
            raise ValueError
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label) for label in p.hostname.split(".")):
            raise ValueError
        if p.port is not None and not 1 <= p.port <= 65535:
            raise ValueError
        if base and (p.path not in ("", "/") or "?" in url):
            raise ValueError
        return p
    except (ValueError, TypeError, AttributeError):
        raise SystemExit("refused URL: require a trusted HTTPS origin without userinfo or malformed components") from None


def checked_origin(url):
    p = checked_url(url, base=True)
    return f"{p.scheme}://{p.netloc}"


def distinct_origins(api, sb):
    api, sb = checked_origin(api), checked_origin(sb)
    parts = [urllib.parse.urlsplit(url) for url in (api, sb)]
    if (parts[0].hostname, parts[0].port or 443) == (parts[1].hostname, parts[1].port or 443):
        raise SystemExit("admin API and Supabase authentication origins must be distinct")
    return api, sb


def valid_uuid(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) is not None


def checked_headers(headers, extra=False):
    out = {}; seen = set()
    for k, v in (headers or {}).items():
        if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z0-9-]+", k) or not isinstance(v, str) or not re.fullmatch(r"[ -~]*", v):
            raise SystemExit("refused malformed request headers")
        key = k.lower()
        if key in seen or key.startswith("cf-access-") or key in (GUARDED_HEADERS if extra else {"host", "cookie", "proxy-authorization"}):
            raise SystemExit("refused protected request header override")
        seen.add(key); out[k] = v
    return out


def scoped_headers(url, headers, scope, api, sb, cf):
    p = checked_url(url)
    h = checked_headers(headers)
    if scope == "admin":
        if f"{p.scheme}://{p.netloc}" != api or not (p.path == "/v1/admin" or p.path.startswith("/v1/admin/")):
            raise SystemExit("refused request outside the configured admin API origin and /v1/admin path")
        if not re.fullmatch(r"[A-Za-z0-9_./-]+", p.path) or "//" in p.path or any(s in (".", "..") for s in p.path.split("/")):
            raise SystemExit("refused noncanonical admin API path")
        return {**h, **cf}
    if scope == "supabase" and url in (f"{sb}/auth/v1/token?grant_type=password", f"{sb}/auth/v1/logout?scope=global"):
        return h
    raise SystemExit("refused request outside its authentication scope")


USER_AGENT = "Vibhaga-Onboarding/1.0"
TLS_CONFIG = b"\x00vibhaga:tls-config"
TLS_VERIFY = b"\x00vibhaga:tls-verify"
CF_1010 = b"\x00vibhaga:cf-1010"
SAFE_ERRORS = {
    (0, TLS_CONFIG): "TLS trust configuration unavailable or invalid; check SSL_CERT_FILE / SSL_CERT_DIR, repair platform CA trust, or provide certifi when default anchors are absent (verification remains required)",
    (0, TLS_VERIFY): "TLS certificate verification failed; check the server certificate and configured CA trust (verification remains required; no credential diagnosis)",
    (403, CF_1010): "HTTP 403: Cloudflare error 1010 (edge request blocked); check the onboarding User-Agent and edge request rules before changing credentials",
}


class TLSConfigurationError(Exception):
    pass


def _capath_has_anchors(capath):
    if not capath:
        return False
    return any(re.fullmatch(r"[0-9a-fA-F]{8}\.[0-9]+", entry.name) and entry.is_file()
               for directory in capath.split(os.pathsep) if Path(directory).is_dir()
               for entry in Path(directory).iterdir())


def checked_tls_context():
    try:
        explicit = any(k in os.environ for k in ("SSL_CERT_FILE", "SSL_CERT_DIR"))
        cafile, capath = os.environ.get("SSL_CERT_FILE"), os.environ.get("SSL_CERT_DIR")
        if explicit:
            if "SSL_CERT_FILE" in os.environ and (not cafile or not Path(cafile).is_file()):
                raise ValueError
            if "SSL_CERT_DIR" in os.environ and (not capath or any(not p or not Path(p).is_dir() for p in capath.split(os.pathsep))):
                raise ValueError
            lazy_anchors = _capath_has_anchors(capath)
            if not cafile and not lazy_anchors:
                raise ValueError
            context = ssl.create_default_context(cafile=cafile, capath=capath)
        else:
            context = ssl.create_default_context()
            lazy_anchors = not context.cert_store_stats()["x509_ca"] and _capath_has_anchors(ssl.get_default_verify_paths().capath)
        if context.cert_store_stats()["x509_ca"] or lazy_anchors:
            return context
        if not explicit:
            import certifi
            context = ssl.create_default_context(cafile=certifi.where())
            if context.cert_store_stats()["x509_ca"]:
                return context
        raise ValueError
    except (OSError, ValueError, ImportError):
        raise TLSConfigurationError(SAFE_ERRORS[(0, TLS_CONFIG)]) from None


def response_error(status, raw):
    diagnostic = SAFE_ERRORS.get((status, raw)) if isinstance(raw, bytes) else None
    if isinstance(raw, dict) and isinstance(raw.get("error"), str):
        diagnostic = next((message for (code, _), message in SAFE_ERRORS.items()
                           if status == code and raw["error"] == message), None)
    return diagnostic or f"HTTP {status} (response body withheld)"


def response_json(status, raw):
    if not 200 <= status < 300:
        return {"error": response_error(status, raw)}
    try:
        return json.loads(raw) if raw else {}
    except (ValueError, UnicodeError):
        return {"error": "invalid JSON response (body withheld)"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def urllib_transport(method, url, headers, body):
    try:
        context = checked_tls_context()
    except TLSConfigurationError:
        return 0, {}, TLS_CONFIG
    h = {k: v for k, v in (headers or {}).items() if k.lower() != "user-agent"}
    req = urllib.request.Request(url, data=body, method=method, headers={**h, "User-Agent": USER_AGENT})
    try:
        with urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context)).open(req, timeout=60) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        raw = b""
        try:
            if e.code == 403:
                candidate = e.read(129)
                if len(candidate) <= 128 and re.fullmatch(rb"[ \t\r\n]*error code: 1010[ \t\r\n]*", candidate):
                    raw = CF_1010
        except (OSError, ValueError):
            pass
        finally:
            e.close()
        return e.code, {}, raw
    except ssl.SSLCertVerificationError:
        return 0, {}, TLS_VERIFY
    except (urllib.error.URLError, OSError, ValueError) as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLCertVerificationError):
            return 0, {}, TLS_VERIFY
        return 0, {}, b"connection failed"  # the curl loop's `000`


class Admin:
    def __init__(self, env=None, transport=urllib_transport):
        self.env = read_env() if env is None else env
        self.t = transport
        self.cf = access_headers(self.env)
        self.api, self.sb = distinct_origins(self.env["NEXT_PUBLIC_API_BASE_URL"], self.env["NEXT_PUBLIC_SUPABASE_URL"])
        self.access = None
        self.user_id = None

    def token(self):
        """Fresh password grant. Call at the start of each stage."""
        st, _, body = self.t("POST", f"{self.sb}/auth/v1/token?grant_type=password",
                             {"apikey": self.env["NEXT_PUBLIC_SUPABASE_ANON_KEY"], "Content-Type": "application/json"},
                             json.dumps({"email": self.env["VIBHAGA_ADMIN_EMAIL"], "password": self.env["VIBHAGA_ADMIN_PASSWORD"]}).encode())
        if st != 200:
            raise SystemExit(f"sign-in failed: {response_error(st, body)} (credentials are not printed)")
        d = response_json(st, body)
        if not isinstance(d, dict) or not isinstance(d.get("access_token"), str) or not re.fullmatch(r"[!-~]+", d["access_token"]):
            raise SystemExit("sign-in failed: invalid response (body withheld)")
        self.access = d["access_token"]
        user = d.get("user")
        uid = user.get("id") if isinstance(user, dict) else None
        self.user_id = uid if isinstance(uid, str) and re.fullmatch(r"[0-9a-fA-F-]{36}", uid) else None
        return self.access

    def call(self, method, path, body=None, retry_000=True, raw_url=None, extra_headers=None):
        """Admin API call; retries ONCE on a connection error (`000`), never on a 4xx/5xx."""
        extra = checked_headers(extra_headers, extra=True)
        if raw_url is not None:
            checked_url(raw_url)
            url, headers = raw_url, extra
        else:
            if not isinstance(path, str) or not path.startswith("/"):
                raise SystemExit("refused nonrelative admin API path")
            url = f"{self.api}{path}"
            headers = scoped_headers(url, {"Authorization": f"Bearer {self.access}", "Content-Type": "application/json", **extra},
                                     "admin", self.api, self.sb, self.cf)
        data = None if body is None else (body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode())
        st, h, out = self.t(method, url, headers, data)
        if st == 0 and retry_000 and out not in (TLS_CONFIG, TLS_VERIFY):
            st, h, out = self.t(method, url, headers, data)
        return st, response_json(st, out)

    def logout(self):
        st, _, _ = self.t("POST", f"{self.sb}/auth/v1/logout?scope=global",
                          {"apikey": self.env["NEXT_PUBLIC_SUPABASE_ANON_KEY"], "Authorization": f"Bearer {self.access}"}, None)
        self.access = None
        return st

    def revocation_sql(self):
        uid = self.user_id or "<actor user_id>"
        if not re.fullmatch(r"[0-9a-fA-F-]{36}|<actor user_id>", uid):
            uid = uid.replace("'", "''")  # never a valid Supabase user id; kept quotable rather than trusted
        return (f"-- run on the merged Supabase project; both must be 0 before the run is done (T4)\n"
                f"SELECT count(*) AS sessions FROM auth.sessions WHERE user_id = '{uid}';\n"
                f"SELECT count(*) AS refresh_tokens FROM auth.refresh_tokens WHERE user_id = '{uid}' AND revoked = false;")


def fake_transport(routes):
    """For self-tests: routes = {(method, url_substring): (status, body_obj_or_callable)}; records every call."""
    calls = []

    def t(method, url, headers, body):
        calls.append((method, url, body))
        for (m, frag), resp in routes.items():
            if m == method and frag in url:
                status, out = resp(body) if callable(resp) else resp
                return status, {}, (out if isinstance(out, bytes) else json.dumps(out).encode())
        return 404, {}, b'{"error":"no fake route"}'

    t.calls = calls
    return t


def fake_env():
    return {"VIBHAGA_ADMIN_EMAIL": "actor@example.test", "VIBHAGA_ADMIN_PASSWORD": "x", "NEXT_PUBLIC_SUPABASE_URL": "https://sb.test",
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": "anon", "NEXT_PUBLIC_API_BASE_URL": "https://api.test"}


if __name__ == "__main__":
    raise SystemExit("Shared module, not a self-test command. Run python3 -m unittest discover -s .devin/skills/_maths-onboarding -p 'test_*.py'; use paper-prep.py preflight for live readiness.")
