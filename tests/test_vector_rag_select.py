# tests/test_vector_rag_select.py
#
# _select_docs() 단위 테스트 — 리랭킹 이후 threshold 필터 + VECTOR_SEARCH_K 상한 로직만 검증.
# pytest tests/test_vector_rag_select.py -v 로 실행 (Qdrant/실제 CrossEncoder 불필요).

from types import SimpleNamespace

from app import config
from app.services import vector_rag


def _doc(text):
    return SimpleNamespace(page_content=text)


class TestSelectDocs:
    """_select_docs()의 threshold 필터링 + VECTOR_SEARCH_K 상한 로직 검증."""

    def test_empty_ranked_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 5)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", -2.0)

        assert vector_rag._select_docs([]) == []

    def test_no_scores_skips_threshold_and_takes_top_k_in_original_order(self, monkeypatch):
        """score=None(리랭커 미사용)이면 threshold 필터 없이 원본 순서로 K개만 자른다."""
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 2)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", 100.0)  # 필터링 안 됨을 확인하기 위해 극단값

        ranked = [(_doc("a"), None), (_doc("b"), None), (_doc("c"), None)]

        result = vector_rag._select_docs(ranked)

        assert [d.page_content for d in result] == ["a", "b"]

    def test_all_scores_above_threshold_returns_all_within_k(self, monkeypatch):
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 5)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", -2.0)

        ranked = [(_doc("a"), 0.9), (_doc("b"), 0.5), (_doc("c"), 0.1)]

        result = vector_rag._select_docs(ranked)

        assert [d.page_content for d in result] == ["a", "b", "c"]

    def test_scores_below_threshold_are_filtered_out(self, monkeypatch):
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 5)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", 0.0)

        ranked = [(_doc("high"), 0.9), (_doc("low"), -0.5), (_doc("mid"), 0.1)]

        result = vector_rag._select_docs(ranked)

        assert [d.page_content for d in result] == ["high", "mid"]

    def test_all_below_threshold_falls_back_to_top_scoring_doc(self, monkeypatch):
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 5)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", 10.0)  # 아무도 통과 못 하도록

        ranked = [(_doc("best"), 0.9), (_doc("second"), 0.5), (_doc("worst"), 0.1)]

        result = vector_rag._select_docs(ranked)

        assert [d.page_content for d in result] == ["best"]

    def test_passing_count_above_k_is_truncated_to_k(self, monkeypatch):
        monkeypatch.setattr(config, "VECTOR_SEARCH_K", 2)
        monkeypatch.setattr(config, "RERANK_SCORE_THRESHOLD", -2.0)

        ranked = [(_doc("a"), 0.9), (_doc("b"), 0.7), (_doc("c"), 0.5), (_doc("d"), 0.3)]

        result = vector_rag._select_docs(ranked)

        assert [d.page_content for d in result] == ["a", "b"]
