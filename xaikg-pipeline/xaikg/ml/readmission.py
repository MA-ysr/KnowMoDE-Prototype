"""Readmission model: preprocessing of the UCI 296 table, HistGradientBoosting classifier, SHAP.

Features are exactly `AIModelSpec.featureNames` of the decision-bindings model (read from the model
file, so the predictor and the explanation contract cannot drift apart: C5_ModelHasFeatures,
C5_BindingFeatureExistsInModel). The target is readmitted == '<30'.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

from ..config import PATHS
from ..manifest import now_iso

MODEL_DIR = PATHS.results / "model"
CATEGORICAL = {"age", "max_glu_serum", "A1Cresult", "diag_1", "diag_2", "diag_3", "change", "diabetesMed",
               "metformin", "repaglinide", "nateglinide", "chlorpropamide", "glimepiride", "glipizide", "glyburide",
               "pioglitazone", "rosiglitazone", "acarbose", "miglitol", "insulin", "glyburide-metformin", "glipizide-metformin",
               "admission_type_id", "discharge_disposition_id", "admission_source_id"}


def model_spec() -> dict:
    root = etree.parse(str(PATHS.models / "decision-bindings.xmi")).getroot()
    ai = root.find("aiModel")
    return {"name": ai.get("name"), "version": ai.get("version"), "attributionMethod": ai.get("attributionMethod", "SHAP"),
            "features": ai.get("featureNames").split()}


ICD9_GROUPS = {"circulatory", "respiratory", "digestive", "diabetes", "injury", "musculoskeletal", "genitourinary",
               "neoplasms", "other", "missing"}
DIAGNOSES = ("diag_1", "diag_2", "diag_3")


def icd9_group(code: str) -> str:
    """Coarse ICD-9 grouping used ONLY inside the predictor (Strack et al. 2014): the decision context
    carries the raw codes, which the KG bindings resolve with the finer valueMap of the decision-bindings
    model. Idempotent on group names."""
    if code in (None, "?", "") or pd.isna(code):
        return "missing"
    if code in ICD9_GROUPS:
        return code
    if code.startswith(("V", "E")):
        return "other"
    try:
        n = float(code)
    except ValueError:
        return "other"
    if 390 <= n <= 459 or int(n) == 785:
        return "circulatory"
    if 460 <= n <= 519 or int(n) == 786:
        return "respiratory"
    if 520 <= n <= 579 or int(n) == 787:
        return "digestive"
    if int(n) == 250:
        return "diabetes"
    if 800 <= n <= 999:
        return "injury"
    if 710 <= n <= 739:
        return "musculoskeletal"
    if 580 <= n <= 629 or int(n) == 788:
        return "genitourinary"
    if 140 <= n <= 239:
        return "neoplasms"
    return "other"


def load_table() -> pd.DataFrame:
    df = pd.read_csv(PATHS.tabular / "diabetic_data.csv", na_values=["?"], low_memory=False)
    # one row per patient (first encounter), as in Strack et al.; drop encounters ending in death/hospice
    df = df.sort_values("encounter_id").drop_duplicates("patient_nbr", keep="first")
    df = df[~df["discharge_disposition_id"].isin([11, 13, 14, 19, 20, 21])]
    return df.reset_index(drop=True)


def encounter_values(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Readable feature values of the encounters, as an information system provides them: the decision
    context that the bindings model and the explanations see (diagnoses as raw ICD-9 codes)."""
    X = df[features].copy()
    for c in features:
        if c in CATEGORICAL:
            X[c] = X[c].astype(str).replace({"nan": "missing", "None": "missing"})
        else:
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)
    return X


def model_values(X: pd.DataFrame) -> pd.DataFrame:
    """The predictor's own feature engineering on a decision context: diagnoses grouped into ICD-9 chapters."""
    X = X.copy()
    for c in DIAGNOSES:
        if c in X:
            X[c] = X[c].map(icd9_group)
    return X


def raw_values(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Model-side readable values (diagnoses grouped), used for training."""
    return model_values(encounter_values(df, features))


def encode(X: pd.DataFrame, categories: dict[str, list[str]]) -> pd.DataFrame:
    """Integer-code the categorical columns with fixed category lists (unknown -> -1 -> 'missing')."""
    E = X.copy()
    for c, cats in categories.items():
        idx = {v: i for i, v in enumerate(cats)}
        E[c] = E[c].astype(str).map(lambda v: idx.get(v, idx.get("missing", 0))).astype(int)
    return E


@dataclass
class Trained:
    model: object
    features: list[str]
    categories: dict[str, list[str]]
    metrics: dict


def train(seed: int = 42) -> Trained:
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import average_precision_score, roc_auc_score
    from sklearn.model_selection import train_test_split

    spec = model_spec()
    df = load_table()
    Xraw = raw_values(df, spec["features"])
    y = (df["readmitted"] == "<30").astype(int).to_numpy()
    cats = {c: sorted(set(Xraw[c].astype(str)) | {"missing"}) for c in spec["features"] if c in CATEGORICAL}
    X = encode(Xraw, cats)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=seed, stratify=y)
    # Categorical columns are integer-coded and treated as ordinal splits on purpose: SHAP's TreeExplainer
    # does not model HistGradientBoosting's native categorical (bitset) splits and silently returns
    # non-additive attributions for them. Attributor.verify_additivity() guards this invariant.
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                         class_weight="balanced", random_state=seed)
    clf.fit(Xtr, ytr)
    proba = clf.predict_proba(Xte)[:, 1]
    # persist the decision contexts (raw codes); model_values() and encode() are applied at prediction time
    Xte = encounter_values(df, spec["features"]).loc[Xte.index]
    metrics = {"auroc": round(float(roc_auc_score(yte, proba)), 4), "auprc": round(float(average_precision_score(yte, proba)), 4),
               "positiveRate": round(float(y.mean()), 4), "train": int(len(Xtr)), "test": int(len(Xte)), "patients": int(len(df))}
    trained = Trained(clf, spec["features"], cats, metrics)
    save(trained, spec, Xte, yte, proba, seed)
    return trained


def save(t: Trained, spec: dict, Xte: pd.DataFrame, yte, proba, seed: int) -> None:
    import joblib
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": t.model, "features": t.features, "categories": t.categories}, MODEL_DIR / "readmission.joblib")
    test = Xte.copy()
    test["y_true"] = yte
    test["p_readmit"] = proba
    test.to_parquet(MODEL_DIR / "test-set.parquet") if _has_pyarrow() else test.to_csv(MODEL_DIR / "test-set.csv", index=False)
    (MODEL_DIR / "model-card.json").write_text(json.dumps({
        "name": spec["name"], "version": spec["version"], "attributionMethod": spec["attributionMethod"],
        "algorithm": "HistGradientBoostingClassifier (scikit-learn), class_weight=balanced", "seed": seed,
        "target": "readmitted == '<30'", "features": t.features, "metrics": t.metrics, "trainedAt": now_iso(),
        "trainingDataset": "UCI 296 Diabetes 130-US hospitals 1999-2008, first encounter per patient, deaths/hospice excluded"},
        indent=2) + "\n", encoding="utf-8")


def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
        return True
    except ImportError:
        return False


def load_trained() -> Trained:
    import joblib
    bundle = joblib.load(MODEL_DIR / "readmission.joblib")
    card = json.loads((MODEL_DIR / "model-card.json").read_text(encoding="utf-8"))
    return Trained(bundle["model"], bundle["features"], bundle["categories"], card["metrics"])


def load_test_set() -> pd.DataFrame:
    p = MODEL_DIR / "test-set.parquet"
    return pd.read_parquet(p) if p.exists() else pd.read_csv(MODEL_DIR / "test-set.csv")


class Attributor:
    """SHAP TreeExplainer over the trained model; returns per-feature attributions for one encounter."""

    def __init__(self, trained: Trained, verify: bool = True):
        import shap
        self.t = trained
        self.explainer = shap.TreeExplainer(trained.model)
        if verify:
            self.verify_additivity()

    def verify_additivity(self, n: int = 200, tol: float = 1e-3) -> float:
        """Faithfulness guard: expected_value + sum(SHAP) must equal the model's raw (log-odds) output.
        Raises if the attribution method does not match the model (e.g. unsupported split types)."""
        test = load_test_set().head(n)
        X = encode(model_values(test[self.t.features]), self.t.categories)
        sv = np.asarray(self.explainer.shap_values(X))
        sv = sv[-1] if sv.ndim == 3 else sv
        ev = self.explainer.expected_value
        ev = ev[-1] if np.ndim(ev) else ev
        err = float(np.max(np.abs(ev + sv.sum(axis=1) - self.t.model.decision_function(X))))
        if err > tol:
            raise RuntimeError(f"SHAP attributions are not additive for this model (max error {err:.4f} log-odds)")
        return err

    def _frame(self, row: dict) -> pd.DataFrame:
        X = pd.DataFrame([{f: row.get(f) for f in self.t.features}])
        for c in self.t.features:
            if c not in self.t.categories:
                X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)
        return encode(model_values(X), self.t.categories)

    def explain(self, row: dict) -> dict:
        X = self._frame(row)
        proba = float(self.t.model.predict_proba(X)[0, 1])
        sv = self.explainer.shap_values(X)
        values = np.asarray(sv)[0] if np.asarray(sv).ndim == 2 else np.asarray(sv)[-1][0]
        attributions = [{"feature": f, "value": row.get(f), "attribution": float(v)} for f, v in zip(self.t.features, values)]
        attributions.sort(key=lambda a: -abs(a["attribution"]))
        return {"probability": proba, "attributions": attributions}
