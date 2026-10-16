import pytest
import numpy as np
from agent_pipeline.session_state import SessionState
from agent_pipeline.workspace_loader import load_workspace_tools
from tools_dtm import make_tools as make_dtm_tools
from tools_reduction import make_tools as make_reduction_tools


def test_reduce_dimensions_pca_fixture():
    """Tests reduce_dimensions_tool (PCA) against known answer #7 in TEST_FIXTURE.md."""
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

    reduction_tools = make_reduction_tools(session)
    reduce_dimensions_tool = next(t for t in reduction_tools if t.name == "reduce_dimensions_tool")

    res = reduce_dimensions_tool.invoke({"method": "pca", "n_components": 2})

    # Assert known answer #7 coordinates from session.artifacts
    expected_pca_coords = np.array([
        [2.3669, 0.8871],
        [1.7039, 0.2642],
        [1.0408, -0.3587],
        [-2.0759, 1.0129],
        [-1.4554, 0.3405],
        [-0.8349, -0.3319],
        [-0.8349, -0.3319],
        [0.0894, -1.4822],
    ])

    actual_coords = np.array(session.artifacts["reduced_coords_pca"])
    np.testing.assert_allclose(actual_coords, expected_pca_coords, atol=1e-3)

    # Assert explained variance ratio from #7
    expected_var_ratio = [0.7532, 0.1965]
    np.testing.assert_allclose(res["explained_variance_ratio"], expected_var_ratio, atol=1e-3)
    assert session.pending_figure is not None


def test_reduce_dimensions_tsne_determinism():
    """Tests reduce_dimensions_tool (t-SNE) determinism across repeated runs."""
    session1 = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session1)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })

    dtm_tools1 = make_dtm_tools(session1)
    build_dtm_tool1 = next(t for t in dtm_tools1 if t.name == "build_dtm_tool")
    build_dtm_tool1.invoke({})

    reduction_tools1 = make_reduction_tools(session1)
    reduce_dimensions_tool1 = next(t for t in reduction_tools1 if t.name == "reduce_dimensions_tool")

    # Run 1
    res1 = reduce_dimensions_tool1.invoke({
        "method": "tsne",
        "n_components": 2,
        "perplexity": 2,
        "seed": 42,
    })

    # Run 2 on fresh session
    session2 = SessionState()
    premade_tools2, _ = load_workspace_tools("premade_tools", session2)
    load_dataset_tool2 = next(t for t in premade_tools2 if t.name == "load_dataset_tool")
    load_dataset_tool2.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })
    build_dtm_tools2 = make_dtm_tools(session2)
    build_dtm2 = next(t for t in build_dtm_tools2 if t.name == "build_dtm_tool")
    build_dtm2.invoke({})
    reduction_tools2 = make_reduction_tools(session2)
    reduce_dimensions_tool2 = next(t for t in reduction_tools2 if t.name == "reduce_dimensions_tool")

    res2 = reduce_dimensions_tool2.invoke({
        "method": "tsne",
        "n_components": 2,
        "perplexity": 2,
        "seed": 42,
    })

    # Assert run 1 and run 2 are identical (deterministic) using session.artifacts
    coords1 = np.array(session1.artifacts["reduced_coords_tsne"])
    coords2 = np.array(session2.artifacts["reduced_coords_tsne"])
    np.testing.assert_allclose(coords1, coords2, atol=1e-5)
    assert coords1.shape == (8, 2)
    assert not np.isnan(coords1).any()
    assert session1.pending_figure is not None


def test_reduce_dimensions_umap_determinism():
    """Tests reduce_dimensions_tool (UMAP) determinism across repeated runs."""
    session1 = SessionState()
    premade_tools, _ = load_workspace_tools("premade_tools", session1)
    load_dataset_tool = next(t for t in premade_tools if t.name == "load_dataset_tool")
    load_dataset_tool.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })

    dtm_tools1 = make_dtm_tools(session1)
    build_dtm_tool1 = next(t for t in dtm_tools1 if t.name == "build_dtm_tool")
    build_dtm_tool1.invoke({})

    reduction_tools1 = make_reduction_tools(session1)
    reduce_dimensions_tool1 = next(t for t in reduction_tools1 if t.name == "reduce_dimensions_tool")

    # Run 1
    res1 = reduce_dimensions_tool1.invoke({
        "method": "umap",
        "n_components": 2,
        "n_neighbors": 3,
        "seed": 42,
    })

    # Run 2 on fresh session
    session2 = SessionState()
    premade_tools2, _ = load_workspace_tools("premade_tools", session2)
    load_dataset_tool2 = next(t for t in premade_tools2 if t.name == "load_dataset_tool")
    load_dataset_tool2.invoke({
        "file_path": "agent_dev/sample_fixture.csv",
        "text_column": "text",
        "label_column": "label",
    })
    build_dtm_tools2 = make_dtm_tools(session2)
    build_dtm2 = next(t for t in build_dtm_tools2 if t.name == "build_dtm_tool")
    build_dtm2.invoke({})
    reduction_tools2 = make_reduction_tools(session2)
    reduce_dimensions_tool2 = next(t for t in reduction_tools2 if t.name == "reduce_dimensions_tool")

    res2 = reduce_dimensions_tool2.invoke({
        "method": "umap",
        "n_components": 2,
        "n_neighbors": 3,
        "seed": 42,
    })

    # Assert run 1 and run 2 are identical (deterministic) using session.artifacts
    coords1 = np.array(session1.artifacts["reduced_coords_umap"])
    coords2 = np.array(session2.artifacts["reduced_coords_umap"])
    np.testing.assert_allclose(coords1, coords2, atol=1e-5)
    assert coords1.shape == (8, 2)
    assert not np.isnan(coords1).any()
    assert session1.pending_figure is not None


def test_binarize_labels_tool_fixture():
    """Tests binarize_labels_tool one-hot encoding on sample_fixture.csv."""
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

    reduction_tools = make_reduction_tools(session)
    binarize_labels_tool = next(t for t in reduction_tools if t.name == "binarize_labels_tool")

    res = binarize_labels_tool.invoke({})

    assert res["categories"] == ["catA", "catB"]
    assert res["n_documents"] == 8

    # Expected one-hot vectors for rows 0-7: [catA, catA, catA, catB, catB, catB, catB, catA]
    expected_matrix = [
        [1, 0],  # row 0: catA
        [1, 0],  # row 1: catA
        [1, 0],  # row 2: catA
        [0, 1],  # row 3: catB
        [0, 1],  # row 4: catB
        [0, 1],  # row 5: catB
        [0, 1],  # row 6: catB
        [1, 0],  # row 7: catA
    ]

    assert session.artifacts["binarized_labels"] == expected_matrix
