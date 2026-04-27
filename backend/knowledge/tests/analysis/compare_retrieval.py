"""
端到端验证脚本：用真实查询测试完整检索管线

用法：
  cd backend/knowledge
  python tests/analysis/compare_retrieval.py

学习目标：
- 观察真实查询下各阶段的返回结果
- 对比不同查询类型的召回差异
- 理解 Re-ranker 分数和动态阈值的行为

注意：需要 SiliconFlow API 可用（embedding + re-ranker），会产生 API 调用。
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from services.retrieval_service import RetrievalService
from services.reranker_service import RerankerService
from config.settings import settings


def print_separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_doc(doc, index, max_content_len=80):
    score = doc.metadata.get("rerank_score", "N/A")
    content = doc.page_content[:max_content_len]
    print(f"  [{index}] 分数={score} | {content}...")


def test_query(query_text, service, label):
    """测试单个查询并打印结果"""
    print_separator(f"查询: {query_text} [{label}]")

    # 调用检索
    print(f"\n  正在检索...")
    try:
        results = service.retrieval(query_text)
    except Exception as e:
        print(f"  ❌ 检索失败: {e}")
        return

    print(f"\n  返回 {len(results)} 篇文档:")
    for i, doc in enumerate(results):
        print_doc(doc, i + 1)

    # 分析分数分布
    scores = [doc.metadata.get("rerank_score", 0) for doc in results]
    if scores and all(isinstance(s, (int, float)) for s in scores):
        print(f"\n  分数统计: 最高={max(scores):.3f}, 最低={min(scores):.3f}")
        above_threshold = sum(1 for s in scores if s >= settings.RERANK_THRESHOLD)
        print(f"  高于阈值({settings.RERANK_THRESHOLD}): {above_threshold}/{len(scores)} 篇")
    else:
        print(f"\n  分数统计: 无法计算（部分文档无 rerank_score）")


def main():
    print("""
知识库检索优化 — 端到端验证
===========================
本脚本将使用真实查询测试完整的检索管线（向量+关键词召回 → RRF → 去重 → Re-ranker → 动态阈值）。
需要 SiliconFlow API 可用。
""")

    # 初始化服务
    print("初始化检索服务...")
    try:
        service = RetrievalService()
        print("✅ 服务初始化成功")
    except Exception as e:
        print(f"❌ 服务初始化失败: {e}")
        print("请检查 .env 配置和网络连接")
        return

    # 定义测试查询
    test_queries = [
        # 语义查询：向量检索应表现好
        ("如何鉴定花岗岩和闪长岩", "语义查询"),

        # 编号查询：关键词检索应命中
        ("TS001 错误代码", "编号查询"),

        # 版本/型号查询：两路都应命中
        ("如何安装 Windows 7", "型号查询"),

        # 常见问题：两路都可能命中
        ("电脑开机无反应怎么办", "常见问题"),

        # 知识库外查询：应被动态阈值截断
        ("2026年诺贝尔物理学奖", "库外查询"),
    ]

    for query, label in test_queries:
        test_query(query, service, label)

    # 总结
    print_separator("测试完成 — 总结")
    print(f"""
观察要点：
1. Phase 2（RRF）：编号类查询是否命中了关键词路的文档？
2. Phase 3（Re-ranker）：高相关文档是否排在前面？
3. Phase 4（动态阈值）：库外查询是否只返回了少量文档？

配置信息：
  向量模型: {settings.EMBEDDING_MODEL}
  Re-ranker: {settings.RERANKER_MODEL}
  TOP_RECALL: {settings.TOP_RECALL}
  TOP_RERANK: {settings.TOP_RERANK}
  RERANK_THRESHOLD: {settings.RERANK_THRESHOLD}
  MIN/MAX_RETURN: {settings.MIN_RETURN}/{settings.MAX_RETURN}
""")


if __name__ == "__main__":
    main()
