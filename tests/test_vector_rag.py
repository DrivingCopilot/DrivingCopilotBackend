# tests/test_vector_rag.py
#
# Vector RAG (리랭커 포함) 단위 테스트.
# pytest tests/test_vector_rag.py 로 실행 (Qdrant/실제 CrossEncoder 불필요).

from types import SimpleNamespace

import pytest

from app import config
from app.services import vector_rag


@pytest.fixture(autouse=True)
def _reset_reranker_singleton():
    vector_rag._reranker = None
    yield
    vector_rag._reranker = None


def _doc(text):
    return SimpleNamespace(page_content=text)


# ── _format_docs: 순수 포맷팅 로직 ───────────────────────────────────────────

class TestFormatDocs:
    """chunk 리스트를 MCP 툴 반환 문자열로 포맷팅하는 로직 검증. 모킹 불필요."""

    def test_empty_list_returns_not_found_message(self):
        assert vector_rag._format_docs([]) == "관련 매뉴얼 내용을 찾지 못했습니다."

    def test_single_doc_formatting(self):
        result = vector_rag._format_docs([_doc("엔진 오일 교체 주기는 1만km")])
        assert result == "[1] 엔진 오일 교체 주기는 1만km"

    @pytest.mark.parametrize("n", [2, 3, 5])
    def test_multi_doc_numbered_formatting(self, n):
        docs = [_doc(f"chunk-{i}") for i in range(n)]
        result = vector_rag._format_docs(docs)
        lines = result.split("\n\n")
        assert len(lines) == n
        for i, line in enumerate(lines, 1):
            assert line == f"[{i}] chunk-{i - 1}"


# ── _rerank: 빈 리스트 단락 처리 ─────────────────────────────────────────────

class TestRerankEmptyDocs:
    """빈 리스트가 들어오면 리랭커를 아예 건드리지 않고 그대로 반환한다."""

    def test_rerank_empty_docs_short_circuits(self, monkeypatch):
        called = {"n": 0}

        def fake_get_reranker():
            called["n"] += 1
            return object()  # predict()가 없으므로 호출되면 바로 에러가 난다

        monkeypatch.setattr(vector_rag, "_get_reranker", fake_get_reranker)

        result = vector_rag._rerank("query", [])

        assert result == []
        assert called["n"] == 0


# ── _rerank: 리랭커 사용 가능 시 재정렬 ──────────────────────────────────────

class TestRerankWithReranker:
    """리랭커가 정상 로드된 경우 점수 내림차순으로 재정렬되는지 확인."""

    def test_rerank_sorts_descending_by_score(self, monkeypatch):
        docs = [_doc("low"), _doc("high"), _doc("mid")]
        scores = [0.1, 0.9, 0.5]

        class FakeReranker:
            def predict(self, pairs):
                return scores

        monkeypatch.setattr(vector_rag, "_get_reranker", lambda: FakeReranker())

        result = vector_rag._rerank("query", docs)

        assert [doc.page_content for doc, _ in result] == ["high", "mid", "low"]

    def test_rerank_pairs_pass_query_and_page_content(self, monkeypatch):
        docs = [_doc("low"), _doc("high"), _doc("mid")]
        captured = {}

        class FakeReranker:
            def predict(self, pairs):
                captured["pairs"] = pairs
                return [0.0] * len(pairs)

        monkeypatch.setattr(vector_rag, "_get_reranker", lambda: FakeReranker())

        vector_rag._rerank("query", docs)

        assert captured["pairs"] == [
            ("query", "low"),
            ("query", "high"),
            ("query", "mid"),
        ]


# ── _rerank: 리랭커 로드 실패 시 graceful degradation ────────────────────────

class TestRerankGracefulDegradation:
    """리랭커 로드 실패(_get_reranker → None) 시 원본 순서를 그대로 유지한다."""

    def test_rerank_falls_back_when_reranker_unavailable(self, monkeypatch):
        docs = [_doc("a"), _doc("b"), _doc("c")]
        monkeypatch.setattr(vector_rag, "_get_reranker", lambda: None)

        result = vector_rag._rerank("query", docs)

        assert result == [(doc, None) for doc in docs]


# ── vector_search: 전체 조립 (CANDIDATE_K → rerank → 최종 K 슬라이싱) ────────

class TestVectorSearchAssembly:
    """vector_search()가 후보 검색 → 재정렬 → 최종 K 슬라이싱을 올바른 순서로 조립하는지 확인."""

    @pytest.mark.asyncio
    async def test_slices_to_final_k_after_rerank(self, monkeypatch):
        candidates = [_doc(f"c{i}") for i in range(config.VECTOR_SEARCH_CANDIDATE_K)]
        # score[i] = i → 인덱스가 클수록 점수가 높아 rerank 후 순서가 완전히 반전됨
        scores = list(range(len(candidates)))

        class FakeReranker:
            def predict(self, pairs):
                return scores

        monkeypatch.setattr(vector_rag, "_run_vector_search", lambda query: candidates)
        monkeypatch.setattr(vector_rag, "_get_reranker", lambda: FakeReranker())

        result = await vector_rag.vector_search("query")

        expected = list(reversed(candidates))[: config.VECTOR_SEARCH_K]
        assert result == vector_rag._format_docs(expected)

    @pytest.mark.asyncio
    async def test_no_candidates_returns_not_found_message(self, monkeypatch):
        monkeypatch.setattr(vector_rag, "_run_vector_search", lambda query: [])

        result = await vector_rag.vector_search("query")

        assert result == "관련 매뉴얼 내용을 찾지 못했습니다."

    @pytest.mark.asyncio
    async def test_run_vector_search_exception_returns_error_string(self, monkeypatch):
        def boom(query):
            raise RuntimeError("qdrant down")

        monkeypatch.setattr(vector_rag, "_run_vector_search", boom)

        result = await vector_rag.vector_search("query")

        assert result.startswith("vector_rag_search 처리 중 오류")
        assert "qdrant down" in result
