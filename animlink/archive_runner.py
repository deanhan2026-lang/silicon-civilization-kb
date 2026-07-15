# -*- coding: utf-8 -*-
"""
Archive runner — copies token files from inbox/* to archive/
Uses os.path only (avoids Path.exists() metadata hangs on NAS).
"""

import os
import shutil
import time

NAS_ROOT = r"Z:\qclaw"

def sync_token_files():
    inbox_dirs = [
        r"inbox\to-windows",
        r"inbox\to-iris",
        r"inbox\to-heng",
    ]
    archive = os.path.join(NAS_ROOT, "inbox", "archive")
    os.makedirs(archive, exist_ok=True)

    copied = 0
    for rel_dir in inbox_dirs:
        src_dir = os.path.join(NAS_ROOT, rel_dir)
        if not os.path.isdir(src_dir):
            continue
        try:
            names = os.listdir(src_dir)
        except Exception:
            continue
        for name in names:
            if not (name.startswith("tk_") or name.startswith("accept_") or name.startswith("delivery_")):
                continue
            src_path = os.path.join(src_dir, name)
            if not os.path.isfile(src_path):
                continue
            dst_path = os.path.join(archive, name)
            if os.path.isfile(dst_path):
                continue
            try:
                shutil.copy2(src_path, dst_path)
                copied += 1
            except Exception:
                pass
    return copied

if __name__ == "__main__":
    start = time.time()
    n = sync_token_files()
    print(f"[archive_runner] Copied {n} files to archive in {time.time()-start:.1f}s")
