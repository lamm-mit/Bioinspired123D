from __future__ import annotations
from langgraph.graph import StateGraph, END

from .state import DesignState

def build_bio3d_agent(
    node_bio3d,
    node_vlm,
    node_codefixer,
    node_codedesigner,
):
    graph = StateGraph(DesignState)
    graph.add_node("bio3d", node_bio3d)
    graph.add_node("vlm", node_vlm)
    graph.add_node("codefixer", node_codefixer)
    graph.add_node("codedesigner", node_codedesigner)

    graph.add_edge("bio3d", "vlm")

    def after_vlm(state: DesignState):
        if state.get("approved", False):
            return END
        if state.get("blender_status") != "success":
            return "codefixer"
        if int(state.get("iteration_count", 0)) >= 3:
            state["final_result"] = state.get("render_path") or state.get("blender_code_fixed")
            return END
        return "codedesigner"

    def after_codefixer(state: DesignState):
        return "vlm" if state.get("fix_success") else END

    graph.add_conditional_edges("vlm", after_vlm, {"codefixer": "codefixer", "codedesigner": "codedesigner", END: END})
    graph.add_conditional_edges("codefixer", after_codefixer, {"vlm": "vlm", END: END})
    graph.add_edge("codedesigner", "vlm")

    graph.set_entry_point("bio3d")
    return graph.compile()


def after_vlm(state: DesignState):
    if state.get("approved", False):
        return END
    if state.get("blender_status") != "success":
        return "codefixer"
    if int(state.get("iteration_count", 0)) >= 3:
        state["final_result"] = state.get("render_path") or state.get("blender_code_fixed")
        return END
    return "codedesigner"

def after_codefixer(state: DesignState):
    return "vlm" if state.get("fix_success") else END