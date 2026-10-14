from typing import Dict, Any, List
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.feature_extraction.text import CountVectorizer
from langchain_core.tools import tool


def make_tools(session):
    @tool
    def build_dtm_tool(
        column: str = "text",
        ngram_range: List[int] = [1, 1],
        min_df: int = 1,
        max_df: float = 1.0,
    ) -> Dict[str, Any]:
        """Builds document-term matrix into session.feature_matrix and session.feature_names.

        Operates on session.dataframe[column] using CountVectorizer to extract terms and counts.
        Stores the fitted vectorizer at session.artifacts['count_vectorizer'] for downstream tools.

        Args:
            column: Text column name to build DTM from (default "text").
            ngram_range: List of 2 ints [min_n, max_n] for n-gram range (default [1, 1]).
                         Note: typed as List[int] for Gemini backend schema safety.
            min_df: Minimum document frequency for terms (default 1).
            max_df: Maximum document frequency ratio for terms (default 1.0).

        Returns:
            Dict containing result_id, n_documents, n_terms, non_zero, total_elements,
            and sparsity_pct.
        """
        result_id = session.next_result_id("build_dtm")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "n_documents": 0,
                "n_terms": 0,
            }
            session.store_result("build_dtm_tool", {}, summary)
            return summary

        df = session.dataframe

        if column not in df.columns:
            summary = {
                "result_id": result_id,
                "error": f"Column '{column}' not found in dataframe.",
                "n_documents": len(df),
                "n_terms": 0,
            }
            session.store_result("build_dtm_tool", {}, summary)
            return summary

        # Read text column directly from session.dataframe
        text_series = df[column].astype(str)

        # Convert ngram_range parameter List[int] -> tuple for CountVectorizer
        ngram_tuple = (int(ngram_range[0]), int(ngram_range[1])) if len(ngram_range) >= 2 else (1, 1)

        # Build CountVectorizer operating directly on text
        vectorizer = CountVectorizer(
            ngram_range=ngram_tuple,
            min_df=min_df,
            max_df=max_df,
        )

        try:
            dtm_matrix = vectorizer.fit_transform(text_series)
            feature_names = vectorizer.get_feature_names_out().tolist()
        except Exception as e:
            summary = {
                "result_id": result_id,
                "error": f"Error building DTM: {str(e)}",
                "n_documents": len(df),
                "n_terms": 0,
            }
            session.store_result("build_dtm_tool", {}, summary)
            return summary

        # Populate session state attributes per TOOLS_PIPELINE_BREAKDOWN.md
        session.feature_matrix = dtm_matrix
        session.feature_names = feature_names

        # Store count_vectorizer artifact for downstream tools like cosine_similarity_tool
        session.artifacts["count_vectorizer"] = vectorizer

        # Set category labels and session.categories if category column present
        category_col = "category_name" if "category_name" in df.columns else ("label" if "label" in df.columns else None)
        if category_col and category_col in df.columns:
            labels_array = df[category_col].values
            session.labels = labels_array
            session.categories = sorted(list(set(labels_array)))

        # Compute matrix dimensions and sparsity matching spec requirement exactly
        n_rows, n_cols = dtm_matrix.shape
        non_zero = int(dtm_matrix.nnz)
        total_elements = int(n_rows * n_cols)
        sparsity_pct = float(100.0 * (1.0 - (non_zero / total_elements))) if total_elements > 0 else 0.0

        summary = {
            "result_id": result_id,
            "n_documents": n_rows,
            "n_terms": n_cols,
            "non_zero": non_zero,
            "total_elements": total_elements,
            "sparsity_pct": sparsity_pct,
            "feature_names": feature_names,
        }

        session.store_result("build_dtm_tool", {}, summary)
        return summary

    @tool
    def term_frequency_tool() -> Dict[str, Any]:
        """Calculates total term frequencies across all documents in session.feature_matrix.

        Prerequisite: build_dtm_tool must be run first so session.feature_matrix
        and session.feature_names are available.

        Returns:
            Dict containing result_id, term_frequencies list, and n_terms.
        """
        result_id = session.next_result_id("term_frequency")

        if session.feature_matrix is None or session.feature_names is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run before term_frequency_tool.",
                "n_terms": 0,
                "term_frequencies": [],
            }
            session.store_result("term_frequency_tool", {}, summary)
            return summary

        matrix = session.feature_matrix
        feature_names = session.feature_names

        # Sum counts across all documents (columns axis=0)
        # Handles sparse matrix sum output
        col_sums = np.asarray(matrix.sum(axis=0)).flatten()

        # Build report DataFrame with terms as 1st col and total_frequency as 2nd col
        df_freq = pd.DataFrame({
            "term": feature_names,
            "total_frequency": col_sums.astype(int),
        })

        # Convert to list of dict records for term_frequencies output
        term_frequencies = df_freq.to_dict(orient="records")

        summary = {
            "result_id": result_id,
            "n_terms": len(feature_names),
            "term_frequencies": term_frequencies,
        }

        # Store full_report DataFrame for visualize_result_tool
        session.store_result("term_frequency_tool", {}, summary, full_report=df_freq)
        return summary

    @tool
    def dtm_heatmap_tool(n_terms: int = 20, n_documents: int = 20) -> Dict[str, Any]:
        """Renders a Seaborn heatmap of a positional slice of the global DTM.

        Prerequisite: build_dtm_tool must be run first so session.feature_matrix
        and session.feature_names are available.

        Args:
            n_terms: Number of terms (columns) to slice from start (default 20).
            n_documents: Number of documents (rows) to slice from start (default 20).

        Returns:
            Dict containing result_id, sliced_matrix (nested list), doc_labels,
            and term_labels.
        """
        result_id = session.next_result_id("dtm_heatmap")

        if session.feature_matrix is None or session.feature_names is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run before dtm_heatmap_tool.",
                "sliced_matrix": [],
                "doc_labels": [],
                "term_labels": [],
            }
            session.store_result("dtm_heatmap_tool", {"n_terms": n_terms, "n_documents": n_documents}, summary)
            return summary

        matrix = session.feature_matrix
        feature_names = session.feature_names

        # Explicitly clamp bounds if matrix dimensions are smaller than requested
        total_docs, total_terms = matrix.shape
        actual_docs = min(n_documents, total_docs)
        actual_terms = min(n_terms, total_terms)

        # Take positional slices bounded by actual dimensions
        sliced_sparse = matrix[0:actual_docs, 0:actual_terms]
        sliced_dense = sliced_sparse.toarray() if hasattr(sliced_sparse, "toarray") else np.asarray(sliced_sparse)

        term_labels = feature_names[0:actual_terms]
        doc_labels = [f"Doc {i}" for i in range(actual_docs)]

        # Build Seaborn heatmap figure
        fig, ax = plt.subplots(figsize=(max(6, len(term_labels) * 0.5), max(4, len(doc_labels) * 0.4)))
        sns.heatmap(
            sliced_dense,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=term_labels,
            yticklabels=doc_labels,
            ax=ax,
        )
        ax.set_title("Document-Term Matrix Heatmap (Raw Counts)")
        ax.set_xlabel("Terms")
        ax.set_ylabel("Documents")
        plt.tight_layout()

        # Set pending figure for frontend rendering per contract
        session.pending_figure = fig

        # Convert numpy array to JSON-serializable nested Python list
        sliced_matrix = sliced_dense.tolist()

        summary = {
            "result_id": result_id,
            "sliced_matrix": sliced_matrix,
            "doc_labels": doc_labels,
            "term_labels": term_labels,
        }

        session.store_result("dtm_heatmap_tool", {"n_terms": n_terms, "n_documents": n_documents}, summary)
        return summary

    return [build_dtm_tool, term_frequency_tool, dtm_heatmap_tool]
