from typing import Dict, Any, List, Optional, Literal
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import umap
from langchain_core.tools import tool


def make_tools(session):
    @tool
    def reduce_dimensions_tool(
        method: Literal["pca", "tsne", "umap"] = "pca",
        n_components: int = 2,
        seed: int = 42,
        perplexity: float = 30.0,
        n_neighbors: int = 15,
    ) -> Dict[str, Any]:
        """Reduces feature matrix dimensionality using PCA, t-SNE, or UMAP and plots scatter plot.

        Operates on session.feature_matrix. Generates a scatter plot colored by category label
        and stores the figure in session.pending_figure. Accepts random_state/seed, perplexity,
        and n_neighbors for deterministic behavior and tuning.

        Args:
            method: Dimensionality reduction technique ("pca", "tsne", or "umap", default "pca").
            n_components: Target dimensions, either 2 or 3 (default 2).
            seed: Random seed for reproducibility (default 42).
            perplexity: Perplexity parameter for t-SNE (default 30.0).
            n_neighbors: Number of neighbors parameter for UMAP (default 15).

        Returns:
            Dict containing result_id, method, n_components, coordinates (nested list),
            category_names, and explained_variance_ratio (PCA only).
        """
        result_id = session.next_result_id("reduce_dimensions")

        if n_components not in (2, 3):
            summary = {
                "result_id": result_id,
                "error": f"Invalid n_components: {n_components}. Only 2 or 3 dimensions are supported.",
                "coordinates": [],
                "explained_variance_ratio": None,
            }
            session.store_result("reduce_dimensions_tool", {"method": method, "n_components": n_components}, summary)
            return summary

        if session.feature_matrix is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run before reduce_dimensions_tool.",
                "coordinates": [],
                "explained_variance_ratio": None,
            }
            session.store_result("reduce_dimensions_tool", {"method": method}, summary)
            return summary

        # Dense array from sparse feature matrix
        matrix_dense = session.feature_matrix.toarray() if hasattr(session.feature_matrix, "toarray") else np.asarray(session.feature_matrix)
        n_samples = matrix_dense.shape[0]

        method_lower = method.lower()
        explained_variance_ratio = None

        try:
            if method_lower == "pca":
                pca = PCA(n_components=n_components, random_state=seed)
                coordinates_array = pca.fit_transform(matrix_dense)
                explained_variance_ratio = pca.explained_variance_ratio_.tolist()

            elif method_lower == "tsne":
                # Standard scikit-learn TSNE with standard defaults + user parameters
                effective_perplexity = min(perplexity, max(1.0, float(n_samples - 1)))
                tsne_model = TSNE(
                    n_components=n_components,
                    perplexity=effective_perplexity,
                    random_state=seed,
                )
                coordinates_array = tsne_model.fit_transform(matrix_dense)

            elif method_lower == "umap":
                # Standard umap-learn UMAP with standard defaults + user parameters
                effective_n_neighbors = min(n_neighbors, max(2, n_samples - 1)) if n_samples > 2 else 2
                reducer = umap.UMAP(
                    n_components=n_components,
                    n_neighbors=effective_n_neighbors,
                    random_state=seed,
                )
                coordinates_array = reducer.fit_transform(matrix_dense)

            else:
                raise ValueError(f"Unsupported reduction method: '{method}'. Choose 'pca', 'tsne', or 'umap'.")

        except Exception as e:
            summary = {
                "result_id": result_id,
                "error": f"Error performing {method} reduction: {str(e)}",
                "coordinates": [],
                "explained_variance_ratio": None,
            }
            session.store_result("reduce_dimensions_tool", {"method": method}, summary)
            return summary

        # Store reduced coordinates artifact in session state
        coordinates_list = coordinates_array.tolist()
        session.artifacts[f"reduced_coords_{method_lower}"] = coordinates_list

        # Extract category labels for scatter plot coloring
        if session.labels is not None and len(session.labels) == n_samples:
            category_labels = [str(lbl) for lbl in session.labels]
        elif session.dataframe is not None and "category_name" in session.dataframe.columns:
            category_labels = session.dataframe["category_name"].astype(str).tolist()
        elif session.dataframe is not None and "label" in session.dataframe.columns:
            category_labels = session.dataframe["label"].astype(str).tolist()
        else:
            category_labels = ["default"] * n_samples

        # Create scatter plot figure (2D or 3D)
        df_plot = pd.DataFrame(
            coordinates_array,
            columns=[f"Dim{i+1}" for i in range(n_components)]
        )
        df_plot["Category"] = category_labels

        if n_components == 2:
            fig, ax = plt.subplots(figsize=(7, 5))
            sns.scatterplot(
                data=df_plot,
                x="Dim1",
                y="Dim2",
                hue="Category",
                palette="tab10",
                style="Category",
                s=100,
                ax=ax,
            )
            ax.set_title(f"Dimensionality Reduction: {method_lower.upper()} (2D)")
            ax.set_xlabel("Component 1")
            ax.set_ylabel("Component 2")
            plt.tight_layout()
        else:
            # 3D scatter plot
            fig = plt.figure(figsize=(8, 6))
            ax = fig.add_subplot(111, projection="3d")
            categories = df_plot["Category"].unique()
            colors = sns.color_palette("tab10", n_colors=len(categories))
            cat_to_color = dict(zip(categories, colors))

            for cat in categories:
                sub_df = df_plot[df_plot["Category"] == cat]
                ax.scatter(
                    sub_df["Dim1"],
                    sub_df["Dim2"],
                    sub_df["Dim3"],
                    label=str(cat),
                    color=cat_to_color[cat],
                    s=60,
                )
            ax.set_title(f"Dimensionality Reduction: {method_lower.upper()} (3D)")
            ax.set_xlabel("Component 1")
            ax.set_ylabel("Component 2")
            ax.set_zlabel("Component 3")
            ax.legend(title="Category")
            plt.tight_layout()

        # Set figure on session.pending_figure per mandatory plotting requirement
        session.pending_figure = fig

        summary = {
            "result_id": result_id,
            "method": method_lower,
            "n_components": n_components,
            "n_samples": n_samples,
            "sample_coordinates": coordinates_list[:5],
            "category_names": category_labels[:5],
            "explained_variance_ratio": explained_variance_ratio,
        }

        session.store_result(
            "reduce_dimensions_tool",
            {
                "method": method,
                "n_components": n_components,
                "seed": seed,
                "perplexity": perplexity,
                "n_neighbors": n_neighbors,
            },
            summary,
            full_report=df_plot,
        )
        return summary

    @tool
    def binarize_labels_tool() -> Dict[str, Any]:
        """One-hot encodes category labels into binary vectors.

        Uses session.categories to determine the length and column ordering of the vectors.
        Leaves session.labels untouched and saves the binarized matrix in session.artifacts["binarized_labels"].

        Returns:
            Dict containing result_id, categories, n_documents, and binarized_labels (nested list).
        """
        result_id = session.next_result_id("binarize_labels")

        # Extract labels array from session.labels or session.dataframe
        labels = None
        if session.labels is not None and len(session.labels) > 0:
            labels = [str(lbl) for lbl in session.labels]
        elif session.dataframe is not None:
            category_col = "category_name" if "category_name" in session.dataframe.columns else (
                "label" if "label" in session.dataframe.columns else "category"
            )
            if category_col in session.dataframe.columns:
                labels = session.dataframe[category_col].astype(str).tolist()

        if labels is None or len(labels) == 0:
            summary = {
                "result_id": result_id,
                "error": "No labels found in session (run build_dtm_tool or load dataset first).",
                "categories": [],
                "n_documents": 0,
                "binarized_labels": [],
            }
            session.store_result("binarize_labels_tool", {}, summary)
            return summary

        # Use session.categories if available; otherwise compute sorted unique labels
        if session.categories is not None and len(session.categories) > 0:
            categories = [str(cat) for cat in session.categories]
        else:
            categories = sorted(list(set(labels)))

        # One-hot encode each document label without modifying original session.labels
        cat_to_idx = {cat: i for i, cat in enumerate(categories)}
        n_cats = len(categories)

        binarized_matrix = []
        for lbl in labels:
            vec = [0] * n_cats
            if lbl in cat_to_idx:
                vec[cat_to_idx[lbl]] = 1
            binarized_matrix.append(vec)

        # Store in session.artifacts["binarized_labels"] per pipeline state conventions
        session.artifacts["binarized_labels"] = binarized_matrix

        summary = {
            "result_id": result_id,
            "categories": categories,
            "n_documents": len(binarized_matrix),
            "sample_binarized_labels": binarized_matrix[:3],
        }

        session.store_result("binarize_labels_tool", {}, summary, full_report=binarized_matrix)
        return summary

    return [reduce_dimensions_tool, binarize_labels_tool]
