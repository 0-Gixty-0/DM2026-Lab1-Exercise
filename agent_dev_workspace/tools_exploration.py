from typing import Dict, Any, Union, Optional
import numpy as np
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

    return [cosine_similarity_tool]
