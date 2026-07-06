# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: AGPL-3.0
"""Unit tests for the external Connector HTTP client."""

import pytest

from openviking.connector import client as client_module
from openviking.connector.client import ConnectorClient
from openviking_cli.exceptions import InternalError


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.raise_for_status_called = False

    def raise_for_status(self):
        self.raise_for_status_called = True

    def json(self):
        return self._payload


class FakeAsyncClient:
    instances = []
    response_payload = {}

    def __init__(self, *, timeout):
        self.timeout = timeout
        self.posts = []
        FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, url, *, json, headers):
        response = FakeResponse(FakeAsyncClient.response_payload)
        self.posts.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "response": response,
            }
        )
        return response


@pytest.fixture(autouse=True)
def reset_fake_http_client(monkeypatch):
    FakeAsyncClient.instances = []
    FakeAsyncClient.response_payload = {}
    monkeypatch.setattr(client_module.httpx, "AsyncClient", FakeAsyncClient)


@pytest.mark.asyncio
async def test_submit_doc_add_builds_connector_payload_and_headers():
    FakeAsyncClient.response_payload = {
        "request_id": "request-1",
        "message": "success",
        "code": 0,
        "data": {"task_key": "connector-task-1"},
    }
    client = ConnectorClient(
        doc_add_url="https://connector.example/api/knowledge/doc/add",
        task_info_url="https://connector.example/api/task/info",
        account_id="main-account",
    )

    result = await client.submit_doc_add(
        add_type="tos",
        api_key="sk-test",
        tos_path="tos://bucket/key",
        path_prefix=["docs", "product"],
        include_child=False,
        extra_params={"parser": "pdf", "priority": "high", "api_key": "body-override"},
    )

    assert result == {"task_key": "connector-task-1"}
    http_client = FakeAsyncClient.instances[-1]
    assert http_client.timeout == 30.0
    assert http_client.posts == [
        {
            "url": "https://connector.example/api/knowledge/doc/add",
            "json": {
                "add_type": "tos",
                "backend": "ov",
                "include_child": False,
                "tos_path": "tos://bucket/key",
                "path_prefix": ["docs", "product"],
                "parser": "pdf",
                "priority": "high",
            },
            "headers": {
                "V-Account-Id": "main-account",
                "Authorization": "Bearer sk-test",
            },
            "response": http_client.posts[0]["response"],
        }
    ]
    assert http_client.posts[0]["response"].raise_for_status_called is True


@pytest.mark.asyncio
async def test_submit_doc_add_omits_optional_none_values_and_empty_account_header():
    FakeAsyncClient.response_payload = {"TaskKey": "connector-task-2"}
    client = ConnectorClient(
        doc_add_url="https://connector.example/doc/add",
        task_info_url="https://connector.example/task/info",
    )

    await client.submit_doc_add(
        add_type="tos",
        api_key="sk-test",
    )

    post = FakeAsyncClient.instances[-1].posts[0]
    assert post["headers"] == {"Authorization": "Bearer sk-test"}
    assert post["json"] == {
        "add_type": "tos",
        "backend": "ov",
        "include_child": True,
    }


@pytest.mark.asyncio
async def test_get_task_info_posts_task_key_to_tracker_endpoint():
    FakeAsyncClient.response_payload = {
        "request_id": "request-2",
        "message": "success",
        "code": 0,
        "data": {
            "Task": {
                "TaskKey": "connector-task-3",
                "Status": "running",
            }
        },
    }
    client = ConnectorClient(
        doc_add_url="https://connector.example/doc/add",
        task_info_url="https://tracker.example/api/task/info",
        account_id="main-account",
    )

    result = await client.get_task_info("connector-task-3", "sk-test")

    assert result == {"TaskKey": "connector-task-3", "Status": "running"}
    http_client = FakeAsyncClient.instances[-1]
    assert http_client.timeout == 10.0
    post = http_client.posts[0]
    assert post["url"] == "https://tracker.example/api/task/info"
    assert post["json"] == {"TaskKey": "connector-task-3"}
    assert post["headers"] == {
        "V-Account-Id": "main-account",
        "Authorization": "Bearer sk-test",
    }
    assert post["response"].raise_for_status_called is True


@pytest.mark.asyncio
async def test_connector_business_error_is_rejected():
    FakeAsyncClient.response_payload = {
        "request_id": "request-3",
        "message": "permission denied",
        "code": 1003,
        "data": {},
    }
    client = ConnectorClient(
        doc_add_url="https://connector.example/doc/add",
        task_info_url="https://connector.example/task/info",
        account_id="main-account",
    )

    with pytest.raises(InternalError, match=r"code=1003.*permission denied"):
        await client.submit_doc_add(
            add_type="tos",
            api_key="sk-test",
            tos_path="bucket/key",
        )
