"""Unit tests for optional RAG retrieval (`search_similar`)."""

from unittest.mock import MagicMock, patch

import pytest

from knowledge.vector_store import search_similar


@pytest.mark.parametrize(
    "query",
    ["", "   ", "\t\n"],
)
def test_empty_or_blank_query_returns_empty(query: str) -> None:
    assert search_similar(query) == []


@patch("knowledge.vector_store.get_collection")
def test_get_collection_none_returns_empty(mock_get_collection: MagicMock) -> None:
    mock_get_collection.return_value = None
    assert search_similar("pod crash") == []


@patch("knowledge.vector_store.get_collection")
def test_get_collection_exception_returns_empty(mock_get_collection: MagicMock) -> None:
    mock_get_collection.side_effect = OSError("cannot create chroma dir")
    assert search_similar("pod crash") == []


@patch("knowledge.vector_store.get_collection")
def test_query_exception_returns_empty(mock_get_collection: MagicMock) -> None:
    collection = MagicMock()
    collection.query.side_effect = RuntimeError("embedding failure")
    mock_get_collection.return_value = collection
    assert search_similar("timeout") == []


@patch("knowledge.vector_store.get_collection")
def test_success_maps_rows(mock_get_collection: MagicMock) -> None:
    collection = MagicMock()
    collection.query.return_value = {
        "ids": [["PROJ-1", "PROJ-2"]],
        "documents": [["alpha doc", "beta doc"]],
        "metadatas": [[{"issue_key": "PROJ-1"}, {"issue_key": "PROJ-2"}]],
        "distances": [[0.11, 0.22]],
    }
    mock_get_collection.return_value = collection

    out = search_similar("database timeout", k=5)

    assert len(out) == 2
    assert out[0] == {
        "id": "PROJ-1",
        "document": "alpha doc",
        "metadata": {"issue_key": "PROJ-1"},
        "distance": 0.11,
    }
    assert out[1]["id"] == "PROJ-2"
    collection.query.assert_called_once_with(query_texts=["database timeout"], n_results=5)


@patch("knowledge.vector_store.get_collection")
def test_mismatched_parallel_arrays_no_index_error(mock_get_collection: MagicMock) -> None:
    """If Chroma returns uneven ids/documents/metadatas/distances, stay in bounds."""
    collection = MagicMock()
    collection.query.return_value = {
        "ids": [["id1", "id2", "id3"]],
        "documents": [["only_doc"]],
        "metadatas": [[{"issue_key": "PROJ-99"}]],
        "distances": [[0.5]],
    }
    mock_get_collection.return_value = collection

    out = search_similar("query")

    assert len(out) == 3
    assert out[0]["document"] == "only_doc"
    assert out[0]["metadata"] == {"issue_key": "PROJ-99"}
    assert out[0]["distance"] == 0.5
    assert out[1]["document"] == ""
    assert out[1]["metadata"] == {}
    assert out[1]["distance"] is None
    assert out[2]["document"] == ""
    assert out[2]["metadata"] == {}
    assert out[2]["distance"] is None


@patch("knowledge.vector_store.get_collection")
def test_non_dict_metadata_becomes_empty_dict(mock_get_collection: MagicMock) -> None:
    collection = MagicMock()
    collection.query.return_value = {
        "ids": [["x"]],
        "documents": [["text"]],
        "metadatas": [["not-a-dict"]],
        "distances": [[None]],
    }
    mock_get_collection.return_value = collection

    out = search_similar("q")
    assert len(out) == 1
    assert out[0]["metadata"] == {}
