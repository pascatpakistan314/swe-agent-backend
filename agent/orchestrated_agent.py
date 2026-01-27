"""
Main Orchestrated SWE-Agent with Multi-Agent Architecture and GitHub Integration
Fixed version that properly imports existing modules
"""

from agent.architect.graph_enhanced import swe_architect
from agent.developer.graph import swe_developer  
from agent.tester.graph import swe_tester
from agent.reviewer.graph import swe_reviewer
from agent.orchestrator.multi_agent_orchestrator import MultiAgentOrchestrator, orchestration_tools
from agent.integrations.github_integration import GitHubPRHandler, github_integration_tools
from agent.tools.multi_language_sandbox import multi_language_sandbox_tools
from agent.tools.multi_language_builder import multi_language_build_tools
from agent.tools.terminal import terminal_tools
from agent.tools.agents_md import agents_md_tools

from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Annotated
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
import asyncio
import os

class OrchestratedAgentState(BaseModel):
    """Enhanced state for orchestrated multi-agent system"""
    
    # Core fields
    task_description: str = Field(..., description="The main task to accomplish")
    implementation_research_scratchpad: Annotated[list[AnyMessage], add_messages] = Field(default_factory=list)
    
    # Orchestration fields
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)
    current_agent: Optional[str] = Field(None)
    agent_results: Dict[str, Any] = Field(default_factory=dict)
    
    # GitHub integration
    pr_number: Optional[int] = Field(None)
    issue_number: Optional[int] = Field(None)
    repo_name: Optional[str] = Field(None)
    
    # Execution context
    workspace_dir: str = Field(default="./workspace_repo")
    workflow_mode: str = Field(default="orchestrated")  # orchestrated, single, github
    
    # Results
    final_result: Optional[Dict[str, Any]] = Field(None)
    success: bool = Field(False)

def create_orchestrated_agent():
    """
    Create the main orchestrated agent with all modern features:
    - Multi-agent orchestration (like Devin)
    - GitHub PR/Issue handling
    - Multi-language support
    - AGENTS.md context
    - Sandboxed execution
    """
    
    # Initialize graph
    graph_builder = StateGraph(OrchestratedAgentState)
    
    # Initialize orchestrator
    orchestrator = MultiAgentOrchestrator()
    
    # Initialize GitHub handler only if token exists
    github_handler = None
    try:
        if os.getenv("GITHUB_TOKEN"):
            github_handler = GitHubPRHandler()
    except Exception as e:
        print(f"Warning: Could not initialize GitHub handler: {e}")
    
    # Define nodes
    def analyze_task(state: OrchestratedAgentState):
        """Analyze and classify the main task"""
        
        # Check if it's a GitHub-related task
        if state.pr_number or state.issue_number:
            return {
                "workflow_mode": "github",
                "current_agent": "github_handler"
            }
        
        # Check task complexity
        keywords = state.task_description.lower() if state.task_description else ""
        
        if any(word in keywords for word in ["simple", "quick", "small", "minor"]):
            return {
                "workflow_mode": "single",
                "current_agent": "developer"
            }
        else:
            return {
                "workflow_mode": "orchestrated",
                "current_agent": "orchestrator"
            }
    
    async def orchestrate_task(state: OrchestratedAgentState):
        """Orchestrate complex tasks using multiple agents"""
        
        print(f"\n🎯 Orchestrating: {state.task_description}")
        
        # Use the orchestrator to decompose and execute
        result = await orchestrator.orchestrate(state.task_description)
        
        return {
            "agent_results": result,
            "subtasks": result.get("results", []),
            "final_result": result,
            "success": result.get("subtasks_completed", 0) > 0
        }
    
    async def handle_github(state: OrchestratedAgentState):
        """Handle GitHub-specific tasks"""
        
        if not github_handler:
            return {
                "success": False,
                "final_result": {"error": "GitHub integration not configured"}
            }
        
        if state.pr_number and state.repo_name:
            # Handle PR review
            repo = github_handler.github.get_repo(state.repo_name)
            pr = repo.get_pull(state.pr_number)
            
            analysis = await github_handler.analyze_pr(pr)
            success = await github_handler.submit_pr_review(
                state.repo_name,
                state.pr_number,
                analysis["review"]
            )
            
            return {
                "success": success,
                "final_result": analysis,
                "agent_results": {"github_review": analysis}
            }
        
        elif state.issue_number and state.repo_name:
            # Handle issue
            repo = github_handler.github.get_repo(state.repo_name)
            issue = repo.get_issue(state.issue_number)
            
            result = await github_handler.handle_issue(issue)
            
            return {
                "success": True,
                "final_result": result,
                "agent_results": {"github_issue": result}
            }
        
        return {
            "success": False,
            "final_result": {"error": "No GitHub task specified"}
        }
    
    def execute_single_agent(state: OrchestratedAgentState):
        """Execute with a single specialized agent"""
        
        agent_map = {
            "architect": swe_architect,
            "developer": swe_developer,
            "tester": swe_tester,
            "reviewer": swe_reviewer
        }
        
        agent = agent_map.get(state.current_agent, swe_developer)
        
        # Prepare input based on agent requirements
        agent_input = {
            "task_description": state.task_description,
            "implementation_research_scratchpad": state.implementation_research_scratchpad
        }
        
        # Some agents may need additional fields
        if state.current_agent == "developer":
            # Developer needs implementation_plan from architect
            # For single agent mode, we'll use architect first
            architect_result = swe_architect.invoke(agent_input)
            if architect_result and architect_result.get("implementation_plan"):
                agent_input["implementation_plan"] = architect_result["implementation_plan"]
        
        result = agent.invoke(agent_input)
        
        return {
            "agent_results": {state.current_agent: result},
            "final_result": result,
            "success": True
        }
    
    def synthesize_results(state: OrchestratedAgentState):
        """Synthesize results from all agents"""
        
        synthesis = {
            "task": state.task_description,
            "workflow_mode": state.workflow_mode,
            "agents_used": list(state.agent_results.keys()) if state.agent_results else [],
            "subtasks_completed": len(state.subtasks),
            "success": state.success,
            "summary": "Task completed successfully" if state.success else "Task failed or incomplete"
        }
        
        # Add specific results based on workflow
        if state.workflow_mode == "github":
            synthesis["github_action"] = state.agent_results.get("github_review") or state.agent_results.get("github_issue")
        elif state.workflow_mode == "orchestrated":
            synthesis["orchestration_details"] = state.final_result
        else:
            synthesis["agent_result"] = state.final_result
        
        return {
            "final_result": synthesis
        }
    
    # Add nodes to graph
    graph_builder.add_node("analyze_task", analyze_task)
    graph_builder.add_node("orchestrate_task", orchestrate_task)
    graph_builder.add_node("handle_github", handle_github)
    graph_builder.add_node("execute_single_agent", execute_single_agent)
    graph_builder.add_node("synthesize_results", synthesize_results)
    
    # Define routing logic
    def route_after_analysis(state: OrchestratedAgentState):
        """Route based on workflow mode"""
        if state.workflow_mode == "github":
            return "handle_github"
        elif state.workflow_mode == "orchestrated":
            return "orchestrate_task"
        else:
            return "execute_single_agent"
    
    # Add edges
    graph_builder.add_edge(START, "analyze_task")
    graph_builder.add_conditional_edges(
        "analyze_task",
        route_after_analysis,
        {
            "handle_github": "handle_github",
            "orchestrate_task": "orchestrate_task",
            "execute_single_agent": "execute_single_agent"
        }
    )
    graph_builder.add_edge("orchestrate_task", "synthesize_results")
    graph_builder.add_edge("handle_github", "synthesize_results")
    graph_builder.add_edge("execute_single_agent", "synthesize_results")
    graph_builder.add_edge("synthesize_results", END)
    
    # Compile graph
    return graph_builder.compile()

# Create the main orchestrated agent
orchestrated_swe_agent = create_orchestrated_agent()

# Enhanced tool node with ALL tools
all_tools = (
    orchestration_tools +
    github_integration_tools +
    multi_language_sandbox_tools +
    multi_language_build_tools +
    terminal_tools +
    agents_md_tools
)

enhanced_tool_node = ToolNode(all_tools, messages_key="implementation_research_scratchpad")

# Export main agent
__all__ = [
    "orchestrated_swe_agent",
    "OrchestratedAgentState",
    "all_tools",
    "enhanced_tool_node"
]

# Quick execution function that matches the interface of the basic agent
def execute_task(
    task: str,
    pr_number: Optional[int] = None,
    issue_number: Optional[int] = None,
    repo_name: Optional[str] = None,
    workspace: str = "./workspace_repo"
) -> Dict[str, Any]:
    """
    Execute a task with the orchestrated agent
    
    Args:
        task: Task description
        pr_number: GitHub PR number (if applicable)
        issue_number: GitHub issue number (if applicable)
        repo_name: GitHub repository name (owner/repo)
        workspace: Working directory
    
    Returns:
        Execution results
    """
    
    # Create state
    state = {
        "task_description": task,
        "implementation_research_scratchpad": [],
        "pr_number": pr_number,
        "issue_number": issue_number,
        "repo_name": repo_name,
        "workspace_dir": workspace
    }
    
    # Run agent
    if asyncio.iscoroutinefunction(orchestrated_swe_agent.invoke):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                orchestrated_swe_agent.ainvoke(state)
            )
        finally:
            loop.close()
    else:
        result = orchestrated_swe_agent.invoke(state)
    
    return result.get("final_result", {})

# Make it compatible with the basic agent interface
class OrchestratedAgentWrapper:
    """Wrapper to make orchestrated agent compatible with basic agent interface"""
    
    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the orchestrated agent with basic agent interface"""
        task_description = inputs.get("task_description", "")
        
        # Run the orchestrated agent
        return execute_task(task_description)
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Async invoke for compatibility"""
        return self.invoke(inputs)
    
    def with_config(self, config: Dict[str, Any]):
        """For compatibility with config chains"""
        return self

# Create a compatible instance
orchestrated_swe_agent_compatible = OrchestratedAgentWrapper()

# CLI integration
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python orchestrated_agent.py 'task description'")
        sys.exit(1)
    
    task = sys.argv[1]
    result = execute_task(task)
    
    print("\n" + "="*50)
    print("ORCHESTRATED AGENT RESULTS")
    print("="*50)
    print(f"Task: {result.get('task', 'N/A')}")
    print(f"Workflow Mode: {result.get('workflow_mode', 'N/A')}")
    print(f"Agents Used: {', '.join(result.get('agents_used', []))}")
    print(f"Success: {result.get('success', False)}")
    print(f"Summary: {result.get('summary', 'N/A')}")
    print("="*50)
