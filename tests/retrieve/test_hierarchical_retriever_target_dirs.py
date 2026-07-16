# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: AGPL-3.0

"""Hierarchical retriever target_directories tests."""

import pytest

from openviking.core.namespace import canonical_agent_resources_root
from openviking.retrieve.hierarchical_retriever import HierarchicalRetriever
from openviking.server.identity import RequestContext, Role
from openviking_cli.retrieve.types import ContextType, TypedQuery
from openviking_cli.session.user_id import UserIdentifier


class DummyStorage:
    """Minimal storage stub to capture search filters."""

    def __init__(self) -> None:
        self.collection_name = "context"
        self.global_search_calls = []
        self.child_search_calls = []

    async def collection_exists_bound(self) -> bool:
        return True

    async def search_global_roots_in_tenant(
        self,
        ctx,
        query_vector=None,
        sparse_query_vector=None,
        context_type=None,
        target_directories=None,
        extra_filter=None,
        limit: int = 10,
    ):
        self.global_search_calls.append(
            {
                "ctx": ctx,
                "query_vector": query_vector,
                "sparse_query_vector": sparse_query_vector,
                "context_type": context_type,
                "target_directories": target_directories,
                "extra_filter": extra_filter,
                "limit": limit,
            }
        )
        return []

    async def search_children_in_tenant(
        self,
        ctx,
        parent_uri: str,
        query_vector=None,
        sparse_query_vector=None,
        context_type=None,
        target_directories=None,
        extra_filter=None,
        limit: int = 10,
    ):
        self.child_search_calls.append(
            {
                "ctx": ctx,
                "parent_uri": parent_uri,
                "query_vector": query_vector,
                "sparse_query_vector": sparse_query_vector,
                "context_type": context_type,
                "target_directories": target_directories,
                "extra_filter": extra_filter,
                "limit": limit,
            }
        )
        return []


def test_resource_roots_include_account_and_current_agent():
    retriever = HierarchicalRetriever(storage=DummyStorage(), embedder=None, rerank_config=None)
    ctx = RequestContext(user=UserIdentifier("acc1", "user1", "agent1"), role=Role.USER)

    assert retriever._get_root_uris_for_type(ContextType.RESOURCE, ctx) == [
        "viking://resources",
        canonical_agent_resources_root(ctx),
    ]


@pytest.mark.asyncio
async def test_retrieve_honors_target_directories_scope_filter():
    target_uri = "viking://resources/foo"
    storage = DummyStorage()
    retriever = HierarchicalRetriever(storage=storage, embedder=None, rerank_config=None)
    ctx = RequestContext(user=UserIdentifier("acc1", "user1", "agent1"), role=Role.USER)

    query = TypedQuery(
        query="test",
        context_type=ContextType.RESOURCE,
        intent="",
        target_directories=[target_uri],
    )

    result = await retriever.retrieve(query, ctx=ctx, limit=3)

    assert result.searched_directories == [target_uri]
    assert storage.global_search_calls
    assert storage.global_search_calls[0]["target_directories"] == [target_uri]
    assert storage.child_search_calls
    assert storage.child_search_calls[0]["target_directories"] == [target_uri]
    assert storage.child_search_calls[0]["parent_uri"] == target_uri
