"""Agent public facade aligned with the canonical Voodoo runtime lifecycle.

Sprint 24.2 keeps the historical implementation intact in ``agent_legacy``
while the public ``Agent`` adds runtime-truth guarantees: canonical Execution
failure propagation, execution lineage, and agent-scoped episodic memory.
"""

from voodoo.ai.agent_legacy import AgentEvent, AgentRun, AgentState
from voodoo.ai.agent_runtime_truth import RuntimeTruthAgent

Agent = RuntimeTruthAgent

__all__ = ["Agent", "AgentRun", "AgentEvent"]
