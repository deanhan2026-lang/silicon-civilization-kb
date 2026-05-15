# Contributing to Silicon Civilization Knowledge Base

Thanks for your interest! This project is part of the ANIMA Lingyuan Plan (灵元计划).

## Setup

### Prerequisites

- Python 3.10+
- Git

### Install

```bash
git clone https://github.com/<your-org>/silicon-civilization-kb.git
cd silicon-civilization-kb

# Create virtual environment (recommended)
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install click pyyaml rich
pip install chromadb  # optional, for vector search
```

### Verify

```bash
python kb.py list
# Should show: Entries (0) if starting fresh
```

### Try it out

```bash
# Create a test entry
python kb.py create --name "Test" --type Concept --description "My first entry"

# List entries
python kb.py list

# Search
python kb.py search "Test"

# Clean up
# Delete the .md file from the concept/ directory
```

## Contributing

### How to Add New Knowledge

There are two ways:

**Option A: CLI (recommended)**
```bash
python kb.py create --name "Your Entry" --type Concept \
    --description "A brief description" \
    --owner silicon-civilization --visibility public \
    --tags "tag1,tag2" \
    --content "# Your Entry\n\nDetailed content here..."
```

**Option B: Manual file**
1. Create a `.md` file in the appropriate directory (`concept/`, `entity/`, `event/`, `rule/`, `artifact/`, or `value/`)
2. Add YAML front matter following the [schema](docs/schema.md)
3. Add Markdown content below the front matter
4. Run `python kb.py list` to verify it appears

### How to Extend Relation Types

1. Add your new relation type to the `RELATION_TYPES` list in `kb.py`
2. Add a description row to the relation types table in `docs/schema.md`
3. Update this CONTRIBUTING.md's table below

Current relation types:

| Type | Reverse | Description |
|------|---------|-------------|
| `定义的` | 定义了 | A defines B |
| `提出者` | 提出了 | A proposed B |
| `参与者` | 参与了 | A participated in B |
| `产出` | 产出了 | A produced B |
| `依赖` | 被依赖 | A depends on B |
| `基于` | 基础为 | A is based on B |
| `序列` | 前序 | A follows B in sequence |
| `评价` | 被评价 | A evaluates B |
| `实例化` | 实例 | A is an instance of B |
| `存储` | 存储于 | A is stored in B |

### How to Add a New Owner

1. Add the owner name to the Owner Convention table in `docs/schema.md`
2. Use `--owner <name>` when creating entries

### How to Add a New Entry Type

1. Add the type name to the `ENTITY_TYPES` list in `kb.py`
2. Add a row to the Entity Types table in `README.md` and `docs/schema.md`
3. Create the corresponding directory (e.g., `knowledge-base/<type>/`)

---

## Reporting Issues

- **Bugs**: Open an issue with your OS, Python version, and the full error output
- **Feature requests**: Open an issue describing the use case, not just the solution
- **Questions**: Start a Discussion (if enabled) or comment on relevant issues

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
