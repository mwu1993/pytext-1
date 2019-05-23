#!/usr/bin/env python3
# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved
from .pytext_config import LATEST_VERSION


ADAPTERS = {}


def register_adapter(from_version):
    def decorator(fn):
        if from_version in ADAPTERS:
            raise Exception(
                "Duplicated adapter from_version={}: '{}' and '{}'".format(
                    from_version, fn.__name__, ADAPTERS[from_version].__name__
                )
            )
        else:
            ADAPTERS[from_version] = fn
        return fn

    return decorator


def find_dicts_containing_key(json_config, key):
    if key in json_config:
        yield json_config
    for _, v in json_config.items():
        if hasattr(v, "__contains__") and hasattr(v, "items"):
            yield from find_dicts_containing_key(v, key)


@register_adapter(from_version=0)
def v0_to_v1(json_config):
    # migrate optimizer and random_seed params
    [task] = json_config["task"].values()
    if (
        "optimizer" not in task
        or "Adam" in task["optimizer"]
        or "SGD" in task["optimizer"]
        or "NAG" in task["optimizer"]
    ) and ("trainer" not in task or "random_seed" not in task["trainer"]):
        return json_config

    if "trainer" in task and "random_seed" in task["trainer"]:
        json_config["random_seed"] = task["trainer"]["random_seed"]
        del task["trainer"]["random_seed"]
    if "optimizer" in task and not any(
        opt in task["optimizer"] for opt in ["Adam", "SGD", "NAG"]
    ):
        op_type = task["optimizer"].get("type", "adam")
        if op_type == "adam":
            op_config = {"Adam": {}}
            for key in ["lr", "weight_decay"]:
                if key in task["optimizer"]:
                    op_config["Adam"][key] = task["optimizer"][key]
        elif op_type == "sgd":
            op_config = {"SGD": {}}
            for key in ["lr", "momentum"]:
                if key in task["optimizer"]:
                    op_config["SGD"][key] = task["optimizer"][key]
        elif op_type == "nag":
            op_config = {"NAG": {}}
            for key in ["lr", "weight_decay", "momentum"]:
                if key in task["optimizer"]:
                    op_config["NAG"][key] = task["optimizer"][key]
        else:
            raise ValueError("Migration not supported for your optimizer")
        task["optimizer"] = op_config
    return json_config


@register_adapter(from_version=1)
def v1_to_v2(json_config):
    # migrate optimizer params
    [task] = json_config["task"].values()
    if (
        "scheduler" not in task
        or task["scheduler"] is None
        or task["scheduler"].get("type") is None
    ):
        return json_config
    op_type = task["scheduler"].get("type")
    if op_type == "step_lr":
        op_config = {"StepLR": {}}
        for key in ["step_size", "gamma"]:
            if key in task["scheduler"]:
                op_config["StepLR"][key] = task["scheduler"][key]
        task["scheduler"] = op_config
    elif op_type == "lm_fine_tuning":
        op_config = {"LmFineTuning": {}}
        for key in [
            "cut_frac",
            "ratio",
            "non_pretrained_param_groups",
            "lm_lr_multiplier",
            "lm_use_per_layer_lr",
            "lm_gradual_unfreezing",
            "last_epoch",
        ]:
            if key in task["scheduler"]:
                op_config["LmFineTuning"][key] = task["scheduler"][key]
        task["scheduler"] = op_config
    elif op_type == "reduce_lr_on_plateau":
        op_config = {"ReduceLROnPlateau": {}}
        for key in [
            "lower_is_better",
            "factor",
            "patience",
            "min_lr",
            "threshold",
            "threshold_is_absolute",
            "cooldown",
        ]:
            if key in task["scheduler"]:
                op_config["ReduceLROnPlateau"][key] = task["scheduler"][key]
        task["scheduler"] = op_config
    elif op_type == "cosine_annealing_lr":
        op_config = {"CosineAnnealingLR": {}}
        for key in ["t_max", "eta_min"]:
            if key in task["scheduler"]:
                op_config["CosineAnnealingLR"][key] = task["scheduler"][key]
        task["scheduler"] = op_config
    elif op_type == "exponential_lr":
        op_config = {"ExponentialLR": {}}
        for key in ["gamma"]:
            if key in task["scheduler"]:
                op_config["ExponentialLR"][key] = task["scheduler"][key]
        task["scheduler"] = op_config
    elif op_type == "none":
        del task["scheduler"]
    else:
        raise ValueError("Migration for your scheduler %s not supported." % op_type)
    return json_config


@register_adapter(from_version=2)
def v2_to_v3(json_config):
    """Optimizer and Scheduler configs used to be part of the task config,
    they now live in the trainer's config.
    """
    [task] = json_config["task"].values()
    for section_str in ["optimizer", "scheduler"]:
        if section_str in task:
            if "trainer" not in task:
                task["trainer"] = {}
            trainer = task["trainer"]
            # a hack to support an older hack:
            # some tasks like ensemble have a 'real_trainer' section inside trainer
            # that has the actual trainer config
            if "real_trainer" in trainer:
                real_trainer = trainer["real_trainer"]
                real_trainer[section_str] = task[section_str]
            else:
                trainer[section_str] = task[section_str]
            # remove from task config
            task.pop(section_str)

    return json_config


@register_adapter(from_version=3)
def v3_to_v4(json_config):
    """Key for provding the path for contextual token embedding has changed from
    `pretrained_model_embedding` to `contextual_token_embedding. This affects the
    `features` section of the config.
    """
    [task] = json_config["task"].values()
    old_key = "pretrained_model_embedding"
    new_key = "contextual_token_embedding"
    for section_str in ["features", "labels"]:
        if section_str in task:
            section = task[section_str]
            if section and old_key in section:
                section[new_key] = section[old_key]
                section.pop(old_key)

    return json_config


def deprecate(json_config, t):
    for section in find_dicts_containing_key(json_config, t):
        section[t + "_Deprecated"] = section.pop(t)


@register_adapter(from_version=4)
def doc_model_deprecated(json_config):
    """
    Rename DocModel to DocModel_Deprecated
    """
    deprecate(json_config, "DocModel")

    return json_config


@register_adapter(from_version=5)
def old_tasks_deprecated(json_config):
    """
    Rename tasks with data_handler config to _Deprecated
    """
    deprecate(json_config, "BertClassificationTask")
    deprecate(json_config, "BertPairClassificationTask")
    deprecate(json_config, "BertPairwiseClassificationTask")
    deprecate(json_config, "COLMClassifyTask")
    deprecate(json_config, "ContextSCLSTMCompositionalTask")
    deprecate(json_config, "ContextSeq2SeqTask")
    deprecate(json_config, "ContextualIntentSlotTask")
    deprecate(json_config, "DocClassificationTask")
    deprecate(json_config, "ElmoDocClassificationTask")
    deprecate(json_config, "ElmoFineTunePairwiseClassificationTask")
    deprecate(json_config, "EnsembleTask")
    deprecate(json_config, "FederatedLearningTaskBase")
    deprecate(json_config, "FLDocClassificationTask")
    deprecate(json_config, "FLQueryDocumentPairwiseRankingTask")
    deprecate(json_config, "I18NDocClassificationTask")
    deprecate(json_config, "I18NJointTextTask")
    deprecate(json_config, "JointTextTask")
    deprecate(json_config, "KDDocClassificationTask")
    deprecate(json_config, "LMTask")
    deprecate(json_config, "NLGSeq2SeqTask")
    deprecate(json_config, "PairClassificationTask")
    deprecate(json_config, "PairwiseAttentionClassificationTask")
    deprecate(json_config, "QueryDocumentPairwiseRankingTask")
    deprecate(json_config, "SCLSTMCompositionalTask")
    deprecate(json_config, "SCLSTMTask")
    deprecate(json_config, "SemanticParsingCppTask")
    deprecate(json_config, "SemanticParsingTask")
    deprecate(json_config, "Seq2SeqTask")
    deprecate(json_config, "SeqNNTask")
    deprecate(json_config, "SGNNClassificationTask")
    deprecate(json_config, "ShallowClassificationTask")
    deprecate(json_config, "ShallowTaggingTask")
    deprecate(json_config, "SpanClassificationTask")
    deprecate(json_config, "TreeParserTask")
    deprecate(json_config, "WordTaggingTask")

    return json_config


@register_adapter(from_version=6)
def v6_to_v7(json_config):
    """
    Make `LabelTensorizer` expansible. If the `labels` field should be an instance of
    `LabelTensorizer`, convert it to`{LabelTensorizer: labels}`.
    """
    [(task_name, task)] = json_config["task"].items()
    if task_name in (
        "BertPairRegressionTask",
        "NewDocumentRegression",
        "NewWordTaggingTask",
    ):
        # Task has a label tensorizer different from LabelTensorizer.
        return json_config

    model = task.get("model")
    if not model:
        return json_config

    model_name = None
    if "inputs" in model:
        inputs = model["inputs"]
    elif len(model) == 1:
        [(model_name, model_val)] = model.items()
        inputs = model_val.get("inputs")
    else:
        inputs = None
    if not inputs:
        return json_config
    if model_name in (
        "NewBertRegressionModel",
        "DocRegressionModel",
        "NewWordTaggingModel",
    ):
        # Model has a label tensorizer different from LabelTensorizer.
        return json_config

    labels = inputs.get("labels")
    if labels is None:
        return json_config

    inputs["labels"] = {"LabelTensorizer": labels}
    return json_config


@register_adapter(from_version=7)
def lm_model_deprecated(json_config):
    """
    Rename LM model to _Deprecated (LMTask is already deprecated in v5)
    """
    deprecate(json_config, "LMLSTM")

    return json_config


def upgrade_one_version(json_config):
    current_version = json_config.get("version", 0)
    adapter = ADAPTERS.get(current_version)
    if not adapter:
        raise Exception(f"no adapter found for version {current_version}")
    json_config = adapter(json_config)
    json_config["version"] = current_version + 1
    return json_config


def upgrade_to_latest(json_config):
    current_version = json_config.get("version") or 0
    if current_version > LATEST_VERSION:
        raise Exception(
            f"config version {json_config['version']} shouldn't exceed lastest \
            version {LATEST_VERSION}"
        )
    while current_version != LATEST_VERSION:
        json_config = upgrade_one_version(json_config)
        current_version = json_config["version"]
    return json_config
