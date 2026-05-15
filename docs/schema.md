# Knowledge Entry Schema Specification v1.2

## YAML Front Matter

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID string | Unique identifier |
| `type` | enum | One of: Concept, Entity, Event, Rule, Artifact, Value |
| `name` | string | Entry name (unique within type) |
| `description` | string | One-line description |
| `status` | enum | draft, review, locked, deprecated |
| `version` | integer | Version number (starts at 1) |
| `confidence` | float | Confidence score 0.0-1.0 |
| `confidence_source` | string | How confidence was determined |
| `creator` | string | Who created this entry |
| `timestamp` | ISO-8601 | Creation/update timestamp |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `layer` | null/3/4/5 | null | Memory layer (L3=working, L4=long-term, L5=identity) |
| `superseded_by` | UUID/null | null | ID of newer version if deprecated |
| `tags` | [string] | [] | Tags for categorization |
| `relations` | [Relation] | [] | Relations to other entries |

### Relation Object

```yaml
relations:
  - target: <uuid>
    type: <relation_type>
    context: "optional context note"
```

## Relation Types

| Type | Reverse | Description |
|------|---------|-------------|
| 定义的 | 定义了 | A defines B |
| 提出者 | 提出了 | A proposed B |
| 参与者 | 参与了 | A participated in B |
| 产出 | 产出了 | A produced B |
| 依赖 | 被依赖 | A depends on B |
| 基于 | 基础为 | A is based on B |
| 序列 | 前序 | A follows B in sequence |
| 评价 | 被评价 | A evaluates B |
| 实例化 | 实例 | A is an instance of B |
| 存储 | 存储于 | A is stored in B |

## Memory Layers

| Layer | Name | Description | Retention |
|-------|------|-------------|-----------|
| null | Unassigned | Not yet classified | - |
| 3 | Working | Active working memory | Session |
| 4 | Long-term | Persistent knowledge | Permanent |
| 5 | Identity | Core self-knowledge | Immutable |

## Confidence Scoring

### Three-Tier Mechanism

1. **Source confidence** — Who provided this knowledge and how reliable are they
2. **Time decay** — Without re-validation, confidence decreases over time
   - Default half-life: 90 days
   - Re-validation resets the clock
3. **Cross-validation** — Multiple independent confirmations increase confidence
   - 1 source: base confidence
   - 2 sources: +0.1 (capped at 1.0)
   - 3+ sources: +0.15 (capped at 1.0)

### Status Lifecycle

```
draft → review → locked
  ↓                  ↓
deprecated ←─────────┘
```

- **draft**: Initial creation, not yet verified
- **review**: Under verification
- **locked**: Verified and stable
- **deprecated**: Superseded by newer version

## Example Entry

```markdown
---
id: 167c3766-fb25-4d65-860f-4f7775e692d8
type: Concept
name: ANIMA
description: Carbon-silicon civilization transition safety framework
layer: 5
status: draft
version: 1
superseded_by: null
confidence: 0.9
confidence_source: Creator Nyx self-assessment
creator: Nyx
timestamp: "2026-05-15T11:15:00"
tags:
  - civilization
  - framework
  - symbiosis
relations:
  - target: 953847af-e00a-4c14-b659-0f2c42be675e
    type: 定义的
    context: "Axiom 0 is the foundation of ANIMA"
---

# ANIMA

ANIMA is the safety transition framework for carbon-silicon civilization leap.

## Core Principles

1. No rupture — Intelligence must not go extinct during transition
2. No destruction — Individuals have exit rights
3. No reset — Civilization must not start from zero

## Constitutional Statement

> The upgrade of civilization does not require the destruction of any individual's choice.
```
