"""User authentication module for the application."""

def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user with credentials.

    Validates username and password against the user database.
    Returns True if authentication succeeds.
    """
    if not username or not password:
        return False

    # Verify against database
    user = get_user_by_username(username)
    if user is None:
        return False

    return verify_password(password, user.password_hash)
