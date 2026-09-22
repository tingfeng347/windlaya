"""Domain-facing errors mapped to the WindLaya HTTP contract."""


class WindLayaError(Exception):
    code = "INTERNAL_ERROR"
    status_code = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidModelError(WindLayaError):
    code = "INVALID_MODEL"
    status_code = 400


class InvalidRequestError(WindLayaError):
    code = "INVALID_REQUEST"
    status_code = 400


class ModelLoadError(WindLayaError):
    code = "MODEL_LOAD_ERROR"
    status_code = 503


class ModelUnavailableError(WindLayaError):
    code = "MODEL_UNAVAILABLE"
    status_code = 503


class InferenceError(WindLayaError):
    code = "INFERENCE_ERROR"
    status_code = 500
