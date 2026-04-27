"""
Phase 2 单元测试：RRF（Reciprocal Rank Fusion）融合算法

学习目标：
- 理解 RRF 公式：score = Σ 1 / (k + rank_i)
- 理解为什么两路都出现的文档得分最高
- 理解 k 参数对分数分布的影响

RRF 公式核心：
  k = 60（论文推荐值）
  rank 从 0 开始
  排第 1（rank=0）：1/(60+0+1) = 0.01639
  排第 2（rank=1）：1/(60+1+1) = 0.01613
  两路都排第 1：0.01639 * 2 = 0.03278
"""
import pytest
from langchain_core.documents import Document
from services.pure_retrieval_utils import rrf_fusion


def make_doc(content: str) -> Document:
    """辅助函数：创建文档"""
    return Document(page_content=content)


class TestRRFFusion:
    """rrf_fusion() 测试套件"""

    def test_single_path_vector_only(self):
        """只有向量路有结果"""
        docs = [
            (make_doc("文档A"), 0.5),
            (make_doc("文档B"), 0.8),
        ]
        result = rrf_fusion(docs, [])
        assert len(result) == 2
        # A 排第 1: 1/(60+0+1) = 0.01639
        assert result[0][0].page_content == "文档A"
        assert abs(result[0][1] - 1 / 61) < 1e-6, "排第1的RRF分数应为 1/61"

    def test_single_path_keyword_only(self):
        """只有关键词路有结果"""
        docs = [
            (make_doc("文档C"), 0.9),
            (make_doc("文档D"), 0.3),
        ]
        result = rrf_fusion([], docs)
        assert len(result) == 2
        assert result[0][0].page_content == "文档C"

    def test_both_paths_same_doc(self, scored_documents_for_rrf):
        """核心测试：在两路中都出现的文档得分最高"""
        vector_results = scored_documents_for_rrf["vector_results"]
        keyword_results = scored_documents_for_rrf["keyword_results"]

        result = rrf_fusion(vector_results, keyword_results)

        # 文档 A 在两路都出现 → RRF 分数 = 1/61 + 1/63 ≈ 0.0325
        # 文档 C 只在关键词路排第1 → RRF 分数 = 1/61 ≈ 0.0164
        # 文档 B 只在向量路排第2 → RRF 分数 = 1/62 ≈ 0.0161

        doc_names = [d.page_content for d, _ in result]
        scores = [s for _, s in result]

        # A 应该在最前面（两路都命中）
        assert result[0][0].page_content == "文档 A 的内容：Windows 7 安装教程的详细步骤说明。", \
            "两路都出现的文档应排在第一位"
        assert scores[0] > scores[1], "两路命中的分数应高于单路命中"

    def test_rank_order_matters(self):
        """排名越靠前，RRF 分数越高"""
        # A 在向量路排第1（rank=0），B 在向量路排第5（rank=4）
        vector = [
            (make_doc("A排第1"), 0.1),
            (make_doc("B排第2"), 0.2),
            (make_doc("C排第3"), 0.3),
            (make_doc("D排第4"), 0.4),
            (make_doc("E排第5"), 0.5),
        ]
        result = rrf_fusion(vector, [])

        # A 应该分数最高
        assert result[0][0].page_content == "A排第1"
        # 分数递减
        for i in range(len(result) - 1):
            assert result[i][1] > result[i + 1][1], \
                f"排名 {i} 的分数应大于排名 {i+1}"

    def test_k_parameter_effect(self):
        """k 越小，排名差异越被放大"""
        docs = [
            (make_doc("排第1"), 0.1),
            (make_doc("排第2"), 0.2),
        ]

        # k=1：差异大
        result_k1 = rrf_fusion(docs, [], k=1)
        diff_k1 = result_k1[0][1] - result_k1[1][1]

        # k=60：差异小
        result_k60 = rrf_fusion(docs, [], k=60)
        diff_k60 = result_k60[0][1] - result_k60[1][1]

        assert diff_k1 > diff_k60, \
            "k 越小，排名靠前的优势越大"

    def test_empty_inputs(self):
        """两路都为空时返回空列表"""
        result = rrf_fusion([], [])
        assert result == []

    def test_score_formula_verification(self):
        """验证 RRF 公式的数值正确性"""
        doc = (make_doc("测试文档"), 0.5)
        result = rrf_fusion([doc], [], k=60)

        expected = 1 / (60 + 0 + 1)  # rank=0, k=60
        assert abs(result[0][1] - expected) < 1e-6, \
            f"RRF 分数应为 {expected}，实际为 {result[0][1]}"

    def test_two_paths_both_appear_score(self):
        """精确验证两路都出现的文档分数"""
        doc_a = make_doc("A")
        doc_b = make_doc("B")

        # A 在两路都排第1
        result = rrf_fusion([(doc_a, 0.1)], [(doc_a, 0.2)], k=60)

        # A 在两路都排第1 → 1/61 + 1/61 = 2/61
        expected = 2 / 61
        assert abs(result[0][1] - expected) < 1e-6, \
            f"两路都排第1的文档分数应为 {expected:.6f}，实际为 {result[0][1]:.6f}"
