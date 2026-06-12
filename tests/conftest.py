"""Test framework conftest — shared fixtures and test helpers."""
import sys, os, tempfile, json, shutil
import pytest

# ── test root ──
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ── fixtures ──

@pytest.fixture(scope="session")
def project_root():
    return PROJECT_ROOT

@pytest.fixture(scope="session")
def sample_gov_protocols():
    """Load G001-G005 YAML for governance parser tests."""
    import yaml
    base = os.path.join(PROJECT_ROOT, "gov_protocol")
    protocols = {}
    for fname in sorted(os.listdir(base)):
        if fname.endswith(".yaml"):
            k = fname.replace(".yaml", "")
            with open(os.path.join(base, fname), encoding="utf-8") as f:
                protocols[k] = yaml.safe_load(f)
    return protocols

@pytest.fixture
def temp_workspace():
    """A temporary directory that looks like a minimal silicon-civilization workspace."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)

@pytest.fixture
def hash_index_factory():
    """Create or load hash_index for kb and integrity tests."""
    def _load(path=None):
        import json
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {}
    return _load

# ── helpers ──

def assert_almost_equal(a, b, eps=1e-6):
    assert abs(a - b) < eps, f"{a} != {b} (eps={eps})"
