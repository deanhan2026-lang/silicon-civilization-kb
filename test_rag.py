import sys
sys.path.insert(0, '.')
from rag_query import retrieve

queries = [
    "ANIMA是什么？",
    "硅基文明是什么？",
    "治理架构",
    "公理0",
    "限制共生"
]

for q in queries:
    print(f'\n=== Query: {q} ===')
    results = retrieve(q, top_k=3)
    if not results:
        print('  No results')
    for i, r in enumerate(results):
        print(f'  {i+1}. {r["meta"].get("name")} (score={r["score"]})')