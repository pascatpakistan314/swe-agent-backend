"""
Updated Main Graph - Enhanced with Terminal Control and Linear Execution
"""

from agent.architect.graph_enhanced import swe_architect

from agent.common.entities import ImplementationPlan
from agent.developer.graph import swe_developer
from agent.integrated_graph import integrated_swe_agent, IntegratedSWEState, ExecutionMode
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages, StateGraph, START, END
from typing import Annotated, Optional

class AgentState(BaseModel):
    task_description: str = Field(..., description="The user's high-level task/goal")
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="The implementation plan to be executed")

class EnhancedAgentState(IntegratedSWEState):
    """Enhanced agent state with backward compatibility"""
    pass

def create_workflow_graph():
    """Create and return the original workflow graph (for backward compatibility)"""
    # Initialize graph
    graph_builder = StateGraph(AgentState)
    
    # Add nodes
    graph_builder.add_node("swe_architect", swe_architect)
    graph_builder.add_node("swe_developer", swe_developer)
    # Add edges for the workflow
    graph_builder.add_edge(START, "swe_architect")
    graph_builder.add_edge("swe_architect", "swe_developer")
    graph_builder.add_edge("swe_developer", END)

    return graph_builder

def create_enhanced_workflow_graph():
    """Create and return the enhanced workflow graph with terminal control"""
    return integrated_swe_agent

# Original agent (for backward compatibility)
swe_agent = create_workflow_graph().compile().with_config({"tags":["agent-v1"], "recursion_limit": 2000})

# Enhanced agent with terminal control (recommended)
enhanced_swe_agent = create_enhanced_workflow_graph()

# Convenience function for running enhanced agent
def run_enhanced_agent(task_description: str, workspace_dir: str = "./workspace_repo", parallel: bool = False):
    """
    Run the enhanced SWE agent with terminal control
    
    Args:
        task_description: Description of the task to implement
        workspace_dir: Directory for the workspace
        parallel: Whether to use parallel execution mode
    
    Returns:
        Execution result dictionary
    """
    execution_mode = ExecutionMode.PARALLEL if parallel else ExecutionMode.SEQUENTIAL
    
    initial_state = EnhancedAgentState(
        task_description=task_description,
        workspace_dir=workspace_dir,
        execution_mode=execution_mode,
        use_existing_components=True,
        force_terminal_setup=True
    )
    
    return enhanced_swe_agent.invoke(initial_state)

# Default export for backward compatibility
__all__ = [
    "swe_agent",           # Original agent
    "enhanced_swe_agent",  # Enhanced agent 
    "run_enhanced_agent",  # Convenience function
    "AgentState",          # Original state
    "EnhancedAgentState"   # Enhanced state
]
