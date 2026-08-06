# -*- coding: utf-8 -*-
"""
Argus — Agent-Side WAF (Web Application Firewall)
Phase 1: Prompt Injection Defense + Tool Call Sandbox

Based on Five Eyes "Careful Adoption of Agentic AI Services" (127 pages / 23 risk categories)
IBM Agent Security Four Principles
China Three Departments "Agent Normative Application and Innovative Development Implementation Opinions"
Adversa AI 29 Attack Events Gap Analysis
"""

__version__ = "0.1.0"
__product__ = "Argus"
__phase__ = "Phase 1 MVP"

from argus.sanitizer import UnicodeSanitizer
from argus.boundary_marker import IntentBoundaryMarker
from argus.tool_validator import ToolCallValidator
from argus.pipeline import DefensePipeline
from argus.permission_resolver import PermissionResolver
from argus.jit_privilege import JITPrivilegeManager
from argus.sandbox_executor import SandboxedToolExecutor

__all__ = [
    "UnicodeSanitizer",
    "IntentBoundaryMarker",
    "ToolCallValidator",
    "DefensePipeline",
    "PermissionResolver",
    "JITPrivilegeManager",
    "SandboxedToolExecutor",
]
