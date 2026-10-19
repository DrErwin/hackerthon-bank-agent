"""Scenario-05 subscription / auto-debit module."""

from .entry import SubscriptionEntry, register_subscription, subscription_factory
from .manifest import MANIFEST
from .ports import CancellationPlan, ExecutionOutcome, GateAnswer, SubscriptionPorts
from .reads import PRIVATE_TOOLS, GatewaySubscriptionPorts
from .service import SubscriptionService

__all__ = [
    "MANIFEST", "PRIVATE_TOOLS", "SubscriptionEntry", "SubscriptionService", "SubscriptionPorts",
    "CancellationPlan", "ExecutionOutcome", "GateAnswer", "GatewaySubscriptionPorts",
    "register_subscription", "subscription_factory",
]
