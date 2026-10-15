import pytest
import numpy as np
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_dtm import make_tools as make_dtm_tools
from tools_filtering import make_tools as make_filtering_tools


def test_variance_filter_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_dtm_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")

    filtering_tools = make_filtering_tools(session)
    variance_filter_tool = next(t for t in filtering_tools if t.name == "variance_filter_tool")

    # Load fixture data and build DTM
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })
    build_dtm_tool.invoke({"column": "text"})

    # Invoke variance_filter_tool with threshold=0.15
    result = variance_filter_tool.invoke({"threshold": 0.15})

    # Assert Known Answer #5 variances in TEST_FIXTURE.md via top_15_terms in summary
    expected_variances = {
        "alpha": 1.1875,
        "always": 0.109375,
        "beta": 0.234375,
        "delta": 0.25,
        "gamma": 1.109375,
    }

    term_details_map = {item["term"]: item["variance"] for item in result["top_15_terms"]}

    for term, exp_var in expected_variances.items():
        assert term in term_details_map
        assert np.isclose(term_details_map[term], exp_var, atol=1e-3)

    # Assert threshold=0.15 filtering counts from Known Answer #5
    # Keeps alpha, beta, delta, gamma (4 terms); removes always (1 term)
    assert result["n_initial_terms"] == 5
    assert result["n_kept_terms"] == 4
    assert result["n_removed_terms"] == 1


def test_pearson_filter_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_dtm_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")

    filtering_tools = make_filtering_tools(session)
    pearson_filter_tool = next(t for t in filtering_tools if t.name == "pearson_filter_tool")

    # Load fixture data and build DTM
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })
    build_dtm_tool.invoke({"column": "text"})

    # Invoke pearson_filter_tool with target_class="catB"
    result = pearson_filter_tool.invoke({"target_class": "catB", "threshold": 0.0})

    # Assert Known Answer #6 Pearson r values in TEST_FIXTURE.md via top_15_terms in summary
    expected_pearson = {
        "alpha": -0.6882,
        "always": 0.3780,
        "beta": -0.7746,
        "delta": 1.0000,
        "gamma": 0.8307,
    }

    corr_map = {item["term"]: item["pearson_r"] for item in result["top_15_terms"]}

    for term, exp_r in expected_pearson.items():
        assert term in corr_map
        assert np.isclose(corr_map[term], exp_r, atol=1e-3)

    assert result["n_initial_terms"] == 5
    assert result["n_kept_terms"] == 5
    assert result["n_removed_terms"] == 0


def test_spearman_filter_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    dtm_tools = make_dtm_tools(session)
    build_dtm_tool = next(t for t in dtm_tools if t.name == "build_dtm_tool")

    filtering_tools = make_filtering_tools(session)
    spearman_filter_tool = next(t for t in filtering_tools if t.name == "spearman_filter_tool")

    # Load fixture data and build DTM
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })
    build_dtm_tool.invoke({"column": "text"})

    # Invoke spearman_filter_tool with target_class="catB"
    result = spearman_filter_tool.invoke({"target_class": "catB", "threshold": 0.0})

    # Assert Known Answer #6 Spearman r values in TEST_FIXTURE.md via top_15_terms in summary
    expected_spearman = {
        "alpha": -0.7500,
        "always": 0.3780,
        "beta": -0.7746,
        "delta": 1.0000,
        "gamma": 0.9363,
    }

    corr_map = {item["term"]: item["spearman_r"] for item in result["top_15_terms"]}

    for term, exp_rho in expected_spearman.items():
        assert term in corr_map
        assert np.isclose(corr_map[term], exp_rho, atol=1e-3)

    assert result["n_initial_terms"] == 5
    assert result["n_kept_terms"] == 5
    assert result["n_removed_terms"] == 0
