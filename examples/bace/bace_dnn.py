import sys
import os
import deepchem
import tempfile, shutil
import numpy as np
import numpy.random
from deepchem.utils.save import load_from_disk
from deepchem.splits import SpecifiedSplitter
from deepchem.featurizers.featurize import DataFeaturizer
from deepchem.datasets import Dataset
from deepchem.transformers import NormalizationTransformer
from deepchem.transformers import ClippingTransformer
from deepchem.hyperparameters import HyperparamOpt
from sklearn.ensemble import RandomForestClassifier
from deepchem.models.sklearn_models import SklearnModel
from bace_features import user_specified_features
from deepchem import metrics
from deepchem.metrics import Metric
from deepchem.utils.evaluate import Evaluator
from deepchem.datasets.bace_datasets import load_bace
from deepchem.models.keras_models.fcnet import SingleTaskDNN


def bace_dnn_model(mode="classification", verbosity="high", split="20-80"):
  (bace_tasks, train_dataset, valid_dataset, test_dataset, crystal_dataset,
   transformers) = load_bace(mode=mode, transform=True, split=split)

  if mode == "regression":
    r2_metric = Metric(metrics.r2_score, verbosity=verbosity)
    rms_metric = Metric(metrics.rms_score, verbosity=verbosity)
    mae_metric = Metric(metrics.mae_score, verbosity=verbosity)
    all_metrics = [r2_metric, rms_metric, mae_metric]
    metric = r2_metric
  elif mode == "classification":
    accuracy_metric = Metric(metrics.accuracy_score, verbosity=verbosity)
    mcc_metric = Metric(metrics.matthews_corrcoef, verbosity=verbosity)
    # Note sensitivity = recall
    recall_metric = Metric(metrics.recall_score, verbosity=verbosity)
    all_metrics = [accuracy_metric, mcc_metric, recall_metric]
    metric = accuracy_metric
  else:
    raise ValueError("Invalid mode %s" % mode)

  def model_builder(tasks, task_types, params_dict, model_dir, verbosity=None):
      n_estimators = params_dict["n_estimators"]
      max_features = params_dict["max_features"]
      return SklearnModel(
          tasks, task_types, params_dict, model_dir, 
          model_instance=RandomForestClassifier(n_estimators=n_estimators,
                                                max_features=max_features))

  params_dict = {"activation": ["relu"],
                  "momentum": [.9],
                  "batch_size": [50],
                  "init": ["glorot_uniform"],
                  "data_shape": [train_dataset.get_data_shape()],
                  "learning_rate": np.power(10., np.random.uniform(-5, -3, size=4)),
                  "decay": np.power(10, np.random.uniform(-6, -4, size=4)),
                  "nb_hidden": [1000],
                  "nb_epoch": [40],
                  "nesterov": [False],
                  "dropout": [.5],
                  "nb_layers": [1],
                  "batchnorm": [False],
                }

  optimizer = HyperparamOpt(SingleTaskDNN, bace_tasks,
                            {task: mode for task in bace_tasks},
                            verbosity=verbosity)
  best_dnn, best_hyperparams, all_results = optimizer.hyperparam_search(
      params_dict, train_dataset, valid_dataset, transformers,
      metric=metric)

  if len(train_dataset) > 0:
    dnn_train_evaluator = Evaluator(best_dnn, train_dataset, transformers)            
    csv_out = "dnn_%s_%s_train.csv" % (mode, split)
    stats_out = "dnn_%s_%s_train_stats.txt" % (mode, split)
    dnn_train_score = dnn_train_evaluator.compute_model_performance(
        all_metrics, csv_out=csv_out, stats_out=stats_out)
    print("DNN Train set %s: %s" % (metric.name, str(dnn_train_score)))

  if len(valid_dataset) > 0:
    dnn_valid_evaluator = Evaluator(best_dnn, valid_dataset, transformers)            
    csv_out = "dnn_%s_%s_valid.csv" % (mode, split)
    stats_out = "dnn_%s_%s_valid_stats.txt" % (mode, split)
    dnn_valid_score = dnn_valid_evaluator.compute_model_performance(
        all_metrics, csv_out=csv_out, stats_out=stats_out)
    print("DNN Valid set %s: %s" % (metric.name, str(dnn_valid_score)))
                                                                                               
  if len(test_dataset) > 0:
    dnn_test_evaluator = Evaluator(best_dnn, test_dataset, transformers)
    csv_out = "dnn_%s_%s_test.csv" % (mode, split)
    stats_out = "dnn_%s_%s_test_stats.txt" % (mode, split)
    dnn_test_score = dnn_test_evaluator.compute_model_performance(
        all_metrics, csv_out=csv_out, stats_out=stats_out)
    print("DNN Test set %s: %s" % (metric.name, str(dnn_test_score)))

  if len(crystal_dataset) > 0:
    dnn_crystal_evaluator = Evaluator(best_dnn, crystal_dataset, transformers)
    csv_out = "dnn_%s_%s_crystal.csv" % (mode, split)
    stats_out = "dnn_%s_%s_crystal_stats.txt" % (mode, split)
    dnn_crystal_score = dnn_crystal_evaluator.compute_model_performance(
        all_metrics, csv_out=csv_out, stats_out=stats_out)
    print("DNN Crystal set %s: %s" % (metric.name, str(dnn_crystal_score)))

if __name__ == "__main__":
  print("Classifier DNN 20-80:")
  print("--------------------------------")
  bace_dnn_model(mode="classification", verbosity="high", split="20-80")
  print("Classifier DNN 80-20:")
  print("--------------------------------")
  bace_dnn_model(mode="classification", verbosity="high", split="80-20")
  print("Regressor DNN 20-80:")
  print("--------------------------------")
  bace_dnn_model(mode="regression", verbosity="high", split="20-80")
  print("Regressor DNN 80-20:")
  print("--------------------------------")
  bace_dnn_model(mode="regression", verbosity="high", split="80-20")
