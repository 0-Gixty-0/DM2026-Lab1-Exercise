import pytest
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_patterns import make_tools as make_patterns_tools


def test_mine_patterns_fpgrowth_fixture_17():
    """Tests mine_patterns_tool with algorithm='fpgrowth' against known answer #17 in TEST_FIXTURE.md."""
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })

    pattern_tools = make_patterns_tools(session)
    mine_patterns_tool = next(t for t in pattern_tools if t.name == "mine_patterns_tool")

    # 1. Test variance & term_frequency filtering methods -> keep zero terms on sample_fixture.csv
    res_var_catA = mine_patterns_tool.invoke({
        "category_name": "catA",
        "filtering_method": "variance",
        "algorithm": "fpgrowth",
        "min_sup": 1,
    })
    assert res_var_catA["patterns"] == []
    assert "no terms survived" in res_var_catA["note"].lower()

    res_tf_catB = mine_patterns_tool.invoke({
        "category_name": "catB",
        "filtering_method": "term_frequency",
        "algorithm": "fpgrowth",
        "min_sup": 1,
    })
    assert res_tf_catB["patterns"] == []
    assert "no terms survived" in res_tf_catB["note"].lower()

    # 2. Test tfidf filtering method -> catA keeps alpha (support 3), catB keeps gamma (support 4)
    # catA with min_sup=1
    res_tfidf_catA = mine_patterns_tool.invoke({
        "category_name": "catA",
        "filtering_method": "tfidf",
        "algorithm": "fpgrowth",
        "min_sup": 1,
    })
    pats_catA = res_tfidf_catA["patterns"]
    assert len(pats_catA) == 1
    assert "alpha" in pats_catA[0]["pattern"]
    assert pats_catA[0]["support"] == 3
    assert session.artifacts["patterns_catA_tfidf_fpgrowth"] == pats_catA

    # catA with min_sup=4 -> 0 patterns returned
    res_tfidf_catA_sup4 = mine_patterns_tool.invoke({
        "category_name": "catA",
        "filtering_method": "tfidf",
        "algorithm": "fpgrowth",
        "min_sup": 4,
    })
    assert res_tfidf_catA_sup4["patterns"] == []

    # catB with min_sup=1
    res_tfidf_catB = mine_patterns_tool.invoke({
        "category_name": "catB",
        "filtering_method": "tfidf",
        "algorithm": "fpgrowth",
        "min_sup": 1,
    })
    pats_catB = res_tfidf_catB["patterns"]
    assert len(pats_catB) == 1
    assert "gamma" in pats_catB[0]["pattern"]
    assert pats_catB[0]["support"] == 4
    assert session.artifacts["patterns_catB_tfidf_fpgrowth"] == pats_catB


def test_mine_patterns_topk_and_maxfpgrowth_fixture_20():
    """Tests mine_patterns_tool with topk and maxfpgrowth against known answer #20 in TEST_FIXTURE.md."""
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })

    pattern_tools = make_patterns_tools(session)
    mine_patterns_tool = next(t for t in pattern_tools if t.name == "mine_patterns_tool")

    # 1. algorithm="topk" (PAMI.frequentPattern.topk.FAE): k=1 returns 1 pattern for catA ({alpha}: 3) and catB ({gamma}: 4)
    res_topk_catA = mine_patterns_tool.invoke({
        "category_name": "catA",
        "filtering_method": "tfidf",
        "algorithm": "topk",
        "k": 1,
    })
    pats_topk_catA = res_topk_catA["patterns"]
    assert len(pats_topk_catA) == 1
    assert "alpha" in pats_topk_catA[0]["pattern"]
    assert pats_topk_catA[0]["support"] == 3

    res_topk_catB = mine_patterns_tool.invoke({
        "category_name": "catB",
        "filtering_method": "tfidf",
        "algorithm": "topk",
        "k": 1,
    })
    pats_topk_catB = res_topk_catB["patterns"]
    assert len(pats_topk_catB) == 1
    assert "gamma" in pats_topk_catB[0]["pattern"]
    assert pats_topk_catB[0]["support"] == 4

    # 2. algorithm="maxfpgrowth" (PAMI.frequentPattern.maximal.MaxFPGrowth):
    # Known answer #20 specifies MaxFPGrowth returns ZERO patterns for both categories at min_sup=1 and min_sup=4
    res_maxfp_catA = mine_patterns_tool.invoke({
        "category_name": "catA",
        "filtering_method": "tfidf",
        "algorithm": "maxfpgrowth",
        "min_sup": 1,
    })
    assert res_maxfp_catA["patterns"] == []

    res_maxfp_catB = mine_patterns_tool.invoke({
        "category_name": "catB",
        "filtering_method": "tfidf",
        "algorithm": "maxfpgrowth",
        "min_sup": 1,
    })
    assert res_maxfp_catB["patterns"] == []
