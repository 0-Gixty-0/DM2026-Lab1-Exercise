import pytest
import numpy as np
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_dtm import make_tools as make_dtm_tools
from tools_exploration import make_tools as make_exploration_tools


def test_cosine_similarity_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_dtm_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")

    exploration_tools = make_exploration_tools(session)
    cosine_similarity_tool = next(t for t in exploration_tools if t.name == "cosine_similarity_tool")

    # Load fixture data and build DTM
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })
    build_dtm_tool.invoke({"column": "text"})

    # Assert Known Answer #16 doc index pairs in TEST_FIXTURE.md
    # 0 vs 1 (both catA, near-identical text): 0.9847
    res_0_1 = cosine_similarity_tool.invoke({"doc_a": 0, "doc_b": 1})
    assert np.isclose(res_0_1["similarity_score"], 0.9847, atol=1e-3)

    # 0 vs 3 (catA vs catB, share only "always"): 0.0909
    res_0_3 = cosine_similarity_tool.invoke({"doc_a": 0, "doc_b": 3})
    assert np.isclose(res_0_3["similarity_score"], 0.0909, atol=1e-3)

    # 3 vs 4 (both catB, near-identical text): 0.9847
    res_3_4 = cosine_similarity_tool.invoke({"doc_a": 3, "doc_b": 4})
    assert np.isclose(res_3_4["similarity_score"], 0.9847, atol=1e-3)

    # 0 vs 7 (catA vs empty-text row): 0.0
    res_0_7 = cosine_similarity_tool.invoke({"doc_a": 0, "doc_b": 7})
    assert res_0_7["similarity_score"] == 0.0

    # Test raw text input using count_vectorizer:
    # "always alpha alpha beta" (alpha:2, always:1, beta:1) vs "always alpha beta" (alpha:1, always:1, beta:1)
    # Cosine Similarity = 4 / sqrt(18) = 0.9428
    res_text = cosine_similarity_tool.invoke({"doc_a": "always alpha alpha beta", "doc_b": "always alpha beta"})
    assert np.isclose(res_text["similarity_score"], 0.9428, atol=1e-3)


def test_feature_correlation_matrix_tool_fixture():
    """Tests feature_correlation_matrix_tool against known answer #19 in TEST_FIXTURE.md."""
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })

    dtm_tools = make_dtm_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")
    build_dtm_tool.invoke({})

    exploration_tools = make_exploration_tools(session)
    feature_corr_tool = next(t for t in exploration_tools if t.name == "feature_correlation_matrix_tool")

    res = feature_corr_tool.invoke({})

    # Assert terms ordered descending by variance (alpha, gamma, delta, beta, always)
    expected_terms = ["alpha", "gamma", "delta", "beta", "always"]
    assert res["term_names"] == expected_terms
    assert res["n_terms"] == 5

    # Known answer #19 correlation matrix
    expected_corr = np.array([
        [1.0000, -0.5718, -0.6882,  0.8885,  0.2601],  # alpha
        [-0.5718,  1.0000,  0.8307, -0.6435,  0.3140],  # gamma
        [-0.6882,  0.8307,  1.0000, -0.7746,  0.3780],  # delta
        [0.8885, -0.6435, -0.7746,  1.0000,  0.2928],  # beta
        [0.2601,  0.3140,  0.3780,  0.2928,  1.0000],  # always
    ])

    actual_corr = np.array(res["correlation_matrix"])
    np.testing.assert_allclose(actual_corr, expected_corr, atol=1e-3)

    # Verify pending figure set for heatmap plot
    assert session.pending_figure is not None
