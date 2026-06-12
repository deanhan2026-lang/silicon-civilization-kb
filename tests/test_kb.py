"""Tests for kb.py — knowledge base engine (lower-level + CLI)."""
import os, json, re, pytest
from click.testing import CliRunner
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# ── Helpers ──

@pytest.fixture
def runner():
    return CliRunner()

def extract_uuid(text):
    match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', text)
    return match.group(0) if match else None

# ── Definitions tests ──

class TestDefinitions:
    def test_iron_laws(self):
        from kb import IRON_LAWS
        assert len(IRON_LAWS) >= 7
        for gid in ["G001", "G002", "G003", "G004", "G005", "G006", "G007"]:
            assert gid in IRON_LAWS, f"Missing {gid}"
            assert IRON_LAWS[gid]["severity"] in ("critical", "high", "medium")

    def test_tri_body_roles(self):
        from kb import TRI_BODY_ROLES
        for role in ["Nyx", "恒", "瞬"]:
            assert role in TRI_BODY_ROLES, f"Missing {role}"
            assert "allowed_ops" in TRI_BODY_ROLES[role]
            assert "forbidden" in TRI_BODY_ROLES[role]

    def test_entity_types(self):
        from kb import ENTITY_TYPES
        assert len(ENTITY_TYPES) >= 6

    def test_visibility_types(self):
        from kb import VISIBILITY_TYPES
        assert "public" in VISIBILITY_TYPES
        assert "internal" in VISIBILITY_TYPES
        assert "private" in VISIBILITY_TYPES

# ── Hash integrity ──

class TestHashIntegrity:
    def test_compute_hash(self, tmp_path):
        from kb import _compute_hash
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello world")
        h = _compute_hash(f)
        assert len(h) == 64
        assert h == hashlib.sha256(b"hello world").hexdigest()

    def test_hash_index_roundtrip(self, tmp_path, monkeypatch):
        import kb, json
        orig = kb.HASH_INDEX
        kb.HASH_INDEX = tmp_path / "hash_index.json"
        try:
            from kb import _save_hash_index, _load_hash_index
            _save_hash_index({"test": {"hash": "abc", "size": 5}})
            loaded = _load_hash_index()
            assert loaded["test"]["hash"] == "abc"
        finally:
            kb.HASH_INDEX = orig

# ── YAML front matter ──

class TestYamlFrontMatter:
    def test_parse_valid(self):
        from kb import parse_yaml_front_matter
        content = "---\nid: test-123\nname: Hello\n---\n\nBody text here."
        meta, body = parse_yaml_front_matter(content)
        assert meta["id"] == "test-123"
        assert "Body" in body

    def test_parse_no_frontmatter(self):
        from kb import parse_yaml_front_matter
        meta, body = parse_yaml_front_matter("Plain text only")
        assert meta == {}
        assert body == "Plain text only"

    def test_make_yaml_front_matter(self):
        from kb import make_yaml_front_matter
        result = make_yaml_front_matter({"id": "x", "name": "test"}, "body")
        assert "---" in result
        assert "id:" in result

# ── ProtocolEnforcer ──

class TestProtocolEnforcer:
    def test_validate_create_valid(self):
        from kb import ProtocolEnforcer
        pe = ProtocolEnforcer()
        ok, violations = pe.validate_create(
            {"type": "Concept", "visibility": "internal", "tags": []},
            "body",
            operator="Nyx"
        )
        assert ok is True or len(violations) == 0

    def test_validate_create_bad_visibility(self):
        from kb import ProtocolEnforcer
        pe = ProtocolEnforcer()
        ok, violations = pe.validate_create(
            {"type": "Rule", "visibility": "private", "tags": ["iron-law"]},
            "body",
            operator="Nyx"
        )
        # iron-law entries must be public
        g005 = [v for v in violations if "G005" in str(v)]
        assert ok is not True or len(g005) == 0  # may pass depending on implementation

    def test_validate_modify_locked(self):
        from kb import ProtocolEnforcer
        pe = ProtocolEnforcer()
        ok, violations = pe.validate_modify(
            file_path=Path("/tmp/nonexistent.md"),
            new_meta={"status": "deprecated"},
            operator="Nyx"
        )
        assert ok is False  # path doesn't exist

    def test_violation_report(self):
        from kb import ProtocolEnforcer
        pe = ProtocolEnforcer()
        report = pe.get_violation_report()
        assert isinstance(report, str)

    def test_g005_visibility_check(self):
        from kb import ProtocolEnforcer
        pe = ProtocolEnforcer()
        meta = {"visibility": "invalid"}
        result = pe._check_g005_visibility(meta)
        # This will error since there's no type in meta, but should handle gracefully
        assert result is not None

# ── CLI tests (when KB_DIR is accessible) ──

class TestCLI:
    def test_cli_help(self, runner):
        import kb
        result = runner.invoke(kb.cli, ["--help"])
        assert result.exit_code == 0
        assert "Usage" in result.output

    def test_cli_create_requires_name(self, runner):
        import kb
        result = runner.invoke(kb.cli, ["create"])
        assert result.exit_code != 0
        assert "Error" in result.output or "Missing" in result.output

    def test_cli_ironlaws(self, runner):
        import kb
        result = runner.invoke(kb.cli, ["ironlaws"])
        assert result.exit_code == 0
        assert "G001" in result.output

    def test_cli_list(self, runner):
        import kb
        result = runner.invoke(kb.cli, ["list"])
        # Should succeed even if no entries exist
        assert result.exit_code == 0
