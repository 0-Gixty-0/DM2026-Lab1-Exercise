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
