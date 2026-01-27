"""
Enhanced Graph Integration - Connects the linear agent with existing components
"""

import os
import asyncio
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import Field

# Import existing components
from agent.architect.graph_enhanced import swe_architect

from agent.developer.graph import swe_developer
from agent.enhanced_linear_agent import (
    EnhancedAgentState, 
    EnhancedLinearAgent,
    ExecutionMode,
    EXECUTION_PHASES
)

# Import tools
from agent.tools.terminal import terminal_tools, get_terminal_manager
from agent.tools.search import search_tools
from agent.tools.codemap import codemap_tools
from agent.tools.write import get_files_structure

load_dotenv()

class IntegratedSWEState(EnhancedAgentState):
    """Extended state that integrates with existing SWE components"""
    
    # Add compatibility fields for existing components
    implementation_research_scratchpad: List[AnyMessage] = Field(default_factory=list)
    scratchpad: List[AnyMessage] = Field(default_factory=list)
    messages: List[AnyMessage] = Field(default_factory=list)
    
    # Execution control
    use_existing_components: bool = True
    force_terminal_setup: bool = True

class IntegratedSWEAgent:
    """Integrated SWE Agent that combines enhanced linear execution with existing components"""
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = workspace_dir
        self.linear_agent = EnhancedLinearAgent(workspace_dir)
        self.terminal_manager = get_terminal_manager()
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )

def enhanced_initialization(state: IntegratedSWEState):
    """Enhanced initialization with terminal setup"""
    
    print("🚀 Enhanced SWE Agent - Terminal Integration Mode")
    print(f"Task: {state.task_description}")
    print(f"Workspace: {state.workspace_dir if hasattr(state, 'workspace_dir') else './workspace_repo'}")
    
    # Force terminal setup
    agent = IntegratedSWEAgent()
    
    # Set up terminal session immediately
    terminal_manager = get_terminal_manager()
    main_session = terminal_manager.create_session("main")
    
    # Navigate to workspace and verify
    workspace_path = getattr(state, 'workspace_dir', './workspace_repo')
    os.makedirs(workspace_path, exist_ok=True)
    
    cd_result = terminal_manager.execute_command(f"cd {workspace_path}", "main")
    ls_result = terminal_manager.execute_command("ls -la", "main")
    pwd_result = terminal_manager.execute_command("pwd", "main")
    
    # Log terminal setup
    terminal_setup_log = {
        "session_created": main_session,
        "cd_result": cd_result,
        "ls_result": ls_result,
        "pwd_result": pwd_result,
        "workspace_verified": True
    }
    
    print("✅ Terminal session established and workspace verified")
    print(f"📁 Working directory: {pwd_result.get('output', '').strip()}")
    
    # Update state with terminal information
    state.terminal_sessions = {"main": main_session}
    state.environment_setup = True
    state.current_phase = "environment_setup"
    
    # Add terminal setup to scratchpad for existing components
    terminal_message = AIMessage(
        content=f"Terminal setup completed. Session ID: {main_session['session_id']}, "
               f"Workspace: {workspace_path}, "
               f"Current directory: {pwd_result.get('output', '').strip()}"
    )
    
    return {
        "terminal_sessions": state.terminal_sessions,
        "environment_setup": True,
        "current_phase": "dependency_management",
        "implementation_research_scratchpad": [terminal_message],
        "scratchpad": [terminal_message],
        "messages": [
            HumanMessage(content=f"Set up development environment for: {state.task_description}"),
            terminal_message
        ]
    }

def dependency_management(state: IntegratedSWEState):
    """Enhanced dependency management with terminal integration"""
    
    print("📦 Managing dependencies with terminal integration...")
    
    terminal_manager = get_terminal_manager()
    
    # Check what type of project we're dealing with
    workspace_path = getattr(state, 'workspace_dir', './workspace_repo')
    
    # Get project structure
    structure_result = get_files_structure.invoke({"directory": workspace_path})
    
    # Check for different project types and their dependencies
    dependency_commands = []
    project_type = "unknown"
    
    # Python project detection and setup
    if any(f in structure_result for f in ["requirements.txt", "setup.py", "pyproject.toml", ".py"]):
        project_type = "python"
        dependency_commands.extend([
            "python --version",
            "pip --version",
        ])
        
        if "requirements.txt" in structure_result:
            dependency_commands.append("pip install -r requirements.txt")
        elif "pyproject.toml" in structure_result:
            dependency_commands.extend([
                "pip install poetry",
                "poetry install"
            ])
    
    # Node.js project detection
    elif "package.json" in structure_result:
        project_type = "nodejs"
        dependency_commands.extend([
            "node --version",
            "npm --version",
            "npm install"
        ])
    
    # Generic setup if no specific project type detected
    else:
        project_type = "generic"
        dependency_commands.extend([
            "python --version",
            "pip --version",
            "node --version"
        ])
        
        # Create basic Python project structure
        basic_files = {
            "requirements.txt": "requests\npython-dotenv\n",
            "main.py": "#!/usr/bin/env python3\n\"\"\"\nMain application file\n\"\"\"\n\nif __name__ == '__main__':\n    print('Hello, World!')\n"
        }
        
        for filename, content in basic_files.items():
            filepath = os.path.join(workspace_path, filename)
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write(content)
        
        dependency_commands.append("pip install -r requirements.txt")
    
    # Execute dependency commands
    execution_results = []
    for command in dependency_commands:
        print(f"🔧 Executing: {command}")
        result = terminal_manager.execute_command(command, "main")
        execution_results.append({
            "command": command,
            "result": result
        })
        
        if result.get("success", False):
            print(f"✅ {command} - Success")
        else:
            print(f"⚠️ {command} - Warning/Error: {result.get('error', 'Unknown issue')}")
    
    # Update state
    state.dependencies_installed = True
    state.current_phase = "architecture_planning"
    
    dependency_message = AIMessage(
        content=f"Dependency management completed for {project_type} project. "
               f"Executed {len(dependency_commands)} commands. "
               f"Results: {len([r for r in execution_results if r['result'].get('success', False)])} successful, "
               f"{len([r for r in execution_results if not r['result'].get('success', False)])} warnings/errors."
    )
    
    return {
        "dependencies_installed": True,
        "current_phase": "architecture_planning",
        "implementation_research_scratchpad": [dependency_message],
        "scratchpad": [dependency_message],
        "messages": [dependency_message],
        "execution_log": state.execution_log + [{
            "phase": "dependency_management",
            "status": "completed",
            "project_type": project_type,
            "commands_executed": dependency_commands,
            "results": execution_results
        }]
    }

def enhanced_architecture_phase(state: IntegratedSWEState):
    """Enhanced architecture phase with terminal awareness"""
    
    print("🏗️ Architecture planning with terminal integration...")
    
    # Prepare state for architect component
    architect_state = {
        "task_description": state.task_description,
        "implementation_research_scratchpad": state.implementation_research_scratchpad
    }
    
    # Run the existing architect with enhanced context
    architect_result = swe_architect.invoke(architect_state)
    
    # Extract implementation plan
    implementation_plan = architect_result.get("implementation_plan")
    
    if implementation_plan:
        print(f"📋 Generated implementation plan with {len(implementation_plan.tasks)} tasks")
        
        # Add terminal context to each task
        for i, task in enumerate(implementation_plan.tasks):
            terminal_context = f"Terminal session 'main' available. Workspace: {getattr(state, 'workspace_dir', './workspace_repo')}"
            for atomic_task in task.atomic_tasks:
                if atomic_task.additional_context:
                    atomic_task.additional_context += f"\n\nTerminal Context: {terminal_context}"
                else:
                    atomic_task.additional_context = f"Terminal Context: {terminal_context}"
    
    # Update state
    state.implementation_plan = implementation_plan
    state.current_phase = "implementation"
    
    return {
        "implementation_plan": implementation_plan,
        "current_phase": "implementation",
        "implementation_research_scratchpad": architect_result.get("implementation_research_scratchpad", [])
    }

def enhanced_development_phase(state: IntegratedSWEState):
    """Enhanced development phase with terminal integration"""
    
    print("⚡ Development phase with terminal integration...")
    
    if not state.implementation_plan:
        raise ValueError("No implementation plan available for development phase")
    
    # Prepare state for developer component
    developer_state = {
        "implementation_plan": state.implementation_plan,
        "current_task_idx": 0,
        "current_atomic_task_idx": 0,
        "atomic_implementation_research": [],
        "current_file_content": "",
        "codebase_structure": ""
    }
    
    # Run the existing developer with enhanced context
    developer_result = swe_developer.invoke(developer_state)
    
    # Verify files were created/modified using terminal
    terminal_manager = get_terminal_manager()
    
    # Check the workspace after development
    ls_result = terminal_manager.execute_command("find . -name '*.py' -o -name '*.js' -o -name '*.ts' -o -name '*.html' -o -name '*.css' | head -20", "main")
    git_status = terminal_manager.execute_command("git status --porcelain", "main")
    
    verification_info = {
        "files_found": ls_result,
        "git_status": git_status
    }
    
    print("📁 Verifying implementation...")
    if ls_result.get("output"):
        print(f"✅ Files created/found:\n{ls_result.get('output', '')}")
    
    # Update state
    state.current_phase = "testing"
    
    return {
        "current_phase": "testing",
        "verification_info": verification_info
    }

def enhanced_testing_phase(state: IntegratedSWEState):
    """Enhanced testing phase with terminal execution"""
    
    print("Testing phase with terminal execution...")
    
    terminal_manager = get_terminal_manager()
    
    # Try to run tests based on project type
    test_commands = [
        "python -m pytest --version",
        "python -m unittest discover -s . -p 'test_*.py'",
        "python -m pytest -v",
        "npm test",
        "python main.py --help",
        "python main.py"
    ]
    
    test_results = []
    successful_tests = 0
    
    for command in test_commands:
        print(f"🔬 Trying: {command}")
        result = terminal_manager.execute_command(command, "main")
        test_results.append({
            "command": command,
            "result": result
        })
        
        if result.get("success", False):
            successful_tests += 1
            print(f" {command} - Passed")
        else:
            print(f" {command} - Failed or not applicable")
    
    # Update state
    state.current_phase = "finalization"
    
    test_message = AIMessage(
        content=f"Testing completed. {successful_tests}/{len(test_commands)} tests passed or applicable. "
               f"Implementation verification completed."
    )
    
    return {
        "current_phase": "finalization",
        "messages": [test_message],
        "execution_log": state.execution_log + [{
            "phase": "testing",
            "status": "completed",
            "tests_run": len(test_commands),
            "successful_tests": successful_tests,
            "results": test_results
        }]
    }

def enhanced_finalization(state: IntegratedSWEState):
    """Enhanced finalization with complete summary"""
    
    print(" Finalizing enhanced SWE agent execution...")
    
    terminal_manager = get_terminal_manager()
    
    # Final workspace verification
    final_ls = terminal_manager.execute_command("ls -la", "main")
    tree_structure = terminal_manager.execute_command("find . -type f | head -20", "main")
    
    # Generate execution summary
    total_phases = len(state.execution_log)
    
    summary = {
        "task_completed": state.task_description,
        "phases_executed": total_phases,
        "terminal_sessions": len(state.terminal_sessions),
        "implementation_plan_tasks": len(state.implementation_plan.tasks) if state.implementation_plan else 0,
        "final_workspace": final_ls.get("output", ""),
        "project_structure": tree_structure.get("output", ""),
        "status": "completed"
    }
    
    print(" Execution Summary:")
    print(f"    Task: {state.task_description}")
    print(f"    Phases completed: {total_phases}")
    print(f"    Terminal sessions: {len(state.terminal_sessions)}")
    print(f"    Implementation tasks: {summary['implementation_plan_tasks']}")
    print(f"    Status: {summary['status']}")
    
    # Close terminal sessions
    for session_id in state.terminal_sessions.keys():
        terminal_manager.close_session(session_id)
    
    state.final_status = "completed"
    
    return {
        "final_status": "completed",
        "execution_summary": summary
    }

# Conditional routing functions
def should_setup_dependencies(state: IntegratedSWEState):
    """Check if dependencies need to be set up"""
    return "setup_dependencies" if not state.dependencies_installed else "architecture"

def should_continue_to_development(state: IntegratedSWEState):
    """Check if we should proceed to development"""
    return "development" if state.implementation_plan else "architecture"

def should_run_tests(state: IntegratedSWEState):
    """Check if tests should be run"""
    return "testing" if state.current_phase == "testing" else "finalization"

# Create the integrated workflow graph
def create_integrated_swe_workflow():
    """Create the integrated SWE workflow with terminal control"""
    
    workflow = StateGraph(IntegratedSWEState)
    
    # Add enhanced nodes
    workflow.add_node("initialization", enhanced_initialization)
    workflow.add_node("dependency_management", dependency_management)
    workflow.add_node("architecture", enhanced_architecture_phase)
    workflow.add_node("development", enhanced_development_phase)
    workflow.add_node("testing", enhanced_testing_phase)
    workflow.add_node("finalization", enhanced_finalization)
    
    # Add terminal tools node for manual operations
    workflow.add_node("terminal_tools", ToolNode(terminal_tools))
    
    # Define the linear flow with conditional routing
    workflow.add_edge(START, "initialization")
    workflow.add_edge("initialization", "dependency_management")
    workflow.add_edge("dependency_management", "architecture")
    workflow.add_edge("architecture", "development")
    workflow.add_edge("development", "testing")
    workflow.add_edge("testing", "finalization")
    workflow.add_edge("finalization", END)
    
    return workflow

# Compile the integrated SWE agent
integrated_swe_agent = create_integrated_swe_workflow().compile().with_config({
    "tags": ["integrated-swe-agent-v1"],
    "recursion_limit": 100
})

# Main execution function
def run_integrated_swe_agent(task_description: str, 
                           workspace_dir: str = "./workspace_repo",
                           execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL):
    """Run the integrated SWE agent with terminal control"""
    
    print("🚀 Starting Integrated SWE Agent with Terminal Control")
    print("=" * 60)
    
    initial_state = IntegratedSWEState(
        task_description=task_description,
        workspace_dir=workspace_dir,
        execution_mode=execution_mode,
        use_existing_components=True,
        force_terminal_setup=True
    )
    
    try:
        # Execute the workflow
        result = integrated_swe_agent.invoke(initial_state)
        
        print("\n🎉 Integrated SWE Agent Execution Completed!")
        print("=" * 60)
        print(f" Final Status: {result.get('final_status', 'unknown')}")
        
        if 'execution_summary' in result:
            summary = result['execution_summary']
            print(f" Summary:")
            print(f"   - Phases: {summary.get('phases_executed', 0)}")
            print(f"   - Tasks: {summary.get('implementation_plan_tasks', 0)}")
            print(f"   - Terminal Sessions: {summary.get('terminal_sessions', 0)}")
        
        return result
        
    except Exception as e:
        print(f" Error during execution: {e}")
        import traceback
        traceback.print_exc()
        return {"final_status": "error", "error": str(e)}

# Create a wrapper for simple_api.py compatibility
class IntegratedAgentWrapper:
    """Wrapper to make integrated agent compatible with simple_api"""
    
    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the integrated agent"""
        task_description = inputs.get("task_description", "")
        workspace_dir = inputs.get("workspace_dir", "./workspace_repo")
        
        return run_integrated_swe_agent(
            task_description=task_description,
            workspace_dir=workspace_dir,
            execution_mode=ExecutionMode.SEQUENTIAL
        )
    
    async def ainvoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Async invoke for compatibility"""
        return self.invoke(inputs)

# Export for simple_api.py
swe_agent = IntegratedAgentWrapper()

if __name__ == "__main__":
    # Example usage
    task = "Create a simple Python web scraper that extracts quotes from quotes.toscrape.com and saves them to a CSV file"
    
    result = run_integrated_swe_agent(
        task_description=task,
        workspace_dir=r"C:\Users\LENOVO\OneDrive\Documents\ZIP_SWE\swe-agent2\swe-agent\workspace_repo",
        execution_mode=ExecutionMode.SEQUENTIAL
    )
    
    print(f"\n Final Result: {result.get('final_status', 'unknown')}")
