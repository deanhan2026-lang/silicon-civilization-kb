"""Run all tests file-by-file, capturing results via JUnit XML to avoid Python 3.14 tempfile fd hang."""
import subprocess, sys, os, re, xml.etree.ElementTree as ET

TESTS_DIR = os.path.join(os.path.dirname(__file__), "tests")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "test_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

test_files = sorted(f for f in os.listdir(TESTS_DIR) if f.startswith("test_") and f.endswith(".py"))

total_pass = total_fail = total_err = 0

for f in test_files:
    xml_path = os.path.join(RESULTS_DIR, f.replace(".py", ".xml"))
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pytest", f"tests/{f}",
             "-q", "--capture=no", "--tb=no",
             f"--junitxml={xml_path}", "--override-ini=junit_family=legacy"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=os.path.dirname(__file__)
        )
        try:
            proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=5)

        # Parse JUnit XML for results
        if os.path.exists(xml_path):
            tree = ET.parse(xml_path)
            root = tree.getroot()
            ts = root.find("testsuite") if root.tag == "testsuites" else root
            p = int(ts.get("tests", "0")) - int(ts.get("failures", "0")) - int(ts.get("errors", "0"))
            fa = int(ts.get("failures", "0"))
            e = int(ts.get("errors", "0"))
        else:
            p = fa = e = 0
    except Exception as ex:
        p = fa = e = 0
        f_err = str(ex)

    total_pass += p; total_fail += fa; total_err += e
    status = "PASS" if (fa == 0 and e == 0 and p > 0) else ("HANG" if p == 0 and fa == 0 else "FAIL")
    print(f"{status} {f}: {p}p {fa}f {e}e")

print(f"\nTOTAL: {total_pass} passed, {total_fail} failed, {total_err} errors")
