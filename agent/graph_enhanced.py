"""Enhanced graph implementation that properly integrates with existing architecture"""

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from typing import Annotated, Optional, List
import os
from pydantic import BaseModel, Field
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.graph import add_messages, StateGraph, START, END

from agent.architect.graph_enhanced import swe_architect

from agent.developer.graph import swe_developer
from agent.common.entities import ImplementationPlan

class EnhancedAgentState(BaseModel):
    """Enhanced state that extends the original state"""
    # Keep original fields
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages]
    implementation_plan: Optional[ImplementationPlan] = Field(None)
    
    # Add quality assurance fields
    needs_testing: bool = Field(True, description="Whether to run tests")
    needs_review: bool = Field(True, description="Whether to run code review")
    quality_threshold: float = Field(0.8, description="Minimum quality score")
    
    # Results tracking
    implementation_complete: bool = Field(False)
    quality_passed: bool = Field(False)
    feedback: List[str] = Field(default_factory=list)

def quality_check_node(state: EnhancedAgentState):
    """
    Quality check node that uses Claude to analyze the implementation
    instead of hardcoded tools
    """
    # Let Claude analyze the implementation quality
    from langchain_anthropic import ChatAnthropic
    
    llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Create a quality check prompt
    quality_prompt = f"""
    You are a quality assurance expert. Analyze the following implementation plan and determine:
    1. Whether comprehensive testing is needed
    2. What types of tests would be most valuable
    3. Key quality metrics to verify
    
    Implementation Plan: {state.implementation_plan}
    
    Provide a brief quality assessment and recommendations.
    """
    
    response = llm.invoke(quality_prompt)
    
    # Simple quality check (in real implementation, parse response properly)
    quality_passed = "acceptable" in response.content.lower() or "good" in response.content.lower()
    
    return {
        "quality_passed": quality_passed,
        "feedback": [response.content],
        "implementation_research_scratchpad": [
            AIMessage(content=f"Quality Assessment: {response.content}")
        ]
    }

def create_adaptive_workflow():
    """
    Create a workflow that adapts based on the task complexity
    Rather than forcing all tasks through the same pipeline
    """
    
    graph_builder = StateGraph(EnhancedAgentState)
    
    # Core nodes from original
    graph_builder.add_node("architect", swe_architect)
    graph_builder.add_node("developer", swe_developer)
    
    # Adaptive quality node
    graph_builder.add_node("quality_check", quality_check_node)
    
    # Routing logic
    def route_after_development(state: EnhancedAgentState):
        """Intelligent routing based on implementation complexity"""
        if not state.implementation_plan:
            return END
            
        # Check if quality check is needed based on task complexity
        task_count = len(state.implementation_plan.tasks) if state.implementation_plan else 0
        
        if task_count == 0:
            return END
        elif task_count == 1 and not state.needs_testing:
            # Simple task, skip quality check
            return END
        else:
            # Complex task, do quality check
            return "quality_check"
    
    def route_after_quality(state: EnhancedAgentState):
        """Route based on quality results"""
        if state.quality_passed:
            return END
        else:
            # Need to fix issues
            return "developer"
    
    # Build graph
    graph_builder.add_edge(START, "architect")
    graph_builder.add_edge("architect", "developer")
    
    graph_builder.add_conditional_edges(
        "developer",
        route_after_development,
        {
            "quality_check": "quality_check",
            END: END
        }
    )
    
    graph_builder.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {
            "developer": "developer",
            END: END
        }
    )
    
    return graph_builder

# Create the enhanced workflow
def build_enhanced_agent():
    """Build the enhanced agent with adaptive workflow"""
    builder = create_adaptive_workflow()
    return builder.compile().with_config({
        "tags": ["enhanced-adaptive"],
        "recursion_limit": 2000
    })

# Export the enhanced agent
enhanced_swe_agent = build_enhanced_agent()

# Keep compatibility with original
swe_agent = enhanced_swe_agent
