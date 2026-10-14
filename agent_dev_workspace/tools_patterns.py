from typing import Dict, Any, List, Optional, Literal
import os
import tempfile
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from langchain_core.tools import tool


def make_tools(session):
    @tool
    def mine_patterns_tool(
        category_name: str,
        filtering_method: Literal["variance", "tfidf", "term_frequency"] = "tfidf",
        algorithm: Literal["fpgrowth", "topk", "maxfpgrowth"] = "fpgrowth",
        min_sup: int = 1,
        k: int = 1,
    ) -> Dict[str, Any]:
        """Mines frequent patterns per category using PAMI after local text filtering.

        Builds a category-local DTM with CountVectorizer(stop_words="english") on session.dataframe,
        filters vocabulary according to filtering_method, converts to transactional DB, and mines
        patterns using PAMI algorithm (FPGrowth, Top-K, or MaxFPGrowth).

        Results and mined pattern lists are stored in session.artifacts keyed as
        f"patterns_{category_name}_{filtering_method}_{algorithm}" so downstream tools
        and discussion turns can easily reference them by key.

        Args:
            category_name: Category label string to mine (e.g. "catA" or "catB").
            filtering_method: Vocabulary filter ("variance", "tfidf", or "term_frequency", default "tfidf").
            algorithm: PAMI mining algorithm ("fpgrowth", "topk", or "maxfpgrowth", default "fpgrowth").
            min_sup: Minimum support threshold for fpgrowth / maxfpgrowth (default 1).
            k: Top-K pattern limit for topk algorithm (default 1).

        Returns:
            Dict containing result_id, category_name, filtering_method, algorithm,
            min_sup, k, patterns (list of dicts with pattern and support), and note.
        """
        result_id = session.next_result_id("mine_patterns")

        # Define explicit artifact key per contract: f"patterns_{category_name}_{filtering_method}_{algorithm}"
        artifact_key = f"patterns_{category_name}_{filtering_method}_{algorithm}"

        if session.dataframe is None:
            summary = {
                "result_id": result_id,
                "error": "No dataframe loaded in session.",
                "patterns": [],
                "note": "no dataframe loaded",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        df = session.dataframe

        category_col = "category_name" if "category_name" in df.columns else (
            "label" if "label" in df.columns else "category"
        )
        text_col = "text" if "text" in df.columns else df.columns[0]

        if category_col not in df.columns:
            summary = {
                "result_id": result_id,
                "error": f"Category column '{category_col}' not found in dataframe.",
                "patterns": [],
                "note": f"column '{category_col}' missing",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        # 1. Early return check: Category filtering
        df_cat = df[df[category_col].astype(str) == str(category_name)].copy()

        if df_cat.empty:
            summary = {
                "result_id": result_id,
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "patterns": [],
                "note": f"no documents found for category '{category_name}'",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        # 2. Early return check: Stop words removal & local vocabulary extraction
        vectorizer = CountVectorizer(stop_words="english")
        try:
            local_dtm = vectorizer.fit_transform(df_cat[text_col].astype(str))
            local_vocab = vectorizer.get_feature_names_out().tolist()
        except Exception as e:
            summary = {
                "result_id": result_id,
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "patterns": [],
                "note": f"no vocabulary extracted after stop words removal: {str(e)}",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        if len(local_vocab) == 0 or local_dtm.shape[1] == 0:
            summary = {
                "result_id": result_id,
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "patterns": [],
                "note": "no terms survived stopword removal",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        dense_local = local_dtm.toarray()

        # Apply chosen filtering_method percentile bands
        kept_indices = []

        if filtering_method == "variance":
            scores = np.var(dense_local, axis=0, ddof=0)
            p5 = np.percentile(scores, 5)
            p95 = np.percentile(scores, 95)
            kept_indices = [i for i, s in enumerate(scores) if p5 < s < p95]

        elif filtering_method == "term_frequency":
            scores = np.sum(dense_local, axis=0)
            p5 = np.percentile(scores, 5)
            p95 = np.percentile(scores, 95)
            kept_indices = [i for i, s in enumerate(scores) if p5 < s < p95]

        elif filtering_method == "tfidf":
            tfidf_trans = TfidfTransformer()
            tfidf_matrix = tfidf_trans.fit_transform(local_dtm).toarray()
            scores = np.mean(tfidf_matrix, axis=0)
            p20 = np.percentile(scores, 20)
            kept_indices = [i for i, s in enumerate(scores) if s >= p20]

        else:
            raise ValueError(f"Unknown filtering method: '{filtering_method}'")

        # 3. Early return check: Vocabulary filtering
        if len(kept_indices) == 0:
            summary = {
                "result_id": result_id,
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "min_sup": min_sup if algorithm in ["fpgrowth", "maxfpgrowth"] else None,
                "k": k if algorithm == "topk" else None,
                "patterns": [],
                "note": f"no terms survived {filtering_method} filtering",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        kept_vocab = [local_vocab[i] for i in kept_indices]
        filtered_dtm = dense_local[:, kept_indices]

        # Convert survived terms to a transactional database file
        transactions = []
        for row in filtered_dtm:
            items = [kept_vocab[j] for j, count in enumerate(row) if count >= 1]
            if items:
                transactions.append("\t".join(items))

        if not transactions:
            summary = {
                "result_id": result_id,
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "patterns": [],
                "note": "no non-empty transactions generated from filtered terms",
            }
            session.artifacts[artifact_key] = []
            session.store_result("mine_patterns_tool", {"category_name": category_name}, summary)
            return summary

        # 4. Pattern mining execution
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, suffix=".txt") as tmp:
            tmp_path = tmp.name
            for line in transactions:
                tmp.write(line + "\n")

        patterns = []
        note = "success"

        try:
            algo_lower = algorithm.lower()
            if algo_lower == "fpgrowth":
                from PAMI.frequentPattern.basic import FPGrowth
                miner = FPGrowth.FPGrowth(tmp_path, minSup=min_sup, sep="\t")
                miner.startMine()
                df_patterns = miner.getPatternsAsDataFrame()

            elif algo_lower == "topk":
                from PAMI.frequentPattern.topk import FAE
                miner = FAE.FAE(tmp_path, k=k, sep="\t")
                miner.startMine()
                df_patterns = miner.getPatternsAsDataFrame()

            elif algo_lower == "maxfpgrowth":
                from PAMI.frequentPattern.maximal import MaxFPGrowth
                miner = MaxFPGrowth.MaxFPGrowth(tmp_path, minSup=min_sup, sep="\t")
                miner.startMine()
                df_patterns = miner.getPatternsAsDataFrame()

            else:
                raise ValueError(f"Unknown mining algorithm: '{algorithm}'")

            if df_patterns is not None and not df_patterns.empty:
                p_col = df_patterns.columns[0]
                s_col = df_patterns.columns[1] if len(df_patterns.columns) > 1 else df_patterns.columns[0]

                for _, p_row in df_patterns.iterrows():
                    pat_str = str(p_row[p_col])
                    sup_val = int(p_row[s_col]) if s_col != p_col else 0
                    patterns.append({
                        "pattern": pat_str,
                        "support": sup_val,
                    })

            if not patterns:
                note = f"zero patterns returned by {algorithm} at threshold (min_sup={min_sup}, k={k})"

        except Exception as e:
            note = f"mining executed with note/warning: {str(e)}"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        summary = {
            "result_id": result_id,
            "category_name": category_name,
            "filtering_method": filtering_method,
            "algorithm": algorithm,
            "min_sup": min_sup if algorithm in ["fpgrowth", "maxfpgrowth"] else None,
            "k": k if algorithm == "topk" else None,
            "patterns": patterns,
            "note": note,
        }

        # Store artifacts per contract key f"patterns_{category_name}_{filtering_method}_{algorithm}"
        session.artifacts[artifact_key] = patterns

        session.store_result(
            "mine_patterns_tool",
            {
                "category_name": category_name,
                "filtering_method": filtering_method,
                "algorithm": algorithm,
                "min_sup": min_sup,
                "k": k,
            },
            summary,
        )
        return summary

    return [mine_patterns_tool]
