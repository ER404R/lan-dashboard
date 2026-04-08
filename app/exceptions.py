class UnauthenticatedError(Exception):
    """Raised when user is not authenticated"""
    pass


class UnauthorizedError(Exception):
    """Raised when user lacks required authorization (e.g., admin)"""
    pass
