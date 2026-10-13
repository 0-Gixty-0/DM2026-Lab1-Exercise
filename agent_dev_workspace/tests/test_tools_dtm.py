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
