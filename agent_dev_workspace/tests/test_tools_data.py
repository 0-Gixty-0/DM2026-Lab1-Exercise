import pytest
import numpy as np
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_data import make_tools


def test_list_files_tool():
    # Initialize state and tool
    session = SessionState()
    tools = make_tools(session)
    list_files_tool = next(t for t in tools if t.name == "list_files_tool")

    # Invoke tool on 'newdataset' subfolder as specified in TEST_FIXTURE.md Known Answer #11
    result = list_files_tool.invoke({"subdirectory": "newdataset"})

    # Assert results match Known Answer #11 specification
    assert "files" in result
    assert "directories" in result
    assert len(result["directories"]) == 0
    assert len(result["files"]) == 1
    assert any("Reddit-stock-sentiment.csv" in f for f in result["files"])


def test_check_missing_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    tools = make_tools(session)
    check_missing_tool = next(t for t in tools if t.name == "check_missing_tool")

    # Load fixture data into session
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    # Invoke check_missing_tool
    result = check_missing_tool.invoke({"column": "text"})

    # Assert known answer #2 requirements from TEST_FIXTURE.md:
    # Exactly 1 row has missing/empty text (index 7, the last row)
    assert result["missing_count"] == 1
    assert result["missing_indices"] == [7]


def test_check_duplicates_tool():
    # Test keep=True (reporting duplicates without dropping)
    session1 = SessionState()
    premade_tools1, _ = load_workspace_tools("premade_tools", session1)
    load_dataset_tool1 = next(t for t in premade_tools1 if t.name == "load_dataset_tool")
    tools1 = make_tools(session1)
    check_duplicates_tool1 = next(t for t in tools1 if t.name == "check_duplicates_tool")

    load_dataset_tool1.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    res_keep = check_duplicates_tool1.invoke({"keep": True})
    assert res_keep["duplicate_count"] == 1
    assert res_keep["remaining_rows"] == 8
    assert len(session1.dataframe) == 8

    # Test keep=False (dropping duplicates with keep=False)
    session2 = SessionState()
    premade_tools2, _ = load_workspace_tools("premade_tools", session2)
    load_dataset_tool2 = next(t for t in premade_tools2 if t.name == "load_dataset_tool")
    tools2 = make_tools(session2)
    check_duplicates_tool2 = next(t for t in tools2 if t.name == "check_duplicates_tool")

    load_dataset_tool2.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    # Record the text of original rows 5 and 6 before dropping ("always gamma delta")
    dup_text = session2.dataframe.loc[5, "text"]
    assert session2.dataframe.loc[6, "text"] == dup_text

    res_drop = check_duplicates_tool2.invoke({"keep": False})
    assert res_drop["duplicate_count"] == 1
    assert res_drop["remaining_rows"] == 6
    assert len(session2.dataframe) == 6

    # Verify that both copies ("always gamma delta") are no longer in the dataframe
    assert dup_text not in session2.dataframe["text"].values


def test_sample_data_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    tools = make_tools(session)
    sample_data_tool = next(t for t in tools if t.name == "sample_data_tool")

    # Load fixture data into session
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    # Invoke sample_data_tool with n=4, seed=42
    result = sample_data_tool.invoke({"n": 4, "seed": 42})

    # Assert known answer #13 requirements from TEST_FIXTURE.md:
    # Exactly returns sampled indices [1, 5, 0, 7]
    assert result["sampled_indices"] == [1, 5, 0, 7]


def test_describe_data_tool():
    # Initialize fresh session and tools
    session = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")

    tools = make_tools(session)
    describe_data_tool = next(t for t in tools if t.name == "describe_data_tool")

    # Load fixture data into session
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label"
    })

    # Invoke describe_data_tool
    result = describe_data_tool.invoke({})

    # Assert Known Answer #18 text_lengths
    expected_text_lengths = [29, 23, 17, 30, 24, 18, 18, 0]
    assert result["text_lengths"] == expected_text_lengths

    # Assert Known Answer #18 overall stats
    overall = result["overall_stats"]
    assert overall["count"] == 8
    assert np.isclose(overall["mean"], 19.875, atol=1e-3)
    assert np.isclose(overall["std"], 9.4330, atol=1e-3)
    assert np.isclose(overall["min"], 0.0, atol=1e-3)
    assert np.isclose(overall["25%"], 17.75, atol=1e-3)
    assert np.isclose(overall["50%"], 20.5, atol=1e-3)
    assert np.isclose(overall["75%"], 25.25, atol=1e-3)
    assert np.isclose(overall["max"], 30.0, atol=1e-3)

    # Assert Known Answer #18 per-category stats for catA
    catA = result["per_category_stats"]["catA"]
    assert catA["count"] == 4
    assert np.isclose(catA["mean"], 17.25, atol=1e-3)
    assert np.isclose(catA["std"], 12.5, atol=1e-3)
    assert np.isclose(catA["min"], 0.0, atol=1e-3)
    assert np.isclose(catA["25%"], 12.75, atol=1e-3)
    assert np.isclose(catA["50%"], 20.0, atol=1e-3)
    assert np.isclose(catA["75%"], 24.5, atol=1e-3)
    assert np.isclose(catA["max"], 29.0, atol=1e-3)

    # Assert Known Answer #18 per-category stats for catB
    catB = result["per_category_stats"]["catB"]
    assert catB["count"] == 4
    assert np.isclose(catB["mean"], 22.5, atol=1e-3)
    assert np.isclose(catB["std"], 5.7446, atol=1e-3)
    assert np.isclose(catB["min"], 18.0, atol=1e-3)
    assert np.isclose(catB["25%"], 18.0, atol=1e-3)
    assert np.isclose(catB["50%"], 21.0, atol=1e-3)
    assert np.isclose(catB["75%"], 25.5, atol=1e-3)
    assert np.isclose(catB["max"], 30.0, atol=1e-3)

    # Assert figure was attached to pending_figure
    assert session.pending_figure is not None
