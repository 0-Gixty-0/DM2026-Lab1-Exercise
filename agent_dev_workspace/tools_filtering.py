from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from langchain_core.tools import tool


def make_tools(session):
    @tool
    def variance_filter_tool(threshold: float = 0.0) -> Dict[str, Any]:
        """Calculates per-term variance across session.feature_matrix and flags low-variance terms.

        Prerequisite: build_dtm_tool must be run first so session.feature_matrix
        and session.feature_names are available.

        Args:
            threshold: Variance threshold for keeping terms (default 0.0).
                       Terms with variance < threshold are flagged for removal.

        Returns:
            Dict containing result_id, threshold, n_initial_terms, n_kept_terms,
            n_removed_terms, and top_15_terms (list of dicts with term and variance).
        """
        result_id = session.next_result_id("variance_filter")

        if session.feature_matrix is None or session.feature_names is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run before variance_filter_tool.",
                "n_initial_terms": 0,
                "n_kept_terms": 0,
                "n_removed_terms": 0,
                "top_15_terms": [],
            }
            session.store_result("variance_filter_tool", {"threshold": threshold}, summary)
            return summary

        # Dense array for per-term calculations
        matrix_dense = session.feature_matrix.toarray() if hasattr(session.feature_matrix, "toarray") else np.asarray(session.feature_matrix)
        feature_names = session.feature_names

        # Compute population variance per term
        n_kept = 0
        n_removed = 0
        report_rows = []

        for i, term in enumerate(feature_names):
            counts = matrix_dense[:, i]
            variance = float(np.var(counts, ddof=0))

            if variance >= threshold:
                n_kept += 1
            else:
                n_removed += 1

            report_rows.append({"term": term, "variance": variance})

        # Create full_report DataFrame with term as 1st col, variance as 2nd col
        # Sorted descending by variance as required by visualize_result_tool spec
        full_report = pd.DataFrame(report_rows)
        if not full_report.empty:
            full_report = full_report.sort_values(by="variance", ascending=False).reset_index(drop=True)
            top_15_terms = full_report.head(15).to_dict(orient="records")
        else:
            top_15_terms = []

        summary = {
            "result_id": result_id,
            "threshold": threshold,
            "n_initial_terms": len(feature_names),
            "n_kept_terms": n_kept,
            "n_removed_terms": n_removed,
            "top_15_terms": top_15_terms,
        }

        # Pass full_report to session.store_result per visualize_result_tool spec
        session.store_result("variance_filter_tool", {"threshold": threshold}, summary, full_report=full_report)
        return summary

    @tool
    def pearson_filter_tool(target_class: str, threshold: float = 0.0) -> Dict[str, Any]:
        """Calculates Pearson correlation between term counts and a target class label.

        Args:
            target_class: Target class category name (one-vs-rest binary target).
            threshold: Absolute correlation threshold for keeping terms (default 0.0).

        Returns:
            Dict containing result_id, target_class, threshold, n_initial_terms,
            n_kept_terms, n_removed_terms, and top_15_terms (list of dicts with term and pearson_r).
        """
        result_id = session.next_result_id("pearson_filter")

        if session.feature_matrix is None or session.feature_names is None or session.labels is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run first.",
                "n_initial_terms": 0,
                "n_kept_terms": 0,
                "n_removed_terms": 0,
                "top_15_terms": [],
            }
            session.store_result("pearson_filter_tool", {"target_class": target_class, "threshold": threshold}, summary)
            return summary

        matrix_dense = session.feature_matrix.toarray() if hasattr(session.feature_matrix, "toarray") else np.asarray(session.feature_matrix)
        feature_names = session.feature_names
        labels = np.asarray(session.labels)

        # Convert target class to binary one-vs-rest array (1 if target_class, 0 otherwise)
        binary_target = (labels == target_class).astype(float)

        n_kept = 0
        n_removed = 0
        report_rows = []

        for i, term in enumerate(feature_names):
            counts = matrix_dense[:, i].astype(float)
            if np.std(counts) == 0 or np.std(binary_target) == 0:
                r_val = 0.0
            else:
                r, _ = pearsonr(counts, binary_target)
                r_val = float(r) if not np.isnan(r) else 0.0

            abs_r = abs(r_val)

            if abs_r >= threshold:
                n_kept += 1
            else:
                n_removed += 1

            report_rows.append({"term": term, "pearson_r": r_val, "abs_r": abs_r})

        # full_report DataFrame: term 1st col, pearson_r 2nd col, sorted descending by absolute value
        full_report = pd.DataFrame(report_rows)
        if not full_report.empty:
            full_report = full_report.sort_values(by="abs_r", ascending=False).reset_index(drop=True)
            full_report_export = full_report[["term", "pearson_r"]].copy()
            top_15_terms = full_report[["term", "pearson_r"]].head(15).to_dict(orient="records")
        else:
            full_report_export = pd.DataFrame(columns=["term", "pearson_r"])
            top_15_terms = []

        summary = {
            "result_id": result_id,
            "target_class": target_class,
            "threshold": threshold,
            "n_initial_terms": len(feature_names),
            "n_kept_terms": n_kept,
            "n_removed_terms": n_removed,
            "top_15_terms": top_15_terms,
        }

        session.store_result("pearson_filter_tool", {"target_class": target_class, "threshold": threshold}, summary, full_report=full_report_export)
        return summary

    @tool
    def spearman_filter_tool(target_class: str, threshold: float = 0.0) -> Dict[str, Any]:
        """Calculates Spearman rank correlation between term counts and a target class label.

        Args:
            target_class: Target class category name (one-vs-rest binary target).
            threshold: Absolute correlation threshold for keeping terms (default 0.0).

        Returns:
            Dict containing result_id, target_class, threshold, n_initial_terms,
            n_kept_terms, n_removed_terms, and top_15_terms (list of dicts with term and spearman_r).
        """
        result_id = session.next_result_id("spearman_filter")

        if session.feature_matrix is None or session.feature_names is None or session.labels is None:
            summary = {
                "result_id": result_id,
                "error": "Prerequisite missing: build_dtm_tool must be run first.",
                "n_initial_terms": 0,
                "n_kept_terms": 0,
                "n_removed_terms": 0,
                "top_15_terms": [],
            }
            session.store_result("spearman_filter_tool", {"target_class": target_class, "threshold": threshold}, summary)
            return summary

        matrix_dense = session.feature_matrix.toarray() if hasattr(session.feature_matrix, "toarray") else np.asarray(session.feature_matrix)
        feature_names = session.feature_names
        labels = np.asarray(session.labels)

        # Convert target class to binary one-vs-rest array (1 if target_class, 0 otherwise)
        binary_target = (labels == target_class).astype(float)

        n_kept = 0
        n_removed = 0
        report_rows = []

        for i, term in enumerate(feature_names):
            counts = matrix_dense[:, i].astype(float)
            if np.std(counts) == 0 or np.std(binary_target) == 0:
                rho_val = 0.0
            else:
                rho, _ = spearmanr(counts, binary_target)
                rho_val = float(rho) if not np.isnan(rho) else 0.0

            abs_rho = abs(rho_val)

            if abs_rho >= threshold:
                n_kept += 1
            else:
                n_removed += 1

            report_rows.append({"term": term, "spearman_r": rho_val, "abs_rho": abs_rho})

        # full_report DataFrame: term 1st col, spearman_r 2nd col, sorted descending by absolute value
        full_report = pd.DataFrame(report_rows)
        if not full_report.empty:
            full_report = full_report.sort_values(by="abs_rho", ascending=False).reset_index(drop=True)
            full_report_export = full_report[["term", "spearman_r"]].copy()
            top_15_terms = full_report[["term", "spearman_r"]].head(15).to_dict(orient="records")
        else:
            full_report_export = pd.DataFrame(columns=["term", "spearman_r"])
            top_15_terms = []

        summary = {
            "result_id": result_id,
            "target_class": target_class,
            "threshold": threshold,
            "n_initial_terms": len(feature_names),
            "n_kept_terms": n_kept,
            "n_removed_terms": n_removed,
            "top_15_terms": top_15_terms,
        }

        session.store_result("spearman_filter_tool", {"target_class": target_class, "threshold": threshold}, summary, full_report=full_report_export)
        return summary

    return [variance_filter_tool, pearson_filter_tool, spearman_filter_tool]
