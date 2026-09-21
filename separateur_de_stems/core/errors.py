class StemSeparatorError(Exception):
    """Base error for expected application failures."""


class UnsupportedFormatError(StemSeparatorError):
    pass


class ModelUnavailableError(StemSeparatorError):
    pass


class OutputError(StemSeparatorError):
    pass


class CancelledError(StemSeparatorError):
    pass
