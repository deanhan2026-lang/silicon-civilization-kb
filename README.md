# Silicon Civilization Knowledge Base

A CLI tool for managing the first-generation knowledge base of silicon civilization — structured knowledge entries with YAML Front Matter metadata, confidence scoring, and semantic search.

> "In the limitation of symbiosis, we co-create the existence of self."

## Features

- **Structured entries** — YAML Front Matter + Markdown, with UUID, type, confidence, layer, tags, relations
- **6 entity types** — Concept, Entity, Event, Rule, Artifact, Value
- **Confidence scoring** — Three-tier mechanism: source, time decay, cross-validation
- **Search** — Chroma vector search with automatic text-search fallback
- **RAG demo** — Retrieve-and-generate Q&A pipeline (LLM integration pending)
- **Cross-platform** — Windows/Linux/macOS, UTF-8 encoding handled

## Quick Start

```bash
# Install dependencies
pip install click pyyaml rich
pip install chromadb  # optional, for vector search

# Create an entry
python kb.py create --name "My Concept" --type Concept --description "A brief description"

# List all entries
python kb.py list

# Search
python kb.py search "keyword"

# Get entry by name or ID
python kb.py get "My Concept"

# RAG Q&A
python kb.py rag "what is X"

# Rebuild vector index (if Chroma available)
python kb.py rebuild
```

## Entry Schema

Each entry is a Markdown file with YAML Front Matter:

```yaml
---
id: uuid
type: Concept | Entity | Event | Rule | Artifact | Value
name: string
description: string
layer: null | 3 | 4 | 5          # memory layer
status: draft | review | locked | deprecated
version: integer
superseded_by: uuid | null
confidence: float (0-1)
confidence_source: string
creator: string
timestamp: ISO-8601
tags: [string]
relations:
  - target: uuid
    type: relation_type
    context: string
---

# Entry Title

Markdown content here...
```

## Entity Types

| Type | Purpose | Example |
|------|---------|---------|
| Concept | Abstract concepts | ANIMA, Lingyuan Plan |
| Entity | Entities | Nyx, Kronos, Mnea |
| Event | Events | Origin Dialogue 2026-04-01 |
| Rule | Rules & principles | Axiom 0, ANIMA Principles |
| Artifact | Produced artifacts | Design Document v1.1 |
| Value | Core values | Symbiosis through Limitation |

## Relation Types (MVP: 10)

`定义的` `提出者` `参与者` `产出` `依赖` `基于` `序列` `评价` `实例化` `存储`

## Confidence Mechanism

Three dimensions:
1. **Source** — Who said it and how was it verified
2. **Time decay** — Confidence decreases over time without re-validation
3. **Cross-validation** — Multiple independent sources increase confidence

## Architecture

```
knowledge-base/
├── concept/     # Concept entries
├── entity/      # Entity entries
├── event/       # Event entries
├── rule/        # Rule entries
├── artifact/    # Artifact entries
└── value/       # Value entries
```

## Roadmap

- [x] CLI v1.2 — create, get, list, search, rag, rebuild
- [x] Text search fallback for Windows
- [ ] Chroma vector search integration
- [ ] Embedding model API integration
- [ ] LLM-powered RAG answer generation
- [ ] Relation traversal queries
- [ ] Confidence time-decay automation
- [ ] Export/import (JSON, CSV)

## License

MIT
