import sys
sys.path.insert(0, '.')
from kb import KB_DIR, ENTITY_TYPES, parse_yaml_front_matter, get_chroma_client

# Test retrieve logic directly
query = "ANIMA是什么"
query_lower = query.lower()
print(f'Query: {query}')
print(f'Query lower: {query_lower}')
print(f'KB_DIR: {KB_DIR}')
print(f'ENTITY_TYPES: {ENTITY_TYPES}')

client = get_chroma_client()
print(f'Chroma client: {client}')

results = []
for entry_t in ENTITY_TYPES:
    type_dir = KB_DIR / entry_t.lower()
    print(f'Checking {type_dir}... exists={type_dir.exists()}')
    if not type_dir.exists():
        continue
    for f in type_dir.glob('*.md'):
        meta, body = parse_yaml_front_matter(f.read_text(encoding='utf-8'))
        if not meta.get('id'):
            print(f'  SKIP no id: {f.name}')
            continue
        text = (meta.get('name','') + ' ' + meta.get('description','') + ' ' + body).lower()
        if query_lower in text:
            count = text.count(query_lower)
            print(f'  MATCH: {meta.get("name")} score={count}')
            results.append({'meta': meta, 'body': body, 'score': count})

print(f'\nTotal results: {len(results)}')
results.sort(key=lambda x: x['score'], reverse=True)
for r in results[:3]:
    print(f'  Top: {r["meta"].get("name")} score={r["score"]}')