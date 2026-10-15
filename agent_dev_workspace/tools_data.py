import os
from typing import Dict, Any, Optional
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import nltk
from nltk.tokenize import word_tokenize
from langchain_core.tools import tool

# Ensure nltk tokenizer resources are available
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)
try:
    nltk.data.find("tokenizers/punkt_tab")
except LookupError:
    nltk.download("punkt_tab", quiet=True)


def _compute_describe_stats(series: pd.Series) -> Dict[str, float]:
    """Helper function to calculate .describe() stats on a pandas Series."""
    desc = series.describe()
    return {
        "count": float(desc.get("count", 0)),
        "mean": float(desc.get("mean", 0.0)),
        "std": float(desc.get("std", 0.0)),
        "min": float(desc.get("min", 0.0)),
        "25%": float(desc.get("25%", 0.0)),
        "50%": float(desc.get("50%", 0.0)),
        "75%": float(desc.get("75%", 0.0)),
        "max": float(desc.get("max", 0.0)),
    }


def make_tools(session):
    @tool
    def list_files_tool(subdirectory: str = ".") -> Dict[str, Any]:
        """Lists files and directories in the target workspace path.

        Args:
            subdirectory: Path relative to the root directory (default ".").

        Returns:
            Dict containing lists of file paths and directory paths,
            plus a result_id.
        """
        result_id = session.next_result_id("list_files")

        target_dir = os.path.abspath(subdirectory)
        if not os.path.exists(target_dir):
            summary = {
                "result_id": result_id,
                "error": f"Directory not found: {subdirectory}",
                "files": [],
                "directories": [],
            }
            session.store_result("list_files_tool", {"subdirectory": subdirectory}, summary)
            return summary

        files = []
        directories = []

        for entry in os.scandir(target_dir):
            if entry.is_file():
                files.append(entry.path)
            elif entry.is_dir():
                directories.append(entry.path)

        files.sort()
        directories.sort()

        summary = {
            "result_id": result_id,
            "subdirectory": subdirectory,
            "files": files,
            "directories": directories,
        }

        session.store_result("list_files_tool", {"subdirectory": subdirectory}, summary)
        return summary

    @tool
    def check_missing_tool(column: str = "text") -> Dict[str, Any]:
        """Checks for missing or empty text values in the session DataFrame.

        Detects nulls, NaNs, Nones, and empty/whitespace-only strings in the
        specified column.

        Args:
            column: Name of the column to check for missing values (default "text").

        Returns:
            Dict containing result_id, missing_count, and missing_indices.
        """
        result_id = session.next_result_id("check_missing")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "missing_count": 0,
                "missing_indices": [],
            }
            session.store_result("check_missing_tool", {"column": column}, summary)
            return summary

        df = session.dataframe
        if column not in df.columns:
            summary = {
                "result_id": result_id,
                "error": f"Column '{column}' not found in dataframe.",
                "missing_count": 0,
                "missing_indices": [],
            }
            session.store_result("check_missing_tool", {"column": column}, summary)
            return summary

        series = df[column]

        # Check for pandas NA/null values
        is_na = series.isna()

        # Check for empty or whitespace-only string values
        is_empty_str = series.apply(
            lambda x: isinstance(x, str) and len(x.strip()) == 0
        )

        missing_mask = is_na | is_empty_str
        missing_indices = df.index[missing_mask].tolist()
        missing_count = int(missing_mask.sum())

        summary = {
            "result_id": result_id,
            "column": column,
            "missing_count": missing_count,
            "missing_indices": missing_indices,
        }

        session.store_result("check_missing_tool", {"column": column}, summary)
        return summary

    @tool
    def check_duplicates_tool(keep: bool = True) -> Dict[str, Any]:
        """Checks for (and optionally removes) duplicate documents in session.dataframe.

        Args:
            keep: If True, duplicate rows are kept (retained) in the DataFrame.
                  If False, duplicate rows are removed using keep=False (dropping all copies).

        Returns:
            Dict containing result_id, duplicate_count, and remaining_rows.
        """
        result_id = session.next_result_id("check_duplicates")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "duplicate_count": 0,
                "remaining_rows": 0,
            }
            session.store_result("check_duplicates_tool", {"keep": keep}, summary)
            return summary

        df = session.dataframe

        # Identify duplicate rows (keep='first' counts extra duplicate occurrences)
        dup_mask = df.duplicated(keep="first")
        duplicate_count = int(dup_mask.sum())

        # If keep is False, remove duplicates using keep=False (dropping all duplicate copies)
        if not keep and duplicate_count > 0:
            session.dataframe = df.drop_duplicates(keep=False).reset_index(drop=True)

        remaining_rows = len(session.dataframe)

        summary = {
            "result_id": result_id,
            "duplicate_count": duplicate_count,
            "remaining_rows": remaining_rows,
            "keep": keep,
        }

        session.store_result("check_duplicates_tool", {"keep": keep}, summary)
        return summary

    @tool
    def sample_data_tool(n: Optional[int] = None, seed: int = 42) -> Dict[str, Any]:
        """Subsamples session.dataframe and returns the list of sampled row indices.

        Args:
            n: Number of samples to draw. If None, defaults to full length of dataframe.
            seed: Seed value for the random state (default 42).

        Returns:
            Dict containing result_id, n, seed, and sampled_indices.
        """
        result_id = session.next_result_id("sample_data")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "sampled_indices": [],
            }
            session.store_result("sample_data_tool", {"n": n, "seed": seed}, summary)
            return summary

        df = session.dataframe

        # If n is None, default to full length of dataset
        if n is None:
            sample_size = len(df)
        else:
            sample_size = min(n, len(df))

        # Sample using pandas DataFrame.sample with seed (default 42)
        sampled_df = df.sample(n=sample_size, random_state=seed)
        sampled_indices = sampled_df.index.tolist()

        summary = {
            "result_id": result_id,
            "n": sample_size,
            "seed": seed,
            "sampled_indices": sampled_indices,
        }

        session.store_result("sample_data_tool", {"n": n, "seed": seed}, summary)
        return summary

    @tool
    def describe_data_tool() -> Dict[str, Any]:
        """Computes text character lengths and descriptive stats overall and per category.

        Also generates a boxplot of text length grouped by category, setting
        session.pending_figure per contract requirement.

        Returns:
            Dict containing result_id, n_documents, overall_stats, and per_category_stats.
        """
        result_id = session.next_result_id("describe_data")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "n_documents": 0,
                "overall_stats": {},
                "per_category_stats": {},
            }
            session.store_result("describe_data_tool", {}, summary)
            return summary

        df = session.dataframe.copy()
        text_column = "text" if "text" in df.columns else df.columns[0]

        # Character count per document in dataframe order
        df["text_length"] = df[text_column].apply(lambda x: len(str(x)) if pd.notna(x) and x is not None else 0)

        # Overall descriptive stats using helper function
        overall_stats = _compute_describe_stats(df["text_length"])

        # Per category descriptive stats using helper function
        per_category_stats = {}
        category_col = "category_name" if "category_name" in df.columns else ("label" if "label" in df.columns else "category")
        if category_col in df.columns:
            for cat, group in df.groupby(category_col):
                per_category_stats[str(cat)] = _compute_describe_stats(group["text_length"])

        # Build boxplot figure and assign to session.pending_figure per contract
        fig, ax = plt.subplots(figsize=(6, 4))
        if category_col in df.columns:
            sns.boxplot(data=df, x=category_col, y="text_length", ax=ax)
            ax.set_title("Text Length by Category")
            ax.set_xlabel("Category")
            ax.set_ylabel("Text Length (chars)")
        else:
            sns.boxplot(y=df["text_length"], ax=ax)
            ax.set_title("Text Length Distribution")
            ax.set_ylabel("Text Length (chars)")

        plt.tight_layout()
        session.pending_figure = fig

        summary = {
            "result_id": result_id,
            "n_documents": len(df),
            "overall_stats": overall_stats,
            "per_category_stats": per_category_stats,
        }

        # Store full report with text_lengths in session.results_store
        session.store_result("describe_data_tool", {}, summary, full_report=df[["text_length"]])
        return summary

    @tool
    def tokenize_tool(column: str = "text") -> Dict[str, Any]:
        """Tokenizes document text into unigrams after lowercasing.

        Updates session.dataframe['unigrams'] and session.artifacts['tokens'].

        Args:
            column: Text column to tokenize (default "text").

        Returns:
            Dict containing result_id, n_documents, total_tokens, and sample_tokens.
        """
        result_id = session.next_result_id("tokenize")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "n_documents": 0,
                "total_tokens": 0,
                "sample_tokens": [],
            }
            session.store_result("tokenize_tool", {"column": column}, summary)
            return summary

        df = session.dataframe

        if column not in df.columns:
            summary = {
                "result_id": result_id,
                "error": f"Column '{column}' not found in dataframe.",
                "n_documents": 0,
                "total_tokens": 0,
                "sample_tokens": [],
            }
            session.store_result("tokenize_tool", {"column": column}, summary)
            return summary

        def _tokenize_text(val):
            if pd.isna(val) or val is None:
                return []
            text_str = str(val).lower()
            if not text_str.strip():
                return []
            return word_tokenize(text_str)

        tokens_series = df[column].apply(_tokenize_text)

        # Store unigrams column in session.dataframe
        df["unigrams"] = tokens_series
        tokenized_docs = tokens_series.tolist()

        # Save tokens artifact into session
        session.artifacts["tokens"] = tokenized_docs

        total_tokens = sum(len(doc_tokens) for doc_tokens in tokenized_docs)
        sample_tokens = tokenized_docs[:3]  # First 3 documents preview for LLM context

        summary = {
            "result_id": result_id,
            "n_documents": len(df),
            "total_tokens": total_tokens,
            "sample_tokens": sample_tokens,
        }

        session.store_result("tokenize_tool", {"column": column}, summary)
        return summary

    @tool
    def inspect_data_tool(n: int = 2, max_characters: int = 200, seed: int = 42) -> Dict[str, Any]:
        """Inspects category label distribution and previews random text samples per category.

        Args:
            n: Number of sample texts to peek for each category (default 2).
            max_characters: Maximum characters to show per sample before truncating
                           with ellipses (default 200).
            seed: Seed value for random state sampling (default 42).

        Returns:
            Dict containing result_id, label_distribution (category_name and percentage),
            and grouped_samples per category.
        """
        result_id = session.next_result_id("inspect_data")

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "label_distribution": [],
                "grouped_samples": {},
            }
            session.store_result("inspect_data_tool", {"n": n, "max_characters": max_characters, "seed": seed}, summary)
            return summary

        df = session.dataframe
        category_col = "category_name" if "category_name" in df.columns else ("label" if "label" in df.columns else "category")
        text_col = "text" if "text" in df.columns else df.columns[0]

        if category_col not in df.columns:
            summary = {
                "result_id": result_id,
                "error": f"Category column '{category_col}' not found in dataframe.",
                "label_distribution": [],
                "grouped_samples": {},
            }
            session.store_result("inspect_data_tool", {"n": n, "max_characters": max_characters, "seed": seed}, summary)
            return summary

        # 1. Calculate label distribution table with category_name and percentage (rounded to 3 decimal places)
        total_docs = len(df)
        counts = df[category_col].value_counts()
        label_distribution = []

        for category_name, count in counts.items():
            percentage = round(float((count / total_docs) * 100.0), 3)
            label_distribution.append({
                "category_name": str(category_name),
                "percentage": percentage,
            })

        # 2. Randomly sample n texts per category using DataFrame.sample(random_state=seed)
        grouped_samples = {}
        for category_name, group in df.groupby(category_col):
            sample_size = min(n, len(group))
            sampled_texts = group[text_col].sample(n=sample_size, random_state=seed).tolist()

            formatted_samples = []
            for text in sampled_texts:
                text_str = str(text) if pd.notna(text) and text is not None else ""
                if len(text_str) > max_characters:
                    text_str = text_str[:max_characters] + "..."
                formatted_samples.append(text_str)

            grouped_samples[str(category_name)] = formatted_samples

        summary = {
            "result_id": result_id,
            "label_distribution": label_distribution,
            "grouped_samples": grouped_samples,
        }

        session.store_result("inspect_data_tool", {"n": n, "max_characters": max_characters, "seed": seed}, summary)
        return summary

    return [
        list_files_tool,
        check_missing_tool,
        check_duplicates_tool,
        sample_data_tool,
        describe_data_tool,
        tokenize_tool,
        inspect_data_tool,
    ]
