from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from reksa_ai.artifacts import new_bundle, save_artifact
from reksa_ai.baselines import ForecastRuleBaseline, PriorityRuleBaseline
from reksa_ai.contracts import PriorityEvent, TemporalFeatures
from reksa_ai.features import (
    FORECAST_CATEGORICAL_FEATURES,
    FORECAST_FEATURES,
    FORECAST_NUMERIC_FEATURES,
    PRIORITY_CATEGORICAL_FEATURES,
    PRIORITY_FEATURES,
    PRIORITY_NUMERIC_FEATURES,
)

EngineKind = Literal["near_miss_forecaster", "priority_engine"]


@dataclass(frozen=True)
class TrainingResult:
    artifact_path: Path
    selected_model: str
    metrics: dict[str, Any]
    train_rows: int
    test_rows: int
    train_groups: int
    test_groups: int
    probability_is_calibrated: bool
    deployment_recommended: bool


def _imports() -> dict[str, Any]:
    try:
        from sklearn.base import clone
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            accuracy_score,
            brier_score_loss,
            confusion_matrix,
            f1_score,
            precision_score,
            recall_score,
            roc_auc_score,
        )
        from sklearn.model_selection import GroupKFold, GroupShuffleSplit
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("scikit-learn is required for model training") from exc
    return {
        "clone": clone,
        "CalibratedClassifierCV": CalibratedClassifierCV,
        "ColumnTransformer": ColumnTransformer,
        "RandomForestClassifier": RandomForestClassifier,
        "SimpleImputer": SimpleImputer,
        "LogisticRegression": LogisticRegression,
        "accuracy_score": accuracy_score,
        "brier_score_loss": brier_score_loss,
        "confusion_matrix": confusion_matrix,
        "f1_score": f1_score,
        "precision_score": precision_score,
        "recall_score": recall_score,
        "roc_auc_score": roc_auc_score,
        "GroupKFold": GroupKFold,
        "GroupShuffleSplit": GroupShuffleSplit,
        "Pipeline": Pipeline,
        "OneHotEncoder": OneHotEncoder,
        "StandardScaler": StandardScaler,
    }


def _validate_columns(frame: pd.DataFrame, required: list[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"dataset is missing columns: {', '.join(missing)}")


def _group_ids(frame: pd.DataFrame, group_columns: list[str]) -> pd.Series:
    _validate_columns(frame, group_columns)
    values = frame[group_columns].fillna("UNKNOWN").astype(str)
    return values.agg("::".join, axis=1)


def _split_indices(frame: pd.DataFrame, groups: pd.Series, test_size: float, seed: int) -> tuple[Any, Any]:
    sk = _imports()
    if groups.nunique() < 2:
        raise ValueError("at least two participant/session groups are required")
    splitter = sk["GroupShuffleSplit"](n_splits=1, test_size=test_size, random_state=seed)
    train_index, test_index = next(splitter.split(frame, groups=groups))
    return train_index, test_index


def _preprocessor(numeric: list[str], categorical: list[str]) -> Any:
    sk = _imports()
    numeric_pipeline = sk["Pipeline"](
        [
            ("imputer", sk["SimpleImputer"](strategy="median", add_indicator=True)),
            ("scaler", sk["StandardScaler"]()),
        ]
    )
    categorical_pipeline = sk["Pipeline"](
        [
            ("imputer", sk["SimpleImputer"](strategy="most_frequent")),
            ("encoder", sk["OneHotEncoder"](handle_unknown="ignore")),
        ]
    )
    return sk["ColumnTransformer"](
        [
            ("numeric", numeric_pipeline, numeric),
            ("categorical", categorical_pipeline, categorical),
        ]
    )


def _candidates(numeric: list[str], categorical: list[str], seed: int) -> dict[str, Any]:
    sk = _imports()
    return {
        "logistic_regression": sk["Pipeline"](
            [
                ("preprocess", _preprocessor(numeric, categorical)),
                (
                    "classifier",
                    sk["LogisticRegression"](
                        max_iter=3000, class_weight="balanced", random_state=seed
                    ),
                ),
            ]
        ),
        "random_forest": sk["Pipeline"](
            [
                ("preprocess", _preprocessor(numeric, categorical)),
                (
                    "classifier",
                    sk["RandomForestClassifier"](
                        n_estimators=400,
                        min_samples_leaf=3,
                        class_weight="balanced_subsample",
                        random_state=seed,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
    }


def _binary_metrics(estimator: Any, features: pd.DataFrame, target: pd.Series) -> dict[str, Any]:
    prediction = estimator.predict(features)
    probabilities = estimator.predict_proba(features)
    classes = [str(value) for value in estimator.classes_]
    positive_probability = probabilities[:, classes.index("1")]
    return _binary_metrics_from_values(target, prediction, positive_probability)


def _binary_metrics_from_values(
    target: pd.Series, prediction: Any, positive_probability: Any
) -> dict[str, Any]:
    sk = _imports()
    result = {
        "precision": float(sk["precision_score"](target, prediction, zero_division=0)),
        "recall": float(sk["recall_score"](target, prediction, zero_division=0)),
        "f1": float(sk["f1_score"](target, prediction, zero_division=0)),
        "brier_score": float(sk["brier_score_loss"](target, positive_probability)),
        "confusion_matrix": sk["confusion_matrix"](target, prediction, labels=[0, 1]).tolist(),
    }
    if target.nunique() == 2:
        result["roc_auc"] = float(sk["roc_auc_score"](target, positive_probability))
    return result


def _multiclass_metrics(estimator: Any, features: pd.DataFrame, target: pd.Series) -> dict[str, Any]:
    prediction = estimator.predict(features)
    return _multiclass_metrics_from_values(target, prediction)


def _multiclass_metrics_from_values(target: pd.Series, prediction: Any) -> dict[str, Any]:
    sk = _imports()
    labels = ["LOW", "MEDIUM", "HIGH"]
    return {
        "accuracy": float(sk["accuracy_score"](target, prediction)),
        "precision_macro": float(
            sk["precision_score"](target, prediction, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            sk["recall_score"](target, prediction, average="macro", zero_division=0)
        ),
        "f1_macro": float(sk["f1_score"](target, prediction, average="macro", zero_division=0)),
        "confusion_matrix": sk["confusion_matrix"](target, prediction, labels=labels).tolist(),
        "confusion_matrix_labels": labels,
    }


def _calibrate_with_groups(estimator: Any, features: pd.DataFrame, target: pd.Series, groups: pd.Series) -> tuple[Any, bool]:
    sk = _imports()
    split_count = min(5, int(groups.nunique()))
    if split_count < 3:
        estimator.fit(features, target)
        return estimator, False
    splitter = sk["GroupKFold"](n_splits=split_count)
    splits = list(splitter.split(features, target, groups))
    for train_index, validation_index in splits:
        if target.iloc[train_index].nunique() < 2 or target.iloc[validation_index].nunique() < 2:
            estimator.fit(features, target)
            return estimator, False
    calibrated = sk["CalibratedClassifierCV"](
        estimator=sk["clone"](estimator), method="sigmoid", cv=splits
    )
    calibrated.fit(features, target)
    return calibrated, True


def train_engine(
    dataset_path: Path,
    output_path: Path,
    *,
    kind: EngineKind,
    model_version: str,
    group_columns: list[str] | None = None,
    test_size: float = 0.25,
    seed: int = 42,
) -> TrainingResult:
    frame = pd.read_csv(dataset_path)
    groups_used = group_columns or ["participant_id", "session_id"]

    if kind == "near_miss_forecaster":
        features = FORECAST_FEATURES
        numeric = FORECAST_NUMERIC_FEATURES
        categorical = FORECAST_CATEGORICAL_FEATURES
        target_name = "escalated_within_horizon"
        _validate_columns(frame, features + [target_name])
        frame = frame.dropna(subset=[target_name]).copy()
        frame[target_name] = frame[target_name].astype(int)
        if set(frame[target_name].unique()) != {0, 1}:
            raise ValueError("forecaster target must contain both 0 and 1")
        score_key = "f1"
    else:
        features = PRIORITY_FEATURES
        numeric = PRIORITY_NUMERIC_FEATURES
        categorical = PRIORITY_CATEGORICAL_FEATURES
        target_name = "supervisor_priority"
        _validate_columns(frame, features + [target_name])
        frame = frame.dropna(subset=[target_name]).copy()
        frame[target_name] = frame[target_name].astype(str).str.upper()
        invalid = sorted(set(frame[target_name]) - {"LOW", "MEDIUM", "HIGH"})
        if invalid:
            raise ValueError(f"invalid supervisor priority labels: {', '.join(invalid)}")
        if frame[target_name].nunique() < 2:
            raise ValueError("priority dataset must contain at least two classes")
        score_key = "f1_macro"

    if len(frame) < 20:
        raise ValueError("at least 20 labeled rows are required before training")
    groups = _group_ids(frame, groups_used)
    train_index, test_index = _split_indices(frame, groups, test_size, seed)
    train = frame.iloc[train_index]
    test = frame.iloc[test_index]
    train_groups = groups.iloc[train_index]
    test_groups = groups.iloc[test_index]
    if set(train_groups) & set(test_groups):
        raise AssertionError("group leakage detected between train and test")
    if train[target_name].nunique() < 2 or test[target_name].nunique() < 2:
        raise ValueError(
            "group split produced a single-class partition; collect more sessions per label"
        )

    candidate_metrics: dict[str, dict[str, Any]] = {}
    for name, estimator in _candidates(numeric, categorical, seed).items():
        estimator.fit(train[features], train[target_name])
        metrics = (
            _binary_metrics(estimator, test[features], test[target_name])
            if kind == "near_miss_forecaster"
            else _multiclass_metrics(estimator, test[features], test[target_name])
        )
        candidate_metrics[name] = metrics

    selected_name = max(candidate_metrics, key=lambda name: candidate_metrics[name][score_key])
    if kind == "near_miss_forecaster":
        baseline = ForecastRuleBaseline()
        baseline_scores = [
            baseline.score(TemporalFeatures.model_validate(row)).score
            for row in test[features].to_dict(orient="records")
        ]
        candidate_metrics["rule_based_baseline"] = _binary_metrics_from_values(
            test[target_name],
            [int(score >= 0.5) for score in baseline_scores],
            baseline_scores,
        )
    else:
        baseline = PriorityRuleBaseline()
        baseline_predictions = []
        contract_columns = list(PriorityEvent.model_fields)
        contract_frame = test[contract_columns].astype(object).where(
            pd.notna(test[contract_columns]), None
        )
        for row in contract_frame.to_dict(orient="records"):
            event = PriorityEvent.model_validate(row)
            baseline_predictions.append(baseline.priority(baseline.score(event).score).value)
        candidate_metrics["rule_based_baseline"] = _multiclass_metrics_from_values(
            test[target_name], baseline_predictions
        )
    selected_template = _candidates(numeric, categorical, seed)[selected_name]
    calibrated = False
    if kind == "near_miss_forecaster":
        validation_estimator, calibrated = _calibrate_with_groups(
            selected_template, train[features], train[target_name], train_groups.reset_index(drop=True)
        )
        selected_metrics = _binary_metrics(
            validation_estimator, test[features], test[target_name]
        )
        final_estimator, final_calibrated = _calibrate_with_groups(
            selected_template, frame[features], frame[target_name], groups.reset_index(drop=True)
        )
        calibrated = calibrated and final_calibrated
    else:
        selected_metrics = candidate_metrics[selected_name]
        final_estimator = selected_template.fit(frame[features], frame[target_name])

    deployment_recommended = (
        selected_metrics[score_key]
        > candidate_metrics["rule_based_baseline"][score_key]
    )

    metrics = {
        "selected_test_metrics": selected_metrics,
        "candidate_test_metrics": candidate_metrics,
        "deployment_recommended": deployment_recommended,
        "deployment_gate": (
            f"selected {score_key} must be greater than rule-based baseline {score_key}"
        ),
        "split_policy": {
            "group_columns": groups_used,
            "test_size": test_size,
            "random_seed": seed,
            "train_groups": int(train_groups.nunique()),
            "test_groups": int(test_groups.nunique()),
        },
        "warning": "Metrics are valid only for the recorded participants, sessions, and scenarios.",
    }
    bundle = new_bundle(
        kind=kind,
        estimator=final_estimator,
        model_version=model_version,
        features=features,
        metrics=metrics,
        probability_is_calibrated=calibrated,
        classes=[str(value) for value in final_estimator.classes_],
        dataset_rows=len(frame),
        deployment_recommended=deployment_recommended,
    )
    save_artifact(bundle, output_path)
    return TrainingResult(
        artifact_path=output_path,
        selected_model=selected_name,
        metrics=metrics,
        train_rows=len(train),
        test_rows=len(test),
        train_groups=int(train_groups.nunique()),
        test_groups=int(test_groups.nunique()),
        probability_is_calibrated=calibrated,
        deployment_recommended=deployment_recommended,
    )
