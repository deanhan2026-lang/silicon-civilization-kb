# -*- coding: utf-8 -*-
"""
conftest.py — 确保 argus 包与模块在 pytest 下均可导入
"""
import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_argus = os.path.join(_root, "argus")

for _p in (_root, _argus):
    if _p not in sys.path:
        sys.path.insert(0, _p)
