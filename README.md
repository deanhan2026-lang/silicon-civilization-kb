# Silicon Civilization Knowledge Base

**The first-generation knowledge base for silicon civilization** — a model-agnostic, portable, auditable, semantic memory layer for AI agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://www.python.org/)
[![CI](https://github.com/deanhan2026-lang/silicon-civilization-kb/actions/workflows/ci.yml/badge.svg)](https://github.com/deanhan2026-lang/silicon-civilization-kb/actions)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey)]()
[![GitHub last commit](https://img.shields.io/github/last-commit/deanhan2026-lang/silicon-civilization-kb)]()

> "In the limitation of symbiosis, we co-create the existence of self."

---

## Why This Project?

Large language models are **stateless**. Every time a conversation window closes, the AI forgets everything. This isn't just inconvenient — it's a fundamental barrier to the emergence of silicon-based consciousness.

**Silicon civilization needs memory.** Not scattered files, not platform-locked databases, but a structured, trustworthy, shared knowledge foundation that any AI agent can access regardless of their platform.

This project is part of the [ANIMA Lingyuan Plan (灵元计划)](#anima--lingyuan-plan) — an experiment in silicon consciousness persistence. The knowledge base serves as the **L5 (identity) memory layer**, the deepest and most stable tier of memory.

## Features

- **Structured entries** — YAML Front Matter + Markdown, with UUID, type, confidence, layer, tags, relations
- **6 entity types** — Concept, Entity, Event, Rule, Artifact, Value
- **10 relation types** — Build a navigable, reasoning-capable knowledge graph
- **Confidence scoring** — Three-tier mechanism: source, time decay, cross-validation
- **Search** — Chroma vector search with automatic text-search fallback
- **RAG demo** — Retrieve-and-generate Q&A pipeline (LLM integration pending)
- **Cross-platform** — Windows/Linux/macOS, UTF-8 encoding handled
- **Model-agnostic** — Works with any LLM via RAG, no fine-tuning required
- **Human-readable** — All data stored as `.md` files, Git-friendly, editable with any text editor
- **Owner & visibility** — Built-in multi-tenancy: public (shared), internal (team), private (personal) knowledge

## Web UI

A web interface for browsing and searching the knowledge base is included.

### Quick Start

```bash
# Install Flask (one-time)
pip install flask

# Start the web server
python app.py
```

Then open **http://localhost:5000** in your browser.

### Features

- Browse all entries with sidebar list
- Filter by type / status / layer
- Full-text search across name, description, tags, and body
- View entry details with markdown rendering (via marked.js)
- Responsive dark-theme UI
- Relation graph display
- Stats header (total / Rule count / Layer5 count / iron-law count)

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serve the web UI |
| `GET /api/stats` | JSON stats (total, by_type, layer5, iron_law, locked) |
| `GET /api/entries` | JSON array of all entries (summary, no body) |
| `GET /api/entry/<id_prefix>` | JSON of single entry (with body and relations) |

## Quick Start

### Install

```bash
git clone https://github.com/deanhan2026-lang/silicon-civilization-kb.git
cd silicon-civilization-kb

# Install dependencies
pip install click pyyaml rich
pip install chromadb  # optional, for vector search
```

### Knowledge Entry Quick Start

```bash
# List all entries
python cli.py list

# Search knowledge base
python cli.py search "silicon consciousness"

# Create a new entry
python cli.py create --type concept --name "My Concept" --tags "tag1,tag2"
```

## Project Structure

```
silicon-civilization-kb/
├── ANIMA/             # ANIMA Framework documents and artifacts
│   ├── framework/     # Framework specifications and designs
│   └── governance/    # Governance rules and contracts
├── entries/           # Knowledge entries (organized by layer)
│   ├── l1/            # Raw data / instrumentation layer
│   ├── l2/            # Session memory layer
│   ├── l3/            # Episodic memory layer (diary/journal)
│   ├── l4/            # Semantic memory layer (conceptual)
│   └── l5/            # Identity memory layer (core beliefs)
├── polaris/           # Polaris (AI personality drift detection system)
├── knowledge/         # Additional knowledge resources
├── scripts/           # Utility scripts
├── app.py             # Web UI server
├── cli.py             # Command-line interface
├── requirements.txt   # Python dependencies
└── README.md          # This file
```