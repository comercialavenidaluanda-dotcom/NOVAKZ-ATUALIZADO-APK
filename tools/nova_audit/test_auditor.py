import tempfile
import zipfile
from pathlib import Path

from auditor import _scan_tree


def test_detects_historical_local_balance_fallback():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "Main.kt").write_text(
            "const val DEFAULT_SANDBOX_BALANCE = 1000.0\n",
            encoding="utf-8",
        )
        findings = _scan_tree(root)
        assert any(f.check == "balance-source-of-truth" for f in findings)


def test_does_not_flag_normal_supabase_user_reference_as_secret():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root / "Supabase.kt").write_text(
            'val url = BuildConfig.SUPABASE_URL\n'
            'val key = BuildConfig.SUPABASE_PUBLISHABLE_KEY\n'
            'val user = supabase.auth.currentUserOrNull()\n',
            encoding="utf-8",
        )
        findings = _scan_tree(root)
        assert not any(f.check == "secret-exposure" for f in findings)
