import importlib.util, os, stat, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("qgen_setup", HERE.parent / "tools" / "qgen-setup.py")
qs = importlib.util.module_from_spec(spec); spec.loader.exec_module(qs)

FULL = {k: f"synthetic-{i}" for i, k in enumerate(qs.REQUIRED)}


class QgenSetupTests(unittest.TestCase):
    def test_collect_reports_missing_by_name(self):
        with mock.patch.dict(os.environ, {"VIBHAGA_ADMIN": "/nonexistent"}, clear=True):
            vals, missing = qs.collect(os.environ)
        self.assertEqual(missing, qs.REQUIRED)

    def test_api_base_falls_back_to_admin_env_local(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".env.local").write_text("NEXT_PUBLIC_API_BASE_URL=https://api.example.test\nNEXT_PUBLIC_SUPABASE_URL=https://dead.example.test\n")
            env = {k: v for k, v in FULL.items() if k not in ("NEXT_PUBLIC_API_BASE_URL", "NEXT_PUBLIC_SUPABASE_URL")}
            env["VIBHAGA_ADMIN"] = d
            vals, missing = qs.collect(env)
        self.assertEqual(vals["NEXT_PUBLIC_API_BASE_URL"], "https://api.example.test")
        self.assertEqual(missing, ["NEXT_PUBLIC_SUPABASE_URL"])   # never taken from .env.local

    def test_write_env_is_0600_and_main_never_prints_values(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "x.env"
            with mock.patch.dict(os.environ, {**FULL, "VIBHAGA_ADMIN": "/nonexistent"}, clear=True), \
                 mock.patch.object(qs, "preflight", return_value=[]), \
                 mock.patch("builtins.print") as pr:
                rc = qs.main(["--out", str(out)])
            self.assertEqual(rc, 0)
            self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
            self.assertIn("DATABASE_URL=synthetic-", out.read_text())
            printed = " ".join(str(c) for c in pr.call_args_list)
            self.assertNotIn("synthetic-", printed)


if __name__ == "__main__":
    unittest.main()
