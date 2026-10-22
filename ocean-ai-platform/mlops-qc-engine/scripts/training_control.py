"""Validation-based controls shared by candidate training entry points."""
from typing import Any


DEFAULT_EPOCHS = 30
DEFAULT_BATCH_SIZE = 64


def build_training_callbacks(tf: Any, patience: int = 6) -> tuple[Any, Any]:
    """Select weights by normalized validation MSE and reduce LR on a plateau."""
    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor="val_loss",
        mode="min",
        min_delta=0.0,
        patience=patience,
        restore_best_weights=True,
    )
    reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
        monitor="val_loss",
        mode="min",
        factor=0.5,
        patience=2,
        min_delta=1e-6,
        min_lr=1e-5,
    )
    return early_stop, reduce_lr


def restore_best_training_weights(model: Any, early_stop: Any) -> dict[str, Any]:
    """Restore validation-selected weights after every successful fit.

    Keras 2.10 restores inside its early-stop branch only. Reaching the maximum
    epoch therefore requires an explicit restore before calibration and saving.
    An absent weight snapshot is a failed training contract, never permission to
    save the final epoch as though it were the selected model.
    """
    best_weights = getattr(early_stop, "best_weights", None)
    if best_weights is None:
        raise RuntimeError("EarlyStopping best_weights are missing after training")
    model.set_weights(best_weights)
    best_epoch = getattr(early_stop, "best_epoch", None)
    return {
        "best_epoch": None if best_epoch is None else int(best_epoch) + 1,
        "restored_best_weights": True,
    }
