"""Serialize cross-module transitions; perform network/disk effects afterwards."""

from contextlib import contextmanager
from functools import wraps
import threading


class Coordinator:
    def __init__(self):
        self.lock = threading.RLock()
        self._local = threading.local()

    @contextmanager
    def transition(self):
        if getattr(self._local, "effects", None) is not None:
            yield
            return
        effects = []
        try:
            with self.lock:
                self._local.effects = effects
                try:
                    yield
                finally:
                    del self._local.effects
        finally:
            # Even a failed request may have committed changes and queued events.
            for effect in effects:
                effect()

    def defer(self, effect):
        effects = getattr(self._local, "effects", None)
        if effects is None:
            effect()
        else:
            effects.append(effect)


def coordinated(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.coordinator.transition():
            return method(self, *args, **kwargs)
    return wrapped
