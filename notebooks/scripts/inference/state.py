from __future__ import annotations
from typing import TypedDict, Optional, Dict, Any

class DesignState(TypedDict, total=False):
    design_prompt: Optional[str]
    blender_code: Optional[str]
    blender_code_fixed: Optional[str]
    render_path: Optional[str]
    blender_status: Optional[str]
    error_snippet: Optional[str]

    vlm_feedback: Optional[str]
    vlm_analysis: Optional[Dict[str, Any]]
    approved: bool

    fix_attempts_used: Optional[int]
    fix_success: Optional[bool]

    render_subdir_wsl: Optional[str]
    last_node: Optional[str]
    iteration_count: Optional[int]
    final_result: Optional[str]
    prev_to_vlm: Optional[str]
