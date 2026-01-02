class AIKeyNotConfiguredError(Exception):
    """Raised when no valid AI provider key is available for a user."""

    def __init__(self, message="No AI provider configured. Please add an API key in Settings."):
        self.message = message
        super().__init__(self.message)


class AIKeyValidationError(Exception):
    """Raised when an AI provider key fails validation."""

    def __init__(self, message="API key validation failed.", provider=None, details=None):
        self.message = message
        self.provider = provider
        self.details = details
        super().__init__(self.message)
