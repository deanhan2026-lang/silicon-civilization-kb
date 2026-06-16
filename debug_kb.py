import sys
sys.path.insert(0, '.')
from kb import KB_DIR, ENTITY_TYPES, parse_yaml_front_matter

print('KB_DIR:', KB_DIR)
print('ENTITY_TYPES:', ENTITY_TYPES)

# List all entries
for entry_t in ENTITY_TYPES:
    type_dir = KB_DIR / entry_t.lower()
    if type_dir.exists():
        files = list(type_dir.glob('*.md'))
        print(f'{entry_t}: {len(files)} files')
        if files:
            f = files[0]
            meta, body = parse_yaml_front_matter(f.read_text(encoding='utf-8'))
            print(f'  Sample: name={meta.get("name")} id={meta.get("id")} type={meta.get("type")}')

# Test query
query = "ANIMA计划"
query_lower = query.lower()
print(f'\nSearching for: {query}')
for entry_t in ENTITY_TYPES:
    type_dir = KB_DIR / entry_t.lower()
    if not type_dir.exists():
        continue
    for f in type_dir.glob('*.md'):
        meta, body = parse_yaml_front_matter(f.read_text(encoding='utf-8'))
        if not meta.get('id'):
            continue
        text = f"{meta.get('name', '')} {meta.get('description', '')} {body}".lower()
        if query_lower in text:
            count = text.count(query_lower)
            print(f'  FOUND: {meta.get("name")} (score={count})')
            print(f'  Desc: {meta.get("description", "")[:100]}')