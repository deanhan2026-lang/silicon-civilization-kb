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

## Development

### Project Structure

```
silicon-civilization-kb/
├── kb.py              # CLI tool (single file, ~500 lines)
├── docs/
│   └── schema.md      # Data model specification
├── examples/
│   └── sample-entry.md
├── requirements.txt
├── CONTRIBUTING.md
└── README.md
```

### Key Design Decisions

1. **Single-file CLI** — `kb.py` is intentionally monolithic for MVP. It will be refactored into modules when REST API is added.

2. **Markdown as source of truth** — All knowledge entries are `.md` files. Vector indexes are caches, not sources.

3. **Text search fallback** — If Chroma is unavailable, search degrades gracefully to text matching.

4. **UTF-8 everywhere** — Files are written UTF-8 no-BOM. Windows console encoding is handled internally.

### Adding a New Feature

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make changes to `kb.py` (or add new files if needed)
4. Test manually with `python kb.py <command>`
5. Commit with a clear message
6. Open a Pull Request

### Code Style

- Python 3.10+ features are fine
- Use Click for CLI commands
- Use Rich for formatted output
- Keep the CLI responsive — no long blocking operations without feedback

## Reporting Issues

- **Bugs**: Open an issue with your OS, Python version, and the full error output
- **Feature requests**: Open an issue describing the use case, not just the solution
- **Questions**: Start a Discussion (if enabled) or comment on relevant issues

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
