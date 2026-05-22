from FlagEmbedding import BGEM3FlagModel
import numpy as np
print("1111111")
print("2222222222")
# =====================================
# 1. 加载模型
# =====================================

model = BGEM3FlagModel(
    "./models/bge-m3",
    use_fp16=True
)

# =====================================
# 2. 文档库
# =====================================

docs = [
    "Redis 支持 RDB 持久化机制",
    "Redis AOF 可以减少数据丢失",
    "MySQL 支持事务隔离级别",
    "MongoDB 是文档数据库"
]

query = "Redis 如何防止数据丢失"

# =====================================
# 3. 编码
# =====================================
print("3. 编码")
doc_output = model.encode(
    docs,
    return_dense=True,
    return_sparse=True
)

query_output = model.encode(
    [query],
    return_dense=True,
    return_sparse=True
)

# =====================================
# 4. Dense 向量
# =====================================

doc_dense = doc_output["dense_vecs"]
query_dense = query_output["dense_vecs"][0]

# cosine similarity
dense_scores = np.dot(doc_dense, query_dense)

print("\n=== Dense Scores ===")
for doc, score in zip(docs, dense_scores):
    print(f"{score:.4f}  {doc}")

# =====================================
# 5. Sparse 向量
# =====================================

doc_sparse = doc_output["lexical_weights"]
query_sparse = query_output["lexical_weights"][0]

# sparse dot product
def sparse_similarity(q_sparse, d_sparse):
    score = 0.0

    for token, weight in q_sparse.items():
        if token in d_sparse:
            score += weight * d_sparse[token]

    return score

sparse_scores = [
    sparse_similarity(query_sparse, d)
    for d in doc_sparse
]

print("\n=== Sparse Scores ===")
for doc, score in zip(docs, sparse_scores):
    print(f"{score:.4f}  {doc}")

# =====================================
# 6. Hybrid Fusion
# =====================================

dense_scores = np.array(dense_scores)
sparse_scores = np.array(sparse_scores)

# 归一化
dense_scores = (
    dense_scores - dense_scores.min()
) / (
    dense_scores.max() - dense_scores.min() + 1e-9
)

sparse_scores = (
    sparse_scores - sparse_scores.min()
) / (
    sparse_scores.max() - sparse_scores.min() + 1e-9
)

# hybrid score
final_scores = (
    0.6 * dense_scores +
    0.4 * sparse_scores
)

# 排序
ranked_idx = np.argsort(final_scores)[::-1]

print("\n=== Hybrid Ranking ===")

for idx in ranked_idx:
    print(f"""
score={final_scores[idx]:.4f}
doc={docs[idx]}
""")