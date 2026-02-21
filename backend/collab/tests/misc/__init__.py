"""
Collab test utilities.

Provides helper functions for setting up two-tier access in tests.
"""

import json

from asgiref.sync import sync_to_async

from pages.tests.factories import PageFactory, ProjectFactory
from users.tests.factories import OrgFactory, OrgMemberFactory, UserFactory


async def assert_ws_rejected(communicator, expected_close_code=None, expected_error_code=None):
    """
    Assert that a WebSocket connection is rejected after initial accept.

    The WebSocket consumer pattern accepts the connection briefly, sends an error
    message, then closes with a code. This allows clients to receive the close code.

    Args:
        communicator: WebsocketCommunicator instance after connect() was called
        expected_close_code: Expected WebSocket close code (e.g., 4003 for access denied)
        expected_error_code: Expected error code in the error message JSON (e.g., "access_denied")

    Returns:
        Tuple of (error_message, close_code) for additional assertions
    """
    # Receive the error message
    response = await communicator.receive_from(timeout=2)
    error_data = json.loads(response)
    assert error_data.get("type") == "error", f"Expected error message, got: {error_data}"

    if expected_error_code:
        assert (
            error_data.get("code") == expected_error_code
        ), f"Expected error code {expected_error_code}, got: {error_data.get('code')}"

    # Receive the close message
    close_message = await communicator.receive_output(timeout=2)
    assert close_message["type"] == "websocket.close", f"Expected close, got: {close_message}"

    actual_close_code = close_message.get("code", 1000)
    if expected_close_code:
        assert (
            actual_close_code == expected_close_code
        ), f"Expected close code {expected_close_code}, got: {actual_close_code}"

    return error_data, actual_close_code


async def create_user_with_org_and_project():
    """
    Create a user with org membership and project for two-tier access tests.

    Returns:
        Tuple of (user, org, project)
    """
    org = await sync_to_async(OrgFactory.create)()
    user = await sync_to_async(UserFactory.create)()
    await sync_to_async(OrgMemberFactory.create)(org=org, user=user)
    project = await sync_to_async(ProjectFactory.create)(org=org, creator=user)
    return user, org, project


async def create_page_with_access(user, org, project, **kwargs):
    """
    Create a page within the user's project.

    Args:
        user: User who will be the creator
        org: Org the project belongs to
        project: Project the page belongs to
        **kwargs: Additional arguments for PageFactory

    Returns:
        Page instance
    """
    return await sync_to_async(PageFactory.create)(project=project, creator=user, **kwargs)


async def add_project_editor(project, user):
    """
    Add a user as a project editor (Tier 2 access).

    Args:
        project: Project to add editor to
        user: User to add as editor
    """
    await sync_to_async(project.editors.add)(user)
