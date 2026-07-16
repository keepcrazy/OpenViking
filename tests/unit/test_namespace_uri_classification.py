# Copyright (c) 2026 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
"""Tests for shared Viking URI namespace/content classification."""

from openviking.core.namespace import (
    canonical_agent_resources_root,
    canonicalize_uri,
    classify_uri,
    context_type_for_uri,
    is_accessible,
    owner_space_for_uri,
)
from openviking.server.identity import AccountNamespacePolicy, RequestContext, Role
from openviking_cli.session.user_id import UserIdentifier


def test_context_type_for_uri_uses_path_segments():
    assert context_type_for_uri("viking://user/alice/memories/entities/m1.md") == "memory"
    assert context_type_for_uri("viking://user/memories/entities/m1.md") == "memory"
    assert context_type_for_uri("viking://agent/memories/cases/m1.md") == "memory"
    assert context_type_for_uri("viking://agent/skills/demo") == "skill"
    assert context_type_for_uri("viking://agent/default/memories/cases/m1.md") == "memory"
    assert (
        context_type_for_uri("viking://user/alice/agent/default/memories/entities/m1.md")
        == "memory"
    )
    assert context_type_for_uri("viking://agent/default/skills/demo") == "skill"
    assert context_type_for_uri("viking://agent/default/user/alice/skills/demo") == "skill"
    assert context_type_for_uri("viking://resources/memories-report.md") == "resource"
    assert context_type_for_uri("viking://agent/default/resources/skills-report.md") == "resource"


def test_exact_memory_and_skill_root_detection():
    assert classify_uri("viking://user/alice/memories/preferences/prefs.md").is_memory
    assert classify_uri("viking://user/alice/memories").is_memory_root
    assert classify_uri("viking://user/memories").is_memory_root
    assert not classify_uri("viking://user/alice/memories/preferences").is_memory_root

    assert classify_uri("viking://agent/default/skills/demo/SKILL.md").is_skill
    assert classify_uri("viking://agent/default/skills/demo").is_skill_root
    assert classify_uri("viking://agent/skills/demo").is_skill_root
    assert not classify_uri("viking://agent/default/skills").is_skill_root
    assert not classify_uri("viking://agent/default/skills/demo/assets").is_skill_root


def test_owner_space_for_uri_respects_namespace_policy():
    ctx = RequestContext(
        user=UserIdentifier(account_id="acct", user_id="alice", agent_id="planner"),
        role=Role.ROOT,
        namespace_policy=AccountNamespacePolicy(
            isolate_user_scope_by_agent=True,
            isolate_agent_scope_by_user=True,
        ),
    )

    assert owner_space_for_uri("viking://user/alice/agent/planner/memories", ctx) == (
        "alice/agent/planner"
    )
    assert owner_space_for_uri("viking://agent/planner/user/alice/skills/demo", ctx) == (
        "planner/user/alice"
    )
    assert owner_space_for_uri("viking://resources/readme.md", ctx) == ""


def test_agent_resource_shorthand_uses_current_agent_namespace():
    ctx = RequestContext(
        user=UserIdentifier(account_id="acct", user_id="alice", agent_id="planner"),
        role=Role.USER,
        namespace_policy=AccountNamespacePolicy(isolate_agent_scope_by_user=True),
    )

    assert canonical_agent_resources_root(ctx) == (
        "viking://agent/planner/user/alice/resources"
    )
    assert canonicalize_uri("viking://agent/resources/project/readme.md", ctx=ctx) == (
        "viking://agent/planner/user/alice/resources/project/readme.md"
    )
    assert context_type_for_uri(canonical_agent_resources_root(ctx)) == "resource"


def test_agent_resources_are_not_accessible_to_another_agent():
    planner_ctx = RequestContext(
        user=UserIdentifier(account_id="acct", user_id="alice", agent_id="planner"),
        role=Role.USER,
        namespace_policy=AccountNamespacePolicy(isolate_agent_scope_by_user=False),
    )
    writer_ctx = RequestContext(
        user=UserIdentifier(account_id="acct", user_id="alice", agent_id="writer"),
        role=Role.USER,
        namespace_policy=AccountNamespacePolicy(isolate_agent_scope_by_user=False),
    )
    planner_resource = "viking://agent/planner/resources/private.md"

    assert is_accessible(planner_resource, planner_ctx)
    assert not is_accessible(planner_resource, writer_ctx)
    assert is_accessible("viking://resources/shared.md", writer_ctx)
