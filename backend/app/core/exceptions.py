"""Application-level exceptions shared across services and transport layers."""


class AuthenticationError(Exception):
    """Credentials or access token could not be authenticated."""


class InactiveAccountError(Exception):
    """An otherwise valid identity has been administratively disabled."""


class DuplicateEmailError(Exception):
    """A normalized email address is already registered."""
