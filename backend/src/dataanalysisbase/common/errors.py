"""Project-wide exception hierarchy."""


class DABError(Exception):
    """Base exception for DataAnalysisBase."""


class ConfigError(DABError):
    """Raised when runtime configuration is invalid."""


class ProviderError(DABError):
    """Raised when a data provider fails in an isolated way."""

    def __init__(
        self,
        provider: str,
        dataset_type: str,
        message: str,
        *,
        retryable: bool = True,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.dataset_type = dataset_type
        self.retryable = retryable


class StorageError(DABError):
    """Raised when storage operations fail."""


class FusionBlockedError(DABError):
    """Raised when reconciliation finds a blocking L3 issue."""


class LLMError(DABError):
    """Raised when LLM calls fail or return invalid output."""


class InvalidSecurityId(DABError):
    """Raised when a security identifier cannot be parsed."""


class NameNotResolvable(InvalidSecurityId):
    """Raised when raw input appears to be a name instead of a code."""


class UnsupportedMarket(InvalidSecurityId):
    """Raised when a market suffix is not supported."""
