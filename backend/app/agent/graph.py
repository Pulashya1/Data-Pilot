"""LangGraph wiring: ingest -> understand -> plan -> execute_step (loop) -> summarize
(MASTER_PROMPT.md §5.1, §12 Phase 3)."""

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agent import nodes
from app.agent.checkpoint import get_checkpointer
from app.agent.state import AgentState


def _build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("ingest", nodes.ingest_node)
    graph.add_node("understand", nodes.understand_node)
    graph.add_node("plan", nodes.plan_node)
    graph.add_node("execute_step", nodes.execute_step_node)
    graph.add_node("summarize", nodes.summarize_node)

    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "understand")
    graph.add_edge("understand", "plan")
    graph.add_conditional_edges(
        "plan", nodes.route_after_step, {"continue": "execute_step", "done": "summarize"}
    )
    graph.add_conditional_edges(
        "execute_step", nodes.route_after_step, {"continue": "execute_step", "done": "summarize"}
    )
    graph.add_edge("summarize", END)
    return graph


def compile_graph() -> CompiledStateGraph:
    return _build_graph().compile(checkpointer=get_checkpointer())
