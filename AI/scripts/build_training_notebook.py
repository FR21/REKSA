#!/usr/bin/env python3
"""Build the complete Colab/local training notebook for both REKSA AI engines."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any


def source(value: str) -> list[str]:
    text = textwrap.dedent(value).strip("\n") + "\n"
    return text.splitlines(keepends=True)


def markdown(value: str) -> dict[str, Any]:
    return {"cell_type": "markdown", "metadata": {}, "source": source(value)}


def code(value: str) -> dict[str, Any]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source(value),
    }


cells = [
    markdown(
        """
        # REKSA AI - Complete Training Notebook

        Notebook ini melatih dua model:

        1. **Near-Miss Risk Forecaster**: memprediksi probabilitas eskalasi dari satu window temporal BLE-RSSI + MPU6050.
        2. **AI Priority Engine**: mengurutkan candidate safety event menjadi prioritas LOW, MEDIUM, atau HIGH.

        Seluruh proses ditampilkan: setup, import, loading, cleaning, audit leakage, feature engineering contract, participant holdout, group cross-validation, rule baseline, Logistic Regression, Random Forest, calibration, evaluasi, explanation, artifact export, dan inference.

        > Dataset yang digunakan bersifat **SYNTHETIC**. Hasil notebook hanya valid untuk pengembangan pipeline, bukan klaim performa keselamatan dunia nyata. AI tetap advisory dan tidak memverifikasi near-miss atau mengendalikan alarm lokal.
        """
    ),
    markdown(
        """
        ## 1. Environment setup

        Cell berikut memasang library hanya jika belum tersedia. Di Google Colab, upload/clone folder `AI` beserta `data/synthetic` sebelum menjalankan notebook.
        """
    ),
    code(
        """
        import importlib.util
        import subprocess
        import sys

        REQUIRED_PACKAGES = {
            "numpy": "numpy>=2.0,<3.0",
            "pandas": "pandas>=2.2,<4.0",
            "sklearn": "scikit-learn>=1.7,<2.0",
            "joblib": "joblib>=1.5,<2.0",
            "matplotlib": "matplotlib>=3.8,<4.0",
            "seaborn": "seaborn>=0.13,<1.0",
            "IPython": "ipython>=8.0",
        }
        missing = [package for module, package in REQUIRED_PACKAGES.items() if importlib.util.find_spec(module) is None]
        if missing:
            print("Installing:", missing)
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *missing])
        else:
            print("All training dependencies are available.")
        """
    ),
    code(
        """
        import json
        import platform
        import random
        from datetime import UTC, datetime
        from pathlib import Path

        import joblib
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import seaborn as sns
        import sklearn
        from IPython.display import display
        from sklearn.base import clone
        from sklearn.calibration import CalibratedClassifierCV, calibration_curve
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.impute import SimpleImputer
        from sklearn.inspection import permutation_importance
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import (
            ConfusionMatrixDisplay,
            accuracy_score,
            average_precision_score,
            brier_score_loss,
            classification_report,
            confusion_matrix,
            f1_score,
            precision_recall_curve,
            precision_score,
            recall_score,
            roc_auc_score,
            roc_curve,
        )
        from sklearn.model_selection import (
            GroupShuffleSplit,
            StratifiedGroupKFold,
            cross_validate,
        )
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        SEED = 20260807
        random.seed(SEED)
        np.random.seed(SEED)
        sns.set_theme(style="whitegrid", context="notebook")
        pd.set_option("display.max_columns", 100)

        print("Python:", platform.python_version())
        print("pandas:", pd.__version__)
        print("scikit-learn:", sklearn.__version__)
        """
    ),
    markdown("## 2. Locate project and load both datasets"),
    code(
        """
        CANDIDATE_ROOTS = [
            Path.cwd(),
            Path.cwd() / "AI",
            Path("/content/REKSA/AI"),
            Path("/content/AI"),
        ]
        AI_ROOT = next(
            (path.resolve() for path in CANDIDATE_ROOTS if (path / "data/synthetic").exists()),
            None,
        )
        if AI_ROOT is None:
            raise FileNotFoundError(
                "Folder AI/data/synthetic tidak ditemukan. Atur AI_ROOT secara manual ke folder AI."
            )

        FORECAST_CSV = AI_ROOT / "data/synthetic/forecasting_windows_synthetic.csv"
        PRIORITY_CSV = AI_ROOT / "data/synthetic/event_dataset_synthetic.csv"
        OUTPUT_DIR = AI_ROOT / "models/notebook"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        forecast_raw = pd.read_csv(FORECAST_CSV)
        priority_raw = pd.read_csv(PRIORITY_CSV)
        print("AI_ROOT:", AI_ROOT)
        print("Forecast raw shape:", forecast_raw.shape)
        print("Priority raw shape:", priority_raw.shape)
        """
    ),
    code(
        """
        display(forecast_raw.head(3))
        display(priority_raw.head(3))
        print("Forecast dtypes:\\n", forecast_raw.dtypes.value_counts())
        print("Priority dtypes:\\n", priority_raw.dtypes.value_counts())
        """
    ),
    markdown(
        """
        ## 3. Explicit feature contracts and leakage guard

        Dataset sudah berada pada level model: satu baris forecaster adalah satu temporal window, sedangkan satu baris Priority Engine adalah satu event. Kolom seperti `scenario_id`, ID, waktu, dan label verification hanya metadata. Kolom tersebut sengaja tidak masuk model karena dapat membocorkan jawaban atau membuat model menghafal peserta/skenario.
        """
    ),
    code(
        """
        FORECAST_NUMERIC = [
            "window_duration_seconds", "sample_count", "rssi_mean", "rssi_peak", "rssi_min",
            "rssi_std", "rssi_slope", "warning_duration_seconds", "danger_duration_seconds",
            "state_transition_count", "packet_loss_ratio", "acceleration_mean_g",
            "acceleration_max_g", "acceleration_energy", "gyroscope_mean_dps",
            "gyroscope_max_dps", "gyroscope_energy", "orientation_change_deg",
            "sudden_motion", "hazard_active", "repeated_exposure_count",
        ]
        FORECAST_CATEGORICAL = ["hazard_type"]
        FORECAST_FEATURES = FORECAST_NUMERIC + FORECAST_CATEGORICAL
        FORECAST_TARGET = "escalated_within_horizon"

        PRIORITY_NUMERIC = [
            "event_duration_seconds", "rssi_mean", "rssi_peak", "rssi_min", "rssi_std",
            "rssi_slope", "warning_duration_seconds", "danger_duration_seconds",
            "state_transition_count", "packet_loss_count", "acceleration_max_g",
            "gyroscope_max_dps", "orientation_change_deg", "sudden_motion",
            "candidate_impact", "candidate_fall", "post_event_stillness_seconds",
            "temperature_c", "humidity_percent", "mq135_deviation", "hazard_active",
            "local_warning_success", "repeated_exposure_count", "similar_event_count",
        ]
        PRIORITY_CATEGORICAL = ["hazard_type", "alarm_level", "connectivity_status"]
        PRIORITY_FEATURES = PRIORITY_NUMERIC + PRIORITY_CATEGORICAL
        PRIORITY_TARGET = "supervisor_priority"

        FORBIDDEN_FEATURES = {
            "participant_id", "session_id", "recording_date", "scenario_id", "trajectory_id",
            "window_id", "event_id", "worker_id", "helmet_id", "hazard_id", "occurred_at",
            "window_started_at", "window_ended_at", "target_source", "verification_label",
            "label_source", "data_origin", FORECAST_TARGET, PRIORITY_TARGET,
        }
        assert not set(FORECAST_FEATURES) & FORBIDDEN_FEATURES
        assert not set(PRIORITY_FEATURES) & FORBIDDEN_FEATURES
        print("Forecast features:", len(FORECAST_FEATURES))
        print("Priority features:", len(PRIORITY_FEATURES))
        print("Leakage guard: PASS")
        """
    ),
    markdown("## 4. Data cleaning and physical consistency audit"),
    code(
        """
        TRUE_VALUES = {"true", "1", "yes", "y"}
        FALSE_VALUES = {"false", "0", "no", "n"}

        def normalize_boolean(series: pd.Series) -> pd.Series:
            if pd.api.types.is_bool_dtype(series):
                return series.astype(int)
            lowered = series.astype(str).str.strip().str.lower()
            unknown = set(lowered.dropna().unique()) - TRUE_VALUES - FALSE_VALUES
            if unknown:
                raise ValueError(f"Unknown boolean values in {series.name}: {sorted(unknown)}")
            return lowered.map(lambda value: 1 if value in TRUE_VALUES else 0)

        def require_columns(frame: pd.DataFrame, columns: list[str], dataset_name: str) -> None:
            missing = sorted(set(columns) - set(frame.columns))
            if missing:
                raise ValueError(f"{dataset_name} missing columns: {missing}")

        def clean_forecast(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
            required = FORECAST_FEATURES + [FORECAST_TARGET, "window_id", "participant_id", "scenario_id"]
            require_columns(frame, required, "forecast")
            result = frame.copy()
            before = len(result)
            result = result.drop_duplicates(subset=["window_id"]).copy()
            for column in FORECAST_NUMERIC:
                if column in {"sudden_motion", "hazard_active"}:
                    result[column] = normalize_boolean(result[column])
                else:
                    result[column] = pd.to_numeric(result[column], errors="coerce")
            result[FORECAST_TARGET] = pd.to_numeric(result[FORECAST_TARGET], errors="coerce")
            result["hazard_type"] = result["hazard_type"].astype(str).str.strip().str.upper()
            result["window_started_at"] = pd.to_datetime(result["window_started_at"], utc=True, errors="coerce")
            physical_mask = (
                (result["rssi_min"] <= result["rssi_mean"])
                & (result["rssi_mean"] <= result["rssi_peak"])
                & (result["warning_duration_seconds"] + result["danger_duration_seconds"] <= result["window_duration_seconds"] + 1e-3)
            )
            invalid_physics = int((~physical_mask).sum())
            result = result.loc[physical_mask & result[FORECAST_TARGET].isin([0, 1])].reset_index(drop=True)
            report = {"before": before, "after": len(result), "duplicates_removed": before - frame.drop_duplicates("window_id").shape[0], "invalid_physics_removed": invalid_physics}
            return result, report

        def clean_priority(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
            required = PRIORITY_FEATURES + [PRIORITY_TARGET, "event_id", "participant_id", "scenario_id"]
            require_columns(frame, required, "priority")
            result = frame.copy()
            before = len(result)
            result = result.drop_duplicates(subset=["event_id"]).copy()
            boolean_columns = {"sudden_motion", "candidate_impact", "candidate_fall", "hazard_active", "local_warning_success"}
            for column in PRIORITY_NUMERIC:
                result[column] = normalize_boolean(result[column]) if column in boolean_columns else pd.to_numeric(result[column], errors="coerce")
            for column in PRIORITY_CATEGORICAL + [PRIORITY_TARGET]:
                result[column] = result[column].astype(str).str.strip().str.upper()
            result["occurred_at"] = pd.to_datetime(result["occurred_at"], utc=True, errors="coerce")
            physical_mask = (
                (result["rssi_min"] <= result["rssi_mean"])
                & (result["rssi_mean"] <= result["rssi_peak"])
                & (result["warning_duration_seconds"] + result["danger_duration_seconds"] <= result["event_duration_seconds"] + 1e-3)
            )
            valid_labels = {"LOW", "MEDIUM", "HIGH"}
            invalid_physics = int((~physical_mask).sum())
            result = result.loc[physical_mask & result[PRIORITY_TARGET].isin(valid_labels)].reset_index(drop=True)
            report = {"before": before, "after": len(result), "duplicates_removed": before - frame.drop_duplicates("event_id").shape[0], "invalid_physics_removed": invalid_physics}
            return result, report

        forecast_df, forecast_cleaning_report = clean_forecast(forecast_raw)
        priority_df, priority_cleaning_report = clean_priority(priority_raw)
        print("Forecast cleaning:", forecast_cleaning_report)
        print("Priority cleaning:", priority_cleaning_report)
        print("Forecast missing feature cells:", int(forecast_df[FORECAST_FEATURES].isna().sum().sum()))
        print("Priority missing feature cells:", int(priority_df[PRIORITY_FEATURES].isna().sum().sum()))
        """
    ),
    markdown(
        """
        Missing value tidak diisi pada seluruh dataset sebelum split. Imputation berada di dalam `Pipeline`, sehingga median/category hanya dipelajari dari training fold. Ini mencegah informasi test masuk ke preprocessing.
        """
    ),
    code(
        """
        fig, axes = plt.subplots(1, 2, figsize=(13, 4))
        sns.countplot(data=forecast_df, x=FORECAST_TARGET, ax=axes[0], color="#3478bd")
        axes[0].set_title("Forecaster target distribution")
        order = ["LOW", "MEDIUM", "HIGH"]
        sns.countplot(data=priority_df, x=PRIORITY_TARGET, order=order, ax=axes[1], color="#d97706")
        axes[1].set_title("Priority target distribution")
        plt.tight_layout()
        plt.show()

        display(forecast_df.groupby("scenario_id")[FORECAST_TARGET].agg(["count", "mean"]).sort_values("mean", ascending=False))
        display(pd.crosstab(priority_df["scenario_id"], priority_df[PRIORITY_TARGET]).reindex(columns=order, fill_value=0))
        """
    ),
    markdown("## 5. Shared split, preprocessing, metrics, and artifact helpers"),
    code(
        """
        def participant_holdout(frame: pd.DataFrame, target: str, test_size: float = 0.25):
            groups = frame["participant_id"].astype(str)
            splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=SEED)
            train_index, test_index = next(splitter.split(frame, frame[target], groups))
            train = frame.iloc[train_index].reset_index(drop=True)
            test = frame.iloc[test_index].reset_index(drop=True)
            overlap = set(train["participant_id"]) & set(test["participant_id"])
            assert not overlap, f"Participant leakage: {overlap}"
            assert train[target].nunique() == frame[target].nunique()
            assert test[target].nunique() == frame[target].nunique()
            return train, test

        def make_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
            numeric_pipeline = Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
            ])
            categorical_pipeline = Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore")),
            ])
            return ColumnTransformer([
                ("numeric", numeric_pipeline, numeric),
                ("categorical", categorical_pipeline, categorical),
            ])

        def model_candidates(numeric: list[str], categorical: list[str]) -> dict[str, Pipeline]:
            return {
                "logistic_regression": Pipeline([
                    ("preprocess", make_preprocessor(numeric, categorical)),
                    ("classifier", LogisticRegression(max_iter=3000, class_weight="balanced", random_state=SEED)),
                ]),
                "random_forest": Pipeline([
                    ("preprocess", make_preprocessor(numeric, categorical)),
                    ("classifier", RandomForestClassifier(
                        n_estimators=300, min_samples_leaf=3, max_features="sqrt",
                        class_weight="balanced_subsample", random_state=SEED, n_jobs=-1,
                    )),
                ]),
            }

        def binary_metrics(y_true, probability, threshold: float = 0.5) -> dict:
            prediction = (np.asarray(probability) >= threshold).astype(int)
            return {
                "threshold": threshold,
                "precision": precision_score(y_true, prediction, zero_division=0),
                "recall": recall_score(y_true, prediction, zero_division=0),
                "f1": f1_score(y_true, prediction, zero_division=0),
                "roc_auc": roc_auc_score(y_true, probability),
                "average_precision": average_precision_score(y_true, probability),
                "brier_score": brier_score_loss(y_true, probability),
                "confusion_matrix": confusion_matrix(y_true, prediction, labels=[0, 1]).tolist(),
            }

        def multiclass_metrics(y_true, prediction) -> dict:
            labels = ["LOW", "MEDIUM", "HIGH"]
            return {
                "accuracy": accuracy_score(y_true, prediction),
                "precision_macro": precision_score(y_true, prediction, labels=labels, average="macro", zero_division=0),
                "recall_macro": recall_score(y_true, prediction, labels=labels, average="macro", zero_division=0),
                "f1_macro": f1_score(y_true, prediction, labels=labels, average="macro", zero_division=0),
                "confusion_matrix": confusion_matrix(y_true, prediction, labels=labels).tolist(),
                "labels": labels,
            }

        def json_default(value):
            if isinstance(value, (np.integer, np.floating, np.bool_)):
                return value.item()
            if isinstance(value, np.ndarray):
                return value.tolist()
            if isinstance(value, Path):
                return str(value)
            raise TypeError(f"Cannot serialize {type(value)}")

        def save_bundle(bundle: dict, path: Path) -> None:
            joblib.dump(bundle, path)
            metadata = {key: value for key, value in bundle.items() if key != "estimator"}
            path.with_suffix(".json").write_text(json.dumps(metadata, indent=2, default=json_default) + "\\n")
            print("Saved:", path)
            print("Saved:", path.with_suffix(".json"))
        """
    ),
    markdown("# Part A - Near-Miss Risk Forecaster"),
    markdown("## A1. Participant holdout and group cross-validation"),
    code(
        """
        forecast_train, forecast_test = participant_holdout(forecast_df, FORECAST_TARGET)
        Xf_train = forecast_train[FORECAST_FEATURES]
        yf_train = forecast_train[FORECAST_TARGET].astype(int)
        gf_train = forecast_train["participant_id"]
        Xf_test = forecast_test[FORECAST_FEATURES]
        yf_test = forecast_test[FORECAST_TARGET].astype(int)

        forecast_cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
        forecast_cv_splits = list(forecast_cv.split(Xf_train, yf_train, gf_train))
        print("Train rows / participants:", len(forecast_train), forecast_train.participant_id.nunique())
        print("Test rows / participants:", len(forecast_test), forecast_test.participant_id.nunique())
        print("Participant overlap:", set(forecast_train.participant_id) & set(forecast_test.participant_id))
        print("Train target rate:", yf_train.mean().round(4), "Test target rate:", yf_test.mean().round(4))
        """
    ),
    markdown("## A2. Rule-based cold-start baseline"),
    code(
        """
        def forecast_rule_score(frame: pd.DataFrame) -> np.ndarray:
            clamp = np.clip
            score = (
                0.03
                + 0.25 * clamp(frame["danger_duration_seconds"] / 5.0, 0, 1)
                + 0.18 * clamp((frame["rssi_peak"] + 90.0) / 40.0, 0, 1)
                + 0.14 * clamp(frame["rssi_slope"].clip(lower=0) / 6.0, 0, 1)
                + 0.13 * frame["sudden_motion"]
                + 0.08 * clamp((frame["acceleration_max_g"] - 1.0) / 3.0, 0, 1)
                + 0.09 * clamp(frame["repeated_exposure_count"] / 5.0, 0, 1)
                + 0.07 * frame["hazard_active"]
                + 0.03 * clamp(frame["packet_loss_ratio"] / 0.4, 0, 1)
            )
            return clamp(score.to_numpy(dtype=float), 0, 0.95)

        forecast_baseline_probability = forecast_rule_score(forecast_test)
        forecast_baseline_metrics = binary_metrics(yf_test, forecast_baseline_probability)
        display(pd.DataFrame([forecast_baseline_metrics]).drop(columns="confusion_matrix"))
        print("Baseline score is not a calibrated probability.")
        """
    ),
    markdown("## A3. Compare Logistic Regression and Random Forest using training CV only"),
    code(
        """
        forecast_models = model_candidates(FORECAST_NUMERIC, FORECAST_CATEGORICAL)
        forecast_cv_rows = []
        for name, estimator in forecast_models.items():
            scores = cross_validate(
                estimator, Xf_train, yf_train, cv=forecast_cv_splits,
                scoring={"precision": "precision", "recall": "recall", "f1": "f1", "roc_auc": "roc_auc"},
                n_jobs=-1, return_train_score=False,
            )
            forecast_cv_rows.append({
                "model": name,
                **{metric: scores[f"test_{metric}"].mean() for metric in ["precision", "recall", "f1", "roc_auc"]},
                "f1_std": scores["test_f1"].std(),
            })
        forecast_cv_table = pd.DataFrame(forecast_cv_rows).sort_values("f1", ascending=False).reset_index(drop=True)
        display(forecast_cv_table.style.format({column: "{:.4f}" for column in forecast_cv_table.columns if column != "model"}))
        FORECAST_SELECTED_NAME = str(forecast_cv_table.iloc[0]["model"])
        print("Selected from training CV:", FORECAST_SELECTED_NAME)
        """
    ),
    markdown("## A4. Probability calibration and untouched participant test"),
    code(
        """
        forecast_selected_template = forecast_models[FORECAST_SELECTED_NAME]
        forecast_uncalibrated = clone(forecast_selected_template).fit(Xf_train, yf_train)
        forecast_calibrated = CalibratedClassifierCV(
            estimator=clone(forecast_selected_template), method="sigmoid", cv=forecast_cv_splits
        ).fit(Xf_train, yf_train)

        forecast_test_probability = forecast_calibrated.predict_proba(Xf_test)[:, 1]
        forecast_test_prediction = (forecast_test_probability >= 0.5).astype(int)
        forecast_test_metrics = binary_metrics(yf_test, forecast_test_probability)
        display(pd.DataFrame([
            {"model": "rule_based_baseline", **forecast_baseline_metrics},
            {"model": f"{FORECAST_SELECTED_NAME}_calibrated", **forecast_test_metrics},
        ]).drop(columns="confusion_matrix").set_index("model"))
        print(classification_report(yf_test, forecast_test_prediction, target_names=["NO_ESCALATION", "ESCALATION"], zero_division=0))
        ConfusionMatrixDisplay.from_predictions(yf_test, forecast_test_prediction, display_labels=["NO", "YES"], cmap="Blues")
        plt.title("Forecaster - unseen participant holdout")
        plt.show()
        """
    ),
    code(
        """
        fpr, tpr, _ = roc_curve(yf_test, forecast_test_probability)
        precision_curve, recall_curve, _ = precision_recall_curve(yf_test, forecast_test_probability)
        observed, predicted = calibration_curve(yf_test, forecast_test_probability, n_bins=10, strategy="quantile")
        fig, axes = plt.subplots(1, 3, figsize=(16, 4))
        axes[0].plot(fpr, tpr, label=f"AUC={forecast_test_metrics['roc_auc']:.3f}")
        axes[0].plot([0, 1], [0, 1], "--", color="gray"); axes[0].set_title("ROC"); axes[0].legend()
        axes[1].plot(recall_curve, precision_curve, label=f"AP={forecast_test_metrics['average_precision']:.3f}")
        axes[1].set_title("Precision-Recall"); axes[1].legend()
        axes[2].plot(predicted, observed, marker="o"); axes[2].plot([0, 1], [0, 1], "--", color="gray")
        axes[2].set_title(f"Calibration (Brier={forecast_test_metrics['brier_score']:.3f})")
        for axis in axes: axis.set_xlim(0, 1); axis.set_ylim(0, 1)
        plt.tight_layout(); plt.show()
        """
    ),
    markdown("## A5. Scenario audit and permutation importance"),
    code(
        """
        forecast_audit = forecast_test[["scenario_id", FORECAST_TARGET]].copy()
        forecast_audit["probability"] = forecast_test_probability
        forecast_audit["prediction"] = forecast_test_prediction
        scenario_rows = []
        for scenario, group in forecast_audit.groupby("scenario_id"):
            scenario_rows.append({
                "scenario": scenario, "rows": len(group), "positive_rate": group[FORECAST_TARGET].mean(),
                "precision": precision_score(group[FORECAST_TARGET], group["prediction"], zero_division=0),
                "recall": recall_score(group[FORECAST_TARGET], group["prediction"], zero_division=0),
                "f1": f1_score(group[FORECAST_TARGET], group["prediction"], zero_division=0),
            })
        display(pd.DataFrame(scenario_rows).sort_values("f1"))

        sample_index = Xf_test.sample(min(2000, len(Xf_test)), random_state=SEED).index
        importance = permutation_importance(
            forecast_uncalibrated, Xf_test.loc[sample_index], yf_test.loc[sample_index],
            scoring="f1", n_repeats=5, random_state=SEED, n_jobs=-1,
        )
        forecast_importance = pd.DataFrame({"feature": FORECAST_FEATURES, "importance": importance.importances_mean}).sort_values("importance", ascending=False)
        display(forecast_importance.head(15))
        sns.barplot(data=forecast_importance.head(15), x="importance", y="feature", color="#3478bd")
        plt.title("Forecaster permutation importance"); plt.show()
        """
    ),
    markdown("## A6. Refit deployment artifact on all synthetic data"),
    code(
        """
        Xf_all = forecast_df[FORECAST_FEATURES]
        yf_all = forecast_df[FORECAST_TARGET].astype(int)
        gf_all = forecast_df["participant_id"]
        full_forecast_cv = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(Xf_all, yf_all, gf_all))
        forecast_deployment_model = CalibratedClassifierCV(
            estimator=clone(forecast_selected_template), method="sigmoid", cv=full_forecast_cv
        ).fit(Xf_all, yf_all)
        forecast_deployment_recommended = forecast_test_metrics["f1"] > forecast_baseline_metrics["f1"]
        forecast_version = f"forecaster-synthetic-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        forecast_bundle = {
            "kind": "near_miss_forecaster", "model_version": forecast_version,
            "estimator": forecast_deployment_model, "features": FORECAST_FEATURES,
            "metrics": {
                "selected_model": FORECAST_SELECTED_NAME,
                "cross_validation": forecast_cv_table.to_dict(orient="records"),
                "held_out_participant_test": forecast_test_metrics,
                "rule_based_baseline_test": forecast_baseline_metrics,
                "split_policy": "participant_id holdout; StratifiedGroupKFold on training participants",
                "data_origin": "SYNTHETIC",
            },
            "probability_is_calibrated": True,
            "classes": [str(value) for value in forecast_deployment_model.classes_],
            "dataset_rows": len(forecast_df),
            "deployment_recommended": forecast_deployment_recommended,
            "trained_at": datetime.now(UTC).isoformat(),
        }
        FORECAST_ARTIFACT = OUTPUT_DIR / "near_miss_forecaster.joblib"
        save_bundle(forecast_bundle, FORECAST_ARTIFACT)
        print("Deployment gate:", forecast_deployment_recommended)
        """
    ),
    markdown("# Part B - AI Priority Engine"),
    markdown("## B1. Participant holdout and rule baseline"),
    code(
        """
        priority_train, priority_test = participant_holdout(priority_df, PRIORITY_TARGET)
        Xp_train = priority_train[PRIORITY_FEATURES]
        yp_train = priority_train[PRIORITY_TARGET]
        gp_train = priority_train["participant_id"]
        Xp_test = priority_test[PRIORITY_FEATURES]
        yp_test = priority_test[PRIORITY_TARGET]
        priority_cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
        priority_cv_splits = list(priority_cv.split(Xp_train, yp_train, gp_train))
        print("Train rows / participants:", len(priority_train), priority_train.participant_id.nunique())
        print("Test rows / participants:", len(priority_test), priority_test.participant_id.nunique())

        def priority_rule_score(frame: pd.DataFrame) -> np.ndarray:
            clamp = np.clip
            score = (
                5.0
                + 23.0 * clamp(frame["danger_duration_seconds"] / 5.0, 0, 1)
                + 18.0 * clamp((frame["rssi_peak"] + 90.0) / 40.0, 0, 1)
                + 10.0 * frame["sudden_motion"]
                + 20.0 * ((frame["candidate_impact"] == 1) | (frame["candidate_fall"] == 1)).astype(int)
                + 10.0 * clamp(frame["repeated_exposure_count"] / 5.0, 0, 1)
                + 7.0 * frame["hazard_active"]
                + 4.0 * clamp(frame["state_transition_count"] / 5.0, 0, 1)
                + 3.0 * (1 - frame["local_warning_success"])
                + 3.0 * clamp(frame["post_event_stillness_seconds"] / 10.0, 0, 1)
                + 2.0 * clamp(frame["mq135_deviation"].clip(lower=0) / 1000.0, 0, 1)
            )
            return clamp(score.to_numpy(dtype=float), 0, 100)

        def priority_from_score(score: np.ndarray) -> np.ndarray:
            return np.where(score >= 70, "HIGH", np.where(score >= 40, "MEDIUM", "LOW"))

        priority_baseline_score = priority_rule_score(priority_test)
        priority_baseline_prediction = priority_from_score(priority_baseline_score)
        priority_baseline_metrics = multiclass_metrics(yp_test, priority_baseline_prediction)
        display(pd.DataFrame([priority_baseline_metrics]).drop(columns=["confusion_matrix", "labels"]))
        """
    ),
    markdown("## B2. Training CV model comparison"),
    code(
        """
        priority_models = model_candidates(PRIORITY_NUMERIC, PRIORITY_CATEGORICAL)
        priority_cv_rows = []
        for name, estimator in priority_models.items():
            scores = cross_validate(
                estimator, Xp_train, yp_train, cv=priority_cv_splits,
                scoring={"precision_macro": "precision_macro", "recall_macro": "recall_macro", "f1_macro": "f1_macro", "accuracy": "accuracy"},
                n_jobs=-1, return_train_score=False,
            )
            priority_cv_rows.append({
                "model": name,
                **{metric: scores[f"test_{metric}"].mean() for metric in ["precision_macro", "recall_macro", "f1_macro", "accuracy"]},
                "f1_macro_std": scores["test_f1_macro"].std(),
            })
        priority_cv_table = pd.DataFrame(priority_cv_rows).sort_values("f1_macro", ascending=False).reset_index(drop=True)
        display(priority_cv_table.style.format({column: "{:.4f}" for column in priority_cv_table.columns if column != "model"}))
        PRIORITY_SELECTED_NAME = str(priority_cv_table.iloc[0]["model"])
        print("Selected from training CV:", PRIORITY_SELECTED_NAME)
        """
    ),
    markdown("## B3. Untouched participant test"),
    code(
        """
        priority_selected_template = priority_models[PRIORITY_SELECTED_NAME]
        priority_evaluation_model = clone(priority_selected_template).fit(Xp_train, yp_train)
        priority_test_prediction = priority_evaluation_model.predict(Xp_test)
        priority_test_probability = priority_evaluation_model.predict_proba(Xp_test)
        priority_test_metrics = multiclass_metrics(yp_test, priority_test_prediction)
        display(pd.DataFrame([
            {"model": "rule_based_baseline", **priority_baseline_metrics},
            {"model": PRIORITY_SELECTED_NAME, **priority_test_metrics},
        ]).drop(columns=["confusion_matrix", "labels"]).set_index("model"))
        print(classification_report(yp_test, priority_test_prediction, labels=["LOW", "MEDIUM", "HIGH"], zero_division=0))
        ConfusionMatrixDisplay.from_predictions(
            yp_test, priority_test_prediction, labels=["LOW", "MEDIUM", "HIGH"],
            display_labels=["LOW", "MEDIUM", "HIGH"], cmap="Oranges",
        )
        plt.title("Priority Engine - unseen participant holdout"); plt.show()
        """
    ),
    markdown("## B4. Scenario audit and feature importance"),
    code(
        """
        priority_audit = priority_test[["scenario_id", PRIORITY_TARGET]].copy()
        priority_audit["prediction"] = priority_test_prediction
        priority_scenario_rows = []
        for scenario, group in priority_audit.groupby("scenario_id"):
            priority_scenario_rows.append({
                "scenario": scenario, "rows": len(group),
                "accuracy": accuracy_score(group[PRIORITY_TARGET], group["prediction"]),
                "f1_macro": f1_score(group[PRIORITY_TARGET], group["prediction"], average="macro", zero_division=0),
            })
        display(pd.DataFrame(priority_scenario_rows).sort_values("f1_macro"))

        sample_index = Xp_test.sample(min(2000, len(Xp_test)), random_state=SEED).index
        importance = permutation_importance(
            priority_evaluation_model, Xp_test.loc[sample_index], yp_test.loc[sample_index],
            scoring="f1_macro", n_repeats=5, random_state=SEED, n_jobs=-1,
        )
        priority_importance = pd.DataFrame({"feature": PRIORITY_FEATURES, "importance": importance.importances_mean}).sort_values("importance", ascending=False)
        display(priority_importance.head(15))
        sns.barplot(data=priority_importance.head(15), x="importance", y="feature", color="#d97706")
        plt.title("Priority Engine permutation importance"); plt.show()
        """
    ),
    markdown("## B5. Refit deployment artifact on all synthetic events"),
    code(
        """
        Xp_all = priority_df[PRIORITY_FEATURES]
        yp_all = priority_df[PRIORITY_TARGET]
        priority_deployment_model = clone(priority_selected_template).fit(Xp_all, yp_all)
        priority_deployment_recommended = priority_test_metrics["f1_macro"] > priority_baseline_metrics["f1_macro"]
        priority_version = f"priority-synthetic-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
        priority_bundle = {
            "kind": "priority_engine", "model_version": priority_version,
            "estimator": priority_deployment_model, "features": PRIORITY_FEATURES,
            "metrics": {
                "selected_model": PRIORITY_SELECTED_NAME,
                "cross_validation": priority_cv_table.to_dict(orient="records"),
                "held_out_participant_test": priority_test_metrics,
                "rule_based_baseline_test": priority_baseline_metrics,
                "split_policy": "participant_id holdout; StratifiedGroupKFold on training participants",
                "data_origin": "SYNTHETIC",
            },
            "probability_is_calibrated": False,
            "classes": [str(value) for value in priority_deployment_model.classes_],
            "dataset_rows": len(priority_df),
            "deployment_recommended": priority_deployment_recommended,
            "trained_at": datetime.now(UTC).isoformat(),
        }
        PRIORITY_ARTIFACT = OUTPUT_DIR / "priority_engine.joblib"
        save_bundle(priority_bundle, PRIORITY_ARTIFACT)
        print("Deployment gate:", priority_deployment_recommended)
        """
    ),
    markdown("# Part C - Inference contract and final model card"),
    code(
        """
        def forecast_level(probability: float) -> str:
            return "HIGH" if probability >= 0.70 else "MEDIUM" if probability >= 0.40 else "LOW"

        forecast_example = forecast_test.iloc[[0]]
        example_probability = float(forecast_deployment_model.predict_proba(forecast_example[FORECAST_FEATURES])[:, 1][0])
        forecast_output = {
            "engine": "NEAR_MISS_RISK_FORECASTER",
            "window_id": forecast_example.iloc[0]["window_id"],
            "worker_id": forecast_example.iloc[0]["worker_id"],
            "hazard_id": forecast_example.iloc[0]["hazard_id"],
            "escalation_probability": round(example_probability, 4),
            "risk_level": forecast_level(example_probability),
            "score_semantics": "CALIBRATED_PROBABILITY",
            "model_version": forecast_version,
            "advisory_only": True,
        }

        priority_example = priority_test.iloc[[0]]
        priority_probabilities = priority_deployment_model.predict_proba(priority_example[PRIORITY_FEATURES])[0]
        priority_classes = [str(label) for label in priority_deployment_model.classes_]
        severity = {"LOW": 20, "MEDIUM": 55, "HIGH": 90}
        priority_label = priority_classes[int(np.argmax(priority_probabilities))]
        priority_score = round(sum(float(probability) * severity[label] for probability, label in zip(priority_probabilities, priority_classes)))
        priority_output = {
            "engine": "AI_PRIORITY_ENGINE",
            "event_id": priority_example.iloc[0]["event_id"],
            "worker_id": priority_example.iloc[0]["worker_id"],
            "priority": priority_label,
            "priority_score": priority_score,
            "model_version": priority_version,
            "advisory_only": True,
            "requires_supervisor_verification": True,
        }
        print(json.dumps(forecast_output, indent=2, default=json_default))
        print(json.dumps(priority_output, indent=2, default=json_default))
        """
    ),
    code(
        """
        model_card = f'''# REKSA AI Synthetic Training Model Card

        Generated: {datetime.now(UTC).isoformat()}

        ## Data limitation
        Both models were trained on SYNTHETIC controlled-scenario data. Metrics do not establish real-world safety performance.

        ## Near-Miss Risk Forecaster
        - Selected model: {FORECAST_SELECTED_NAME}
        - Holdout policy: unseen participant_id
        - Test F1: {forecast_test_metrics['f1']:.4f}
        - Test recall: {forecast_test_metrics['recall']:.4f}
        - Test ROC-AUC: {forecast_test_metrics['roc_auc']:.4f}
        - Brier score: {forecast_test_metrics['brier_score']:.4f}
        - Calibrated: yes (sigmoid, grouped folds)
        - Deployment gate vs rule baseline: {forecast_deployment_recommended}

        ## AI Priority Engine
        - Selected model: {PRIORITY_SELECTED_NAME}
        - Holdout policy: unseen participant_id
        - Test macro F1: {priority_test_metrics['f1_macro']:.4f}
        - Test macro recall: {priority_test_metrics['recall_macro']:.4f}
        - Deployment gate vs rule baseline: {priority_deployment_recommended}

        ## Safety boundary
        These models are advisory only. The forecaster does not replace the deterministic ESP32 state machine. The Priority Engine does not verify near-miss events. Final verification remains with the K3 supervisor.
        '''
        MODEL_CARD_PATH = OUTPUT_DIR / "REKSA_AI_SYNTHETIC_MODEL_CARD.md"
        MODEL_CARD_PATH.write_text(model_card.strip() + "\\n", encoding="utf-8")
        print(model_card)
        print("Artifacts:")
        for path in sorted(OUTPUT_DIR.iterdir()):
            print(" -", path.name, f"({path.stat().st_size / 1024:.1f} KiB)")
        """
    ),
    markdown(
        """
        ## Final interpretation

        - Jika model ML tidak mengalahkan rule baseline pada participant holdout, `deployment_recommended` menjadi `false` dan API REKSA akan kembali memakai baseline.
        - Hasil tinggi pada dataset sintetis biasanya optimistis karena model dapat mempelajari pola generator. Ulangi seluruh notebook dengan controlled trajectories asli dan label supervisor.
        - Untuk data asli, pertahankan participant holdout. Jangan melakukan random row split pada overlapping windows.
        - Forecaster yang akan dipindah ke ESP32 membutuhkan benchmark ukuran flash/RAM, latensi, dan konversi model terpisah. Artifact notebook saat ini ditujukan untuk backend terlebih dahulu.
        """
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "colab": {"name": "Reksa_AI.ipynb", "provenance": []},
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

output = Path(__file__).resolve().parents[1] / "notebooks/Reksa_AI.ipynb"
output.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Built {output} with {len(cells)} cells")
