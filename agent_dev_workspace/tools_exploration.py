from typing import Dict, Any, Union, Optional
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics.pairwise import cosine_similarity
from langchain_core.tools import tool


def make_tools(session):
    @tool
    def cosine_similarity_tool(
        doc_a: Union[int, str],
        doc_b: Union[int, str]
    ) -> Dict[str, Any]:
        """Calculates cosine similarity between two documents.

        Args:
            doc_a: Document index (int) or raw text string.
            doc_b: Document index (int) or raw text string.

        Returns:
            Dict containing result_id, doc_a, doc_b, and similarity_score.
        """
        result_id = session.next_result_id("cosine_similarity")

        # Helper to extract or vectorize 2D count vector for a given input (int index or str text)
        def _get_vector(doc_input: Union[int, str]):
            if isinstance(doc_input, (int, np.integer)):
                if session.feature_matrix is None:
                    raise ValueError("Prerequisite missing: build_dtm_tool must be run to look up document indices.")
                n_docs = session.feature_matrix.shape[0]
                idx = int(doc_input)
                if idx < 0 or idx >= n_docs:
                    raise ValueError(f"Document index {idx} out of range (0 to {n_docs - 1}).")
                return session.feature_matrix[idx : idx + 1]
            elif isinstance(doc_input, str):
                vectorizer = session.artifacts.get("count_vectorizer")
                if vectorizer is None:
                    raise ValueError("Prerequisite missing: count_vectorizer not found in session.artifacts. Run build_dtm_tool first.")
                return vectorizer.transform([doc_input])
            else:
                raise TypeError(f"Invalid input type '{type(doc_input).__name__}'. Expected int or str.")

        try:
            vec_a = _get_vector(doc_a)
            vec_b = _get_vector(doc_b)
        except Exception as e:
            summary = {
                "result_id": result_id,
                "error": str(e),
                "similarity_score": 0.0,
            }
            session.store_result("cosine_similarity_tool", {"doc_a": doc_a, "doc_b": doc_b}, summary)
            return summary

        # Compute cosine similarity
        norm_a = np.linalg.norm(vec_a.toarray())
        norm_b = np.linalg.norm(vec_b.toarray())

        if norm_a == 0 or norm_b == 0:
            sim_score = 0.0
        else:
            sim_matrix = cosine_similarity(vec_a, vec_b)
            sim_score = float(sim_matrix[0, 0])
            if np.isnan(sim_score):
                sim_score = 0.0

        summary = {
            "result_id": result_id,
            "doc_a": doc_a,
            "doc_b": doc_b,
            "similarity_score": round(sim_score, 4),
        }

        session.store_result("cosine_similarity_tool", {"doc_a": doc_a, "doc_b": doc_b}, summary)
        return summary

    @tool
    def feature_correlation_matrix_tool() -> Dict[str, Any]:
        """Calculates Pearson correlation matrix for top-20 terms by variance across full DTM.

        Prerequisite: build_dtm_tool must be run first so session.feature_matrix
        and session.feature_names are available.

        Renders an annotated Seaborn heatmap of the correlation matrix and sets
        it on session.pending_figure. Returns the correlation matrix and term names.

        Returns:
            Dict containing result_id, term_names, correlation_matrix (nested list),
            and n_terms.
        """
        result_id = session.next_result_id("feature_correlation_matrix")

        if session.feature_matrix is None or session.feature_names is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run before feature_correlation_matrix_tool.",
                "term_names": [],
                "correlation_matrix": [],
                "n_terms": 0,
            }
            session.store_result("feature_correlation_matrix_tool", {}, summary)
            return summary

        # Check if DTM belongs to a single category slice instead of the full dataset
        if session.labels is not None and len(session.labels) > 0:
            unique_labels = set(session.labels)
            if len(unique_labels) == 1:
                summary = {
                    "result_id": result_id,
                    "error": (
                        f"Single category detected ('{list(unique_labels)[0]}'). "
                        "feature_correlation_matrix_tool should not be run on a category-specific "
                        "document term matrix, but on the full global matrix across all categories."
                    ),
                    "term_names": [],
                    "correlation_matrix": [],
                    "n_terms": 0,
                }
                session.store_result("feature_correlation_matrix_tool", {}, summary)
                return summary

        matrix = session.feature_matrix
        feature_names = session.feature_names

        # Convert sparse DTM to dense numpy array
        dense_matrix = matrix.toarray() if hasattr(matrix, "toarray") else np.asarray(matrix)

        # 1. Compute per-term population variance across all documents (ddof=0 matches spec)
        variances = np.var(dense_matrix, axis=0, ddof=0)

        # 2. Select top 20 terms by variance (if fewer than 20 terms exist, take all)
        n_top = min(20, len(feature_names))
        top_indices = np.argsort(variances)[::-1][:n_top]

        top_terms = [feature_names[i] for i in top_indices]
        top_submatrix = dense_matrix[:, top_indices]

        # 3. Compute Pearson correlation matrix across top variance terms
        # rowvar=False means columns are features/variables
        if top_submatrix.shape[0] < 2:
            corr_matrix = np.eye(n_top)
        else:
            corr_matrix = np.corrcoef(top_submatrix, rowvar=False)
            # Handle potential 1x1 edge case or NaNs
            corr_matrix = np.nan_to_num(corr_matrix, nan=0.0)

        # Ensure corr_matrix is 2D numpy array
        if corr_matrix.ndim == 0:
            corr_matrix = np.array([[float(corr_matrix)]])
        elif corr_matrix.ndim == 1:
            corr_matrix = corr_matrix.reshape(1, 1)

        # 4. Render Seaborn heatmap with correlation values annotated
        fig, ax = plt.subplots(figsize=(max(6, n_top * 0.6), max(5, n_top * 0.5)))
        sns.heatmap(
            corr_matrix,
            annot=True,
            fmt=".4f",
            cmap="coolwarm",
            vmin=-1.0,
            vmax=1.0,
            xticklabels=top_terms,
            yticklabels=top_terms,
            ax=ax,
        )
        ax.set_title("Feature Correlation Matrix (Top Variance Terms)")
        plt.tight_layout()

        # Set figure on session.pending_figure per contract requirement
        session.pending_figure = fig

        # Convert matrix to JSON-serializable nested list rounded to 4 decimals
        corr_list = np.round(corr_matrix, 4).tolist()

        summary = {
            "result_id": result_id,
            "term_names": top_terms,
            "correlation_matrix": corr_list,
            "n_terms": n_top,
        }

        session.store_result("feature_correlation_matrix_tool", {}, summary)
        return summary

    return [cosine_similarity_tool, feature_correlation_matrix_tool]
