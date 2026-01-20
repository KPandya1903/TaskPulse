"""
Test Suite for Pulse Authentication Module.

This module contains comprehensive tests for the authentication system including:
- User registration
- User login
- Token refresh
- Protected route access

TDD Approach:
These tests are written BEFORE the implementation exists. They will fail initially
(red phase), and the implementation should be written to make them pass (green phase).

Test Naming Convention:
- test_<action>_<scenario> - e.g., test_login_success, test_login_invalid_email

All tests use async/await patterns with httpx.AsyncClient for testing FastAPI
async endpoints.
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4

# These imports will fail initially - expected for TDD red phase
from app.models.user import User


# =============================================================================
# USER LOGIN TESTS
# =============================================================================


class TestUserLogin:
    """Test cases for the POST /api/v1/auth/login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(
        self,
        client: AsyncClient,
        test_user: User,
        login_data: dict,
    ) -> None:
        """
        Test successful user login with valid credentials.

        Given: A registered and active user exists in the database
        When: The user submits valid email and password to /api/v1/auth/login
        Then: The response should contain:
            - HTTP 200 status code
            - access_token (JWT string)
            - refresh_token (JWT string)
            - token_type: "bearer"
        """
        response = await client.post(
            "/api/v1/auth/login",
            data=login_data,  # OAuth2 password flow uses form data
        )

        assert response.status_code == 200, (
            f"Expected 200 OK for valid login, got {response.status_code}. "
            f"Response: {response.json()}"
        )

        data = response.json()

        assert "access_token" in data, "Response should contain 'access_token'"
        assert "refresh_token" in data, "Response should contain 'refresh_token'"
        assert data.get("token_type") == "bearer", (
            f"token_type should be 'bearer', got '{data.get('token_type')}'"
        )

        # Verify tokens are non-empty strings
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 0, (
            "access_token should be a non-empty string"
        )
        assert isinstance(data["refresh_token"], str) and len(data["refresh_token"]) > 0, (
            "refresh_token should be a non-empty string"
        )

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client: AsyncClient) -> None:
        """
        Test login attempt with non-existent email.

        Given: No user exists with the specified email
        When: Login is attempted with that email
        Then: The response should be 401 Unauthorized with appropriate error message
        """
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "anypassword123",
            },
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for non-existent email, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_login_invalid_password(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """
        Test login attempt with wrong password.

        Given: A user exists with email 'test@example.com'
        When: Login is attempted with correct email but wrong password
        Then: The response should be 401 Unauthorized
        """
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for wrong password, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_login_inactive_user(
        self,
        client: AsyncClient,
        inactive_user: User,
    ) -> None:
        """
        Test that inactive users cannot log in.

        Given: A user exists but their account is marked as inactive (is_active=False)
        When: The user attempts to log in with valid credentials
        Then: The response should be 401 Unauthorized indicating the account is inactive
        """
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "inactive@example.com",
                "password": "testpassword123",
            },
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for inactive user, got {response.status_code}. "
            "Inactive users should not be able to log in."
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_login_missing_credentials(self, client: AsyncClient) -> None:
        """
        Test login attempt with missing credentials.

        Given: No credentials are provided
        When: Login endpoint is called without username/password
        Then: The response should be 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/api/v1/auth/login",
            data={},
        )

        assert response.status_code == 422, (
            f"Expected 422 for missing credentials, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_login_empty_password(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """
        Test login attempt with empty password.

        Given: A valid user exists
        When: Login is attempted with correct email but empty password
        Then: The response should indicate authentication failure
        """
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "test@example.com",
                "password": "",
            },
        )

        # Should be either 401 (auth failed) or 422 (validation failed)
        assert response.status_code in (401, 422), (
            f"Expected 401 or 422 for empty password, got {response.status_code}"
        )


# =============================================================================
# PROTECTED ROUTE ACCESS TESTS
# =============================================================================


class TestProtectedRouteAccess:
    """Test cases for the GET /api/v1/auth/me endpoint (protected route)."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(
        self,
        client: AsyncClient,
        test_user: User,
        auth_headers: dict[str, str],
    ) -> None:
        """
        Test accessing protected route with valid authentication token.

        Given: A valid access token for an existing user
        When: The /api/v1/auth/me endpoint is called with the token
        Then: The response should contain the user's information:
            - HTTP 200 status code
            - User email
            - User full_name
            - is_active status
            - User ID
        """
        response = await client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )

        assert response.status_code == 200, (
            f"Expected 200 OK for valid token, got {response.status_code}. "
            f"Response: {response.json()}"
        )

        data = response.json()

        assert data.get("email") == test_user.email, (
            f"Expected email '{test_user.email}', got '{data.get('email')}'"
        )
        assert data.get("full_name") == test_user.full_name, (
            f"Expected full_name '{test_user.full_name}', got '{data.get('full_name')}'"
        )
        assert data.get("is_active") is True, "User should be active"
        assert "id" in data, "Response should contain user ID"

        # Verify sensitive data is not exposed
        assert "hashed_password" not in data, (
            "Response should not expose hashed_password"
        )

    @pytest.mark.asyncio
    async def test_get_current_user_no_token(self, client: AsyncClient) -> None:
        """
        Test accessing protected route without authentication token.

        Given: No authentication token is provided
        When: The /api/v1/auth/me endpoint is called without Authorization header
        Then: The response should be 401 Unauthorized
        """
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized without token, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(
        self,
        client: AsyncClient,
        invalid_auth_headers: dict[str, str],
    ) -> None:
        """
        Test accessing protected route with invalid/malformed token.

        Given: A malformed or invalid JWT token
        When: The /api/v1/auth/me endpoint is called with this token
        Then: The response should be 401 Unauthorized
        """
        response = await client.get(
            "/api/v1/auth/me",
            headers=invalid_auth_headers,
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for invalid token, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(
        self,
        client: AsyncClient,
        expired_auth_headers: dict[str, str],
    ) -> None:
        """
        Test accessing protected route with expired token.

        Given: An expired JWT access token
        When: The /api/v1/auth/me endpoint is called with the expired token
        Then: The response should be 401 Unauthorized indicating token expiration
        """
        response = await client.get(
            "/api/v1/auth/me",
            headers=expired_auth_headers,
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for expired token, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_get_current_user_wrong_scheme(self, client: AsyncClient) -> None:
        """
        Test accessing protected route with wrong authentication scheme.

        Given: An Authorization header with wrong scheme (e.g., Basic instead of Bearer)
        When: The /api/v1/auth/me endpoint is called
        Then: The response should be 401 Unauthorized
        """
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},  # Basic auth header
        )

        assert response.status_code == 401, (
            f"Expected 401 for wrong auth scheme, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_get_current_user_deleted_user(
        self,
        client: AsyncClient,
        db_session,
    ) -> None:
        """
        Test accessing protected route when user has been deleted.

        Given: A valid token was issued for a user who has since been deleted
        When: The /api/v1/auth/me endpoint is called with that token
        Then: The response should be 401 Unauthorized
        """
        # Import here to get security functions
        from app.core.security import create_access_token

        # Create token for a non-existent user ID
        fake_user_id = str(uuid4())
        token = create_access_token(subject=fake_user_id)

        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 401, (
            f"Expected 401 for deleted user, got {response.status_code}"
        )


# =============================================================================
# USER REGISTRATION TESTS
# =============================================================================


class TestUserRegistration:
    """Test cases for the POST /api/v1/auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_success(
        self,
        client: AsyncClient,
        create_test_user_data: dict,
    ) -> None:
        """
        Test successful user registration.

        Given: Valid registration data (email, password, full_name)
        When: POST request is made to /api/v1/auth/register
        Then: The response should:
            - Have HTTP 201 Created status code
            - Return the created user's data (without password)
            - The user should be able to log in afterward
        """
        response = await client.post(
            "/api/v1/auth/register",
            json=create_test_user_data,
        )

        assert response.status_code == 201, (
            f"Expected 201 Created for successful registration, got {response.status_code}. "
            f"Response: {response.json()}"
        )

        data = response.json()

        assert data.get("email") == create_test_user_data["email"], (
            f"Expected email '{create_test_user_data['email']}', got '{data.get('email')}'"
        )
        assert data.get("full_name") == create_test_user_data["full_name"], (
            f"Expected full_name '{create_test_user_data['full_name']}', "
            f"got '{data.get('full_name')}'"
        )
        assert "id" in data, "Response should contain user ID"
        assert data.get("is_active") is True, "New users should be active by default"

        # Verify password is not returned
        assert "password" not in data, "Response should not contain password"
        assert "hashed_password" not in data, "Response should not contain hashed_password"

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """
        Test registration with an email that already exists.

        Given: A user already exists with email 'test@example.com'
        When: Registration is attempted with the same email
        Then: The response should be 400 Bad Request indicating duplicate email
        """
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",  # Same as test_user
                "password": "anotherpassword123",
                "full_name": "Another User",
            },
        )

        assert response.status_code == 400, (
            f"Expected 400 Bad Request for duplicate email, got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"
        # The error message should indicate the email is already registered
        assert "email" in data["detail"].lower() or "already" in data["detail"].lower(), (
            f"Error message should mention email conflict: {data['detail']}"
        )

    @pytest.mark.asyncio
    async def test_register_invalid_email_format(self, client: AsyncClient) -> None:
        """
        Test registration with invalid email format.

        Given: Registration data with malformed email
        When: POST request is made to /api/v1/auth/register
        Then: The response should be 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-a-valid-email",
                "password": "validpassword123",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 422, (
            f"Expected 422 for invalid email format, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient) -> None:
        """
        Test registration with a weak/short password.

        Given: Registration data with password that doesn't meet requirements
        When: POST request is made to /api/v1/auth/register
        Then: The response should indicate password validation failure
        """
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "123",  # Too short
                "full_name": "Test User",
            },
        )

        # Should be 422 (validation) or 400 (business rule)
        assert response.status_code in (400, 422), (
            f"Expected 400 or 422 for weak password, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_missing_required_fields(self, client: AsyncClient) -> None:
        """
        Test registration with missing required fields.

        Given: Registration data missing email or password
        When: POST request is made to /api/v1/auth/register
        Then: The response should be 422 Unprocessable Entity
        """
        # Missing email
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "password": "validpassword123",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 422, (
            f"Expected 422 for missing email, got {response.status_code}"
        )

        # Missing password
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "full_name": "Test User",
            },
        )

        assert response.status_code == 422, (
            f"Expected 422 for missing password, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_register_then_login(
        self,
        client: AsyncClient,
        create_test_user_data: dict,
    ) -> None:
        """
        Test that a newly registered user can immediately log in.

        Given: A new user is successfully registered
        When: The user attempts to log in with their credentials
        Then: Login should succeed and return tokens
        """
        # First, register the user
        register_response = await client.post(
            "/api/v1/auth/register",
            json=create_test_user_data,
        )

        assert register_response.status_code == 201, (
            f"Registration failed: {register_response.json()}"
        )

        # Then, try to login
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": create_test_user_data["email"],
                "password": create_test_user_data["password"],
            },
        )

        assert login_response.status_code == 200, (
            f"Login after registration failed: {login_response.json()}"
        )

        data = login_response.json()
        assert "access_token" in data, "Login should return access_token"
        assert "refresh_token" in data, "Login should return refresh_token"


# =============================================================================
# TOKEN REFRESH TESTS
# =============================================================================


class TestTokenRefresh:
    """Test cases for the POST /api/v1/auth/refresh endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_token_success(
        self,
        client: AsyncClient,
        test_user: User,
        valid_refresh_token: str,
    ) -> None:
        """
        Test successful token refresh with valid refresh token.

        Given: A valid, non-expired, non-revoked refresh token
        When: POST request is made to /api/v1/auth/refresh with the token
        Then: The response should contain:
            - HTTP 200 status code
            - New access_token
            - New refresh_token (token rotation)
            - token_type: "bearer"
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": valid_refresh_token},
        )

        assert response.status_code == 200, (
            f"Expected 200 OK for valid refresh, got {response.status_code}. "
            f"Response: {response.json()}"
        )

        data = response.json()

        assert "access_token" in data, "Response should contain new 'access_token'"
        assert "refresh_token" in data, "Response should contain new 'refresh_token'"
        assert data.get("token_type") == "bearer", "token_type should be 'bearer'"

        # Verify new tokens are different (token rotation)
        assert data["refresh_token"] != valid_refresh_token, (
            "New refresh token should be different from the old one (token rotation)"
        )

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient) -> None:
        """
        Test token refresh with invalid/malformed refresh token.

        Given: An invalid or malformed refresh token
        When: POST request is made to /api/v1/auth/refresh
        Then: The response should be 401 Unauthorized
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.refresh.token"},
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for invalid refresh token, "
            f"got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_refresh_token_revoked(
        self,
        client: AsyncClient,
        test_user: User,
        revoked_refresh_token: str,
    ) -> None:
        """
        Test token refresh with a revoked refresh token.

        Given: A refresh token that has been revoked (e.g., user logged out)
        When: POST request is made to /api/v1/auth/refresh with the revoked token
        Then: The response should be 401 Unauthorized
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": revoked_refresh_token},
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for revoked refresh token, "
            f"got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_refresh_token_expired(
        self,
        client: AsyncClient,
        test_user: User,
        expired_refresh_token: str,
    ) -> None:
        """
        Test token refresh with an expired refresh token.

        Given: A refresh token that has passed its expiration date
        When: POST request is made to /api/v1/auth/refresh
        Then: The response should be 401 Unauthorized
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": expired_refresh_token},
        )

        assert response.status_code == 401, (
            f"Expected 401 Unauthorized for expired refresh token, "
            f"got {response.status_code}"
        )

        data = response.json()
        assert "detail" in data, "Error response should contain 'detail' field"

    @pytest.mark.asyncio
    async def test_refresh_token_missing(self, client: AsyncClient) -> None:
        """
        Test token refresh without providing a refresh token.

        Given: No refresh token is provided in the request
        When: POST request is made to /api/v1/auth/refresh
        Then: The response should be 422 Unprocessable Entity (validation error)
        """
        response = await client.post(
            "/api/v1/auth/refresh",
            json={},
        )

        assert response.status_code == 422, (
            f"Expected 422 for missing refresh token, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_token_user_inactive(
        self,
        client: AsyncClient,
        db_session,
        inactive_user: User,
    ) -> None:
        """
        Test token refresh when user has been deactivated.

        Given: A valid refresh token for a user who is now inactive
        When: POST request is made to /api/v1/auth/refresh
        Then: The response should be 401 Unauthorized
        """
        from app.core.security import create_refresh_token
        from app.models.refresh_token import RefreshToken
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4

        # Create a refresh token for the inactive user
        token_str = create_refresh_token(subject=str(inactive_user.id))
        refresh_token = RefreshToken(
            id=uuid4(),
            token=token_str,
            user_id=inactive_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(refresh_token)
        await db_session.commit()

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": token_str},
        )

        assert response.status_code == 401, (
            f"Expected 401 for inactive user refresh, got {response.status_code}"
        )

    @pytest.mark.asyncio
    async def test_refresh_token_not_in_database(
        self,
        client: AsyncClient,
        test_user: User,
    ) -> None:
        """
        Test token refresh with a validly signed token not in database.

        Given: A JWT that is correctly signed but not stored in the database
        When: POST request is made to /api/v1/auth/refresh
        Then: The response should be 401 Unauthorized
        """
        from app.core.security import create_refresh_token

        # Create a valid token but don't store it in the database
        orphan_token = create_refresh_token(subject=str(test_user.id))

        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": orphan_token},
        )

        assert response.status_code == 401, (
            f"Expected 401 for token not in database, got {response.status_code}"
        )


# =============================================================================
# TOKEN VALIDATION TESTS
# =============================================================================


class TestTokenValidation:
    """Additional tests for token validation edge cases."""

    @pytest.mark.asyncio
    async def test_access_token_has_correct_expiry(
        self,
        client: AsyncClient,
        test_user: User,
        login_data: dict,
    ) -> None:
        """
        Test that access tokens have the correct expiration time.

        Given: A user logs in successfully
        When: The access token is decoded
        Then: The token should expire in approximately 30 minutes
        """
        from app.core.security import decode_token

        response = await client.post(
            "/api/v1/auth/login",
            data=login_data,
        )

        assert response.status_code == 200

        data = response.json()
        token_data = decode_token(data["access_token"])

        # Token should have 'exp' claim
        assert "exp" in token_data, "Access token should have 'exp' claim"

        # Check expiration is approximately 30 minutes from now
        from datetime import datetime, timezone

        exp_timestamp = token_data["exp"]
        exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Allow 1 minute tolerance
        expected_expiry_min = 29  # minutes
        expected_expiry_max = 31  # minutes

        actual_expiry_minutes = (exp_datetime - now).total_seconds() / 60

        assert expected_expiry_min <= actual_expiry_minutes <= expected_expiry_max, (
            f"Access token expiry should be ~30 minutes, got {actual_expiry_minutes:.1f} minutes"
        )

    @pytest.mark.asyncio
    async def test_tokens_contain_user_id(
        self,
        client: AsyncClient,
        test_user: User,
        login_data: dict,
    ) -> None:
        """
        Test that tokens contain the user ID as subject.

        Given: A user logs in successfully
        When: The tokens are decoded
        Then: Both tokens should contain the user ID in the 'sub' claim
        """
        from app.core.security import decode_token

        response = await client.post(
            "/api/v1/auth/login",
            data=login_data,
        )

        assert response.status_code == 200

        data = response.json()

        # Decode and verify access token
        access_token_data = decode_token(data["access_token"])
        assert "sub" in access_token_data, "Access token should have 'sub' claim"
        assert access_token_data["sub"] == str(test_user.id), (
            f"Access token subject should be user ID, got {access_token_data['sub']}"
        )

        # Decode and verify refresh token
        refresh_token_data = decode_token(data["refresh_token"])
        assert "sub" in refresh_token_data, "Refresh token should have 'sub' claim"
        assert refresh_token_data["sub"] == str(test_user.id), (
            f"Refresh token subject should be user ID, got {refresh_token_data['sub']}"
        )
