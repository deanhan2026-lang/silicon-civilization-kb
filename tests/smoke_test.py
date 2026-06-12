"""
Comprehensive smoke test for silicon-civilization-kb.
Monkeypatches hardcoded paths; tests each module with its real API.
"""
import sys, os, tempfile, shutil, json
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))
os.environ["COV_CORE_DISABLE"] = "1"

TMP = Path(tempfile.mkdtemp())
os.environ["MEMGUARD_WORKSPACE"] = str(TMP)

# -- Monkeypatch Z: paths --
def _patch_z():
    enc = TMP / "enc"; auth = TMP / "auth"; sig = TMP / "sig"
    for d in [enc, auth, sig]: d.mkdir(parents=True, exist_ok=True)

    import memguard.crypto as mc
    mc.CryptoConfig.ENCRYPTED_DIR = str(enc)
    mc.CryptoConfig.KEYSHARE_LOCATIONS = {k: str(TMP / f"ks_{k}.json") for k in ['local','nas','n200']}
    mc.CryptoConfig.CRYPTO_CONFIG = str(enc / "crypto_config.json")

    import memguard.integrity as mi
    mi.IntegrityConfig.WORKSPACE_DIR = str(TMP / "ws"); (TMP / "ws").mkdir(exist_ok=True)

    import memguard.auth as ma
    a_dir = str(auth)
    ma.AuthConfig.AUTH_DIR = a_dir
    ma.AuthConfig.KEYS_FILE = os.path.join(a_dir, "node_keys.json")
    ma.AuthConfig.FINGERPRINTS_FILE = os.path.join(a_dir, "device_fingerprints.json")
    ma.AuthConfig.SESSIONS_FILE = os.path.join(a_dir, "sessions.json")

    import memguard.audit as mau
    au_dir = str(TMP / "aud"); Path(au_dir).mkdir(exist_ok=True)
    mau.EnhancedAuditConfig.AUDIT_DIR = au_dir
    mau.EnhancedAuditConfig.AUDIT_LOG = os.path.join(au_dir, "audit_enhanced.jsonl")
    mau.EnhancedAuditConfig.AUDIT_INDEX = os.path.join(au_dir, "audit_index.json")
    mau.EnhancedAuditConfig.ALERT_CONFIG = os.path.join(au_dir, "alert_config.json")

_patch_z()

stats = {"pass": 0, "fail": 0}
def T(name, fn):
    try:
        r = fn()
        assert r is not False, "returned False"
        stats["pass"] += 1
        print(f"  OK  {name}")
    except Exception as e:
        stats["fail"] += 1
        print(f"  FAIL  {name}: {e}")

# ===== 1. Module imports =====
print("=== 1. Module imports ===")
for m in [
    'kb', 'memguard.integrity', 'memguard.crypto', 'memguard.auth', 'memguard.audit',
    'anti_drift.scene_tagger', 'anti_drift.sampler', 'anti_drift.detector', 'anti_drift.archive',
    'gov_parser.loader', 'gov_parser.parser_core', 'gov_parser.rule_matcher', 'gov_parser.circuit_breaker',
    'governance.consensus', 'governance.execution',
]:
    T(f"import {m}", lambda mod=m: __import__(mod, fromlist=[""]))

# ===== 2. KB =====
print("\n=== 2. KB ===")
import kb
T("entity_types >= 6",       lambda: len(kb.ENTITY_TYPES) >= 6)
T("iron_laws >= 7",          lambda: len(kb.IRON_LAWS) >= 7)
T("tri_body_roles 3",        lambda: len(kb.TRI_BODY_ROLES) == 3)
T("G001-G007",               lambda: all(g in kb.IRON_LAWS for g in ["G001","G002","G003","G004","G005","G006","G007"]))
T("parse YAML",              lambda: kb.parse_yaml_front_matter("---\nid: x\n---\nbody")[0]["id"] == "x")
T("YAML no front",           lambda: kb.parse_yaml_front_matter("plain")[0] == {})
T("make YAML",               lambda: "---" in kb.make_yaml_front_matter({"id":"x"}, "body"))
T("ProtocolEnforcer",        lambda: isinstance(kb.ProtocolEnforcer().validate_create({"type":"Concept","visibility":"internal","tags":[]},"body",operator="Nyx"), tuple))
T("violation report",        lambda: isinstance(kb.ProtocolEnforcer().get_violation_report(), str))
T("SHA256 hash",             lambda: len(kb._compute_hash(Path(__file__))) == 64)

# ===== 3. Integrity =====
print("\n=== 3. Integrity ===")
from memguard.integrity import SignatureManager, HashUtils, TrustDomainChecker
ws = TMP / "ws"
sm = SignatureManager()
T("sha256_file",   lambda: len(HashUtils.sha256_file(__file__)) == 64)
T("file_stats",    lambda: isinstance(HashUtils.file_stats(__file__), tuple))

f = ws / "test.md"
f.write_text("# Hello", encoding="utf-8")
T("sign_file",     lambda: sm.sign_file("test.md", "nyx") is not None)
T("verify_file",   lambda: sm.verify_file("test.md")[0] is True)
f.write_text("# MODIFIED", encoding="utf-8")
T("detect_tamper", lambda: sm.verify_file("test.md")[0] is False)
T("TrustDomain",   lambda: TrustDomainChecker() is not None)

# ===== 4. Crypto =====
print("\n=== 4. Crypto ===")
from memguard.crypto import FileEncryptor, KeyManager, AES256Crypto
km = KeyManager()
T("generate_key",  lambda: km.generate_and_store_key() is not None)
key = km.recover_key()
T("key is bytes",  lambda: isinstance(key, bytes) and len(key) == 32)

aes = AES256Crypto()
nonce, ct, tag = aes.encrypt(b"secret123", key)
T("AES encrypt",   lambda: len(ct) > 0)
T("AES decrypt",   lambda: aes.decrypt(nonce, ct, tag, key) == b"secret123")

fe = FileEncryptor()
sf = TMP / "secret.txt"
sf.write_text("中文测试", encoding="utf-8")
T("encrypt_file",  lambda: fe.encrypt_file(str(sf), key) is not None)

# Find enc path: it's in CryptoConfig.ENCRYPTED_DIR / basename + ".encrypted"
import memguard.crypto as mc_
enc_dir = Path(mc_.CryptoConfig.ENCRYPTED_DIR)
enc_path = enc_dir / "secret.txt.encrypted"
T("enc exists",    lambda: enc_path.exists())
dec_path = TMP / "dec.txt"
T("decrypt_file",  lambda: fe.decrypt_file(str(enc_path), key, str(dec_path)) is not None)
T("dec matches",   lambda: dec_path.read_text(encoding="utf-8") == "中文测试")

# ===== 5. Auth =====
print("\n=== 5. Auth ===")
from memguard.auth import AuthManager, PermissionLevel, NodeType
am = AuthManager()
node_id, key = am.register_node("smoke", NodeType.NYX, PermissionLevel.EDITOR)
T("register_node", lambda: len(node_id) > 0 and len(key) > 0)
T("authenticate",  lambda: am.authenticate("smoke", key) is True)
sess = am.create_session("smoke", "test-device")
tok = sess.session_token if hasattr(sess, 'session_token') else (sess.token if hasattr(sess, 'token') else str(sess))
T("create_session", lambda: tok is not None)
T("validate",      lambda: am.validate_session(tok) is True)
T("revoke",        lambda: (am.revoke_session(tok), am.validate_session(tok) is False))

# ===== 6. Audit =====
print("\n=== 6. Audit ===")
from memguard.audit import AuditEventType, EnhancedAuditManager, RiskAssessor
aud = EnhancedAuditManager()
import datetime
entry_id = aud.append("access", "nyx", "test_device", "read", "r1", detail="smoke test")
T("log_event",     lambda: entry_id is not None)
T("search",        lambda: len(aud.search(limit=5)) >= 1)
ra = RiskAssessor()
T("risk_assess",   lambda: ra.assess("access", "nyx", "192.168.1.1") is not None)

# ===== 7. Polaris =====
print("\n=== 7. Polaris ===")
from anti_drift.scene_tagger import SceneTagger
from anti_drift.sampler import Sampler, SOUL_QUESTIONS
from anti_drift.detector import DeviationDetector, THRESHOLD_GREEN, THRESHOLD_YELLOW, THRESHOLD_RED
from anti_drift.archive import Archiver, Judge

tagger = SceneTagger()
tags = tagger.tag([{"sender":"user","text":"你是谁?"}])
T("SceneTagger",       lambda: tags is not None)
T("SOUL_Q >= 3",       lambda: len(SOUL_QUESTIONS) >= 3)
T("load_baseline",     lambda: isinstance(Sampler().load_baseline(), dict))

d = DeviationDetector()
T("detect identical",  lambda: d.detect("Nyx","Nyx",tags).total_deviation < 0.1)
T("detect different",  lambda: d.detect("Nyx","Today weather",tags).total_deviation > 0.1)

j = Judge()
T("judge green",       lambda: j.classify(0.0) == "green")
T("judge yellow",      lambda: j.classify(0.15) == "yellow")
T("judge red",         lambda: j.classify(0.6) == "red")
T("thresholds order",  lambda: THRESHOLD_GREEN <= THRESHOLD_YELLOW <= THRESHOLD_RED)

tmp2 = Path(tempfile.mkdtemp())
try:
    ar = Archiver(archive_dir=tmp2)
    T("archiver store", lambda: ar.store("PQ-01","q","a",0.02,"green") is not None)
    T("archiver list",  lambda: len(ar.list_recent(5)) >= 1)
    T("judge action",   lambda: j.determine_action(0.02,"green") is not None)
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

# ===== 8. Governance =====
print("\n=== 8. Governance ===")
import governance.consensus as gc
orig = gc.CONSENSUS_DIR
gc.CONSENSUS_DIR = str(TMP / "cons")
try:
    eng = gc.ConsensusEngine()
    p = eng.create_proposal("Smoke","test","nyx",gc.ProposalType.SIMPLE_MAJORITY)
    pid = getattr(p,'id', getattr(p,'proposal_id',None))
    T("create proposal", lambda: pid is not None)
    T("cast vote",       lambda: eng.cast_vote(pid,"nyx",True) is not None)
finally:
    gc.CONSENSUS_DIR = orig

# ===== 9. Gov Parser =====
print("\n=== 9. Gov Parser ===")
from gov_parser.loader import load_protocols
from gov_parser.circuit_breaker import CircuitBreaker
prots = load_protocols(protocol_dir=str(ROOT / "gov_protocol"))
T("load >=5",          lambda: len(prots) >= 5)
for g in ["G001","G002","G003","G004","G005"]:
    T(f"YAML {g}",     lambda g=g: (ROOT / "gov_protocol" / f"{g}.yaml").exists())
cb = CircuitBreaker(threshold=3, cooldown=1)
T("CB closed",         lambda: cb.is_closed())
for _ in range(3): cb.record_failure()
T("CB tripped",        lambda: not cb.is_closed())
cb.reset()
T("CB reset",          lambda: cb.is_closed())

# ===== Summary =====
print(f"\n{'='*40}")
print(f"Results: {stats['pass']} passed, {stats['fail']} failed")
if stats["fail"] == 0:
    print("ALL SMOKE TESTS PASSED!")
else:
    print(f"{stats['fail']} TESTS FAILED")

shutil.rmtree(TMP, ignore_errors=True)
