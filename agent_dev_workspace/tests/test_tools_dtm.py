import pytest
import numpy as np
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_dtm import make_tools


def test_build_dtm_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")

    # Load fixture data into session
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    # Invoke build_dtm_tool
    result = build_dtm_tool.invoke({"column": "text"})

    # Assert Known Answer #4 requirements from TEST_FIXTURE.md
    expected_vocab = ["alpha", "always", "beta", "delta", "gamma"]
    assert result["feature_names"] == expected_vocab
    assert session.feature_names == expected_vocab

    assert result["n_documents"] == 8
    assert result["n_terms"] == 5
    assert result["non_zero"] == 21
    assert result["total_elements"] == 40
    assert np.isclose(result["sparsity_pct"], 47.5, atol=1e-3)

    # Assert session state matrix and artifacts updated
    assert session.feature_matrix is not None
    assert session.feature_matrix.shape == (8, 5)
    assert "count_vectorizer" in session.artifacts


def test_term_frequency_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")
    term_frequency_tool = next(t for t in dtm_tools if t.name == "term_frequency_tool")

    # Load fixture data and build DTM
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })
    build_dtm_tool.invoke({"column": "text"})

    # Invoke term_frequency_tool
    result = term_frequency_tool.invoke({})

    # Assert Known Answer #14 term frequencies in TEST_FIXTURE.md
    expected_freqs = {
        "alpha": 6,
        "always": 7,
        "beta": 3,
        "delta": 4,
        "gamma": 7,
    }

    tf_map = {item["term"]: item["total_frequency"] for item in result["term_frequencies"]}
    for term, exp_count in expected_freqs.items():
        assert term in tf_map
        assert tf_map[term] == exp_count


def test_dtm_heatmap_tool_fixture():
    """Tests dtm_heatmap_tool against known answer #21 in TEST_FIXTURE.md."""
    # Create single session object and load premade load_dataset_tool
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    # Load fixture dataset into session
    load_res = load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })
    assert load_res["n_documents"] == 8

    # Instantiation of student tools_dtm tools bound to the same session
    dtm_tools = make_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")
    dtm_heatmap_tool = next(t for t in dtm_tools if t.name == "dtm_heatmap_tool")

    # Build DTM first (prerequisite)
    build_res = build_dtm_tool.invoke({})
    assert build_res["n_terms"] == 5
    assert build_res["n_documents"] == 8

    # 1. Test full matrix call (defaults n_terms=20, n_documents=20 exceed fixture size 8x5)
    heatmap_res_full = dtm_heatmap_tool.invoke({"n_terms": 20, "n_documents": 20})

    assert heatmap_res_full["term_labels"] == ["alpha", "always", "beta", "delta", "gamma"]
    assert len(heatmap_res_full["doc_labels"]) == 8
    assert session.pending_figure is not None

    # Expected 8x5 matrix from TEST_FIXTURE.md #21
    expected_full_matrix = [
        [3, 1, 1, 0, 0],  # Doc 0
        [2, 1, 1, 0, 0],  # Doc 1
        [1, 1, 1, 0, 0],  # Doc 2
        [0, 1, 0, 1, 3],  # Doc 3
        [0, 1, 0, 1, 2],  # Doc 4
        [0, 1, 0, 1, 1],  # Doc 5
        [0, 1, 0, 1, 1],  # Doc 6
        [0, 0, 0, 0, 0],  # Doc 7
    ]

    np.testing.assert_array_equal(
        np.array(heatmap_res_full["sliced_matrix"]),
        np.array(expected_full_matrix)
    )

    # 2. Test smaller slice (n_terms=2, n_documents=3) matching top-left 3x2 corner in #21
    heatmap_res_slice = dtm_heatmap_tool.invoke({"n_terms": 2, "n_documents": 3})

    assert heatmap_res_slice["term_labels"] == ["alpha", "always"]
    assert heatmap_res_slice["doc_labels"] == ["Doc 0", "Doc 1", "Doc 2"]

    expected_slice_matrix = [
        [3, 1],
        [2, 1],
        [1, 1],
    ]

    np.testing.assert_array_equal(
        np.array(heatmap_res_slice["sliced_matrix"]),
        np.array(expected_slice_matrix)
    )
