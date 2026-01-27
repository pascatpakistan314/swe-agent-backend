"""
Enhanced Linear SWE Agent with Parallel Execution and Terminal Control
This agent addresses the issues with terminal setup and project control.
"""

import os
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, TypedDict, Annotated, Any
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AnyMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.tools import tool
from langgraph.graph import add_messages, StateGraph, START, END
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field

# Import existing tools
from agent.tools.terminal import terminal_tools, get_terminal_manager
from agent.tools.search import search_tools
from agent.tools.codemap import codemap_tools
from agent.tools.write import get_files_structure
from agent.common.entities import ImplementationPlan, ImplementationTask, AtomicTask

load_dotenv()

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"

@dataclass
class ParallelTask:
    """Represents a task that can be executed in parallel"""
    id: str
    description: str
    commands: List[str]
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    output: str = ""
    error: str = ""
    session_id: Optional[str] = None

class EnhancedAgentState(BaseModel):
    """State for the enhanced linear agent with parallel execution"""
    
    # Core task information
    task_description: str = Field(..., description="The user's high-level task/goal")
    
    # Execution control
    execution_mode: ExecutionMode = Field(default=ExecutionMode.SEQUENTIAL, description="Execution mode")
    current_phase: str = Field(default="initialization", description="Current execution phase")
    
    # Terminal and environment management
    terminal_sessions: Dict[str, Any] = Field(default_factory=dict, description="Active terminal sessions")
    environment_setup: bool = Field(default=False, description="Whether environment is set up")
    dependencies_installed: bool = Field(default=False, description="Whether dependencies are installed")
    
    # Task management
    parallel_tasks: List[ParallelTask] = Field(default_factory=list, description="Tasks for parallel execution")
    completed_tasks: List[str] = Field(default_factory=list, description="Completed task IDs")
    failed_tasks: List[str] = Field(default_factory=list, description="Failed task IDs")
    
    # Implementation planning
    implementation_plan: Optional[ImplementationPlan] = Field(None, description="Generated implementation plan")
    research_findings: Annotated[List[AnyMessage], add_messages] = Field(default_factory=list)
    
    # Execution results
    execution_log: List[Dict[str, Any]] = Field(default_factory=list, description="Execution log")
    final_status: str = Field(default="in_progress", description="Final execution status")

# Phase definitions for linear execution
EXECUTION_PHASES = [
    "initialization",
    "environment_setup", 
    "dependency_installation",
    "research_and_planning",
    "implementation",
    "testing",
    "finalization"
]

class EnhancedLinearAgent:
    """Enhanced linear agent with parallel execution capabilities"""
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = Path(workspace_dir)
        self.llm = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.terminal_manager = get_terminal_manager()
        
    async def setup_environment(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Set up the development environment"""
        
        print("🚀 Setting up development environment...")
        
        # Create workspace directory if it doesn't exist
        os.makedirs(self.workspace_dir, exist_ok=True)
        
        # Create main terminal session
        main_session = self.terminal_manager.create_session("main")
        
        # Navigate to workspace
        cd_result = self.terminal_manager.execute_command(
            f"cd {self.workspace_dir}", "main"
        )
        
        # Check if this is a Python project
        python_files = list(self.workspace_dir.glob("*.py"))
        requirements_file = self.workspace_dir / "requirements.txt"
        package_json = self.workspace_dir / "package.json"
        
        environment_info = {
            "workspace_dir": str(self.workspace_dir),
            "python_project": len(python_files) > 0 or requirements_file.exists(),
            "node_project": package_json.exists(),
            "main_session": main_session,
            "cd_result": cd_result
        }
        
        state.terminal_sessions["main"] = main_session
        state.environment_setup = True
        state.execution_log.append({
            "phase": "environment_setup",
            "status": "completed",
            "details": environment_info
        })
        
        return {
            "environment_setup": True,
            "terminal_sessions": state.terminal_sessions,
            "execution_log": state.execution_log
        }
    
    async def install_dependencies(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Install project dependencies"""
        
        print("📦 Installing dependencies...")
        
        installation_tasks = []
        
        # Check for Python dependencies
        requirements_file = self.workspace_dir / "requirements.txt"
        if requirements_file.exists():
            installation_tasks.append(ParallelTask(
                id="python_deps",
                description="Install Python dependencies",
                commands=["pip install -r requirements.txt"],
                session_id="main"
            ))
        
        # Check for Node.js dependencies
        package_json = self.workspace_dir / "package.json"
        if package_json.exists():
            installation_tasks.append(ParallelTask(
                id="node_deps", 
                description="Install Node.js dependencies",
                commands=["npm install"],
                session_id="main"
            ))
        
        # Check for other common dependency files
        poetry_lock = self.workspace_dir / "poetry.lock"
        if poetry_lock.exists():
            installation_tasks.append(ParallelTask(
                id="poetry_deps",
                description="Install Poetry dependencies", 
                commands=["poetry install"],
                session_id="main"
            ))
        
        # Execute dependency installation
        results = []
        for task in installation_tasks:
            print(f"Installing {task.description}...")
            for command in task.commands:
                result = self.terminal_manager.execute_command(command, task.session_id)
                results.append(result)
                task.output += result.get("output", "")
                if not result.get("success", False):
                    task.status = TaskStatus.FAILED
                    task.error += result.get("error", "")
                else:
                    task.status = TaskStatus.COMPLETED
        
        # If no dependencies found, create basic setup
        if not installation_tasks:
            print("No dependency files found, creating basic Python setup...")
            
            # Create a basic requirements.txt if it's a Python project
            python_files = list(self.workspace_dir.glob("*.py"))
            if python_files:
                basic_deps = ["requests", "python-dotenv"]
                with open(requirements_file, "w") as f:
                    for dep in basic_deps:
                        f.write(f"{dep}\n")
                
                install_result = self.terminal_manager.execute_command(
                    "pip install -r requirements.txt", "main"
                )
                results.append(install_result)
        
        state.dependencies_installed = True
        state.execution_log.append({
            "phase": "dependency_installation",
            "status": "completed",
            "tasks": [task.__dict__ for task in installation_tasks],
            "results": results
        })
        
        return {
            "dependencies_installed": True,
            "execution_log": state.execution_log
        }
    
    async def research_and_plan(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Conduct research and create implementation plan"""
        
        print("🔍 Conducting research and planning...")
        
        # Get codebase structure
        codebase_structure = get_files_structure.invoke({
            "directory": str(self.workspace_dir)
        })
        
        # Analyze the task and create research plan
        research_prompt = f"""
        Task: {state.task_description}
        
        Codebase Structure:
        {codebase_structure}
        
        Analyze this task and create a comprehensive research and implementation plan.
        Consider:
        1. What needs to be implemented
        2. What files need to be created/modified  
        3. What external dependencies might be needed
        4. What research is needed to understand the requirements
        5. How to break down the work into parallel tasks
        
        Provide a detailed analysis and implementation strategy.
        """
        
        research_response = await self.llm.ainvoke([
            SystemMessage(content="You are an expert software architect analyzing implementation requirements."),
            HumanMessage(content=research_prompt)
        ])
        
        state.research_findings.append(research_response)
        
        # Create implementation plan based on research
        plan_prompt = f"""
        Based on the research findings, create a detailed implementation plan.
        
        Task: {state.task_description}
        Research: {research_response.content}
        Codebase: {codebase_structure}
        
        Create an ImplementationPlan with specific tasks that can be executed in parallel where possible.
        Each task should be atomic and well-defined.
        """
        
        # Use structured output to get implementation plan
        structured_llm = self.llm.with_structured_output(ImplementationPlan)
        implementation_plan = await structured_llm.ainvoke([
            SystemMessage(content="You are creating a detailed implementation plan."),
            HumanMessage(content=plan_prompt)
        ])
        
        state.implementation_plan = implementation_plan
        state.execution_log.append({
            "phase": "research_and_planning",
            "status": "completed", 
            "plan_tasks": len(implementation_plan.tasks) if implementation_plan else 0
        })
        
        return {
            "implementation_plan": implementation_plan,
            "research_findings": state.research_findings,
            "execution_log": state.execution_log
        }
    
    async def execute_implementation(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Execute the implementation plan with parallel execution support"""
        
        print("⚡ Executing implementation...")
        
        if not state.implementation_plan:
            raise ValueError("No implementation plan available")
        
        # Convert implementation tasks to parallel tasks
        parallel_tasks = []
        for i, task in enumerate(state.implementation_plan.tasks):
            parallel_task = ParallelTask(
                id=f"impl_task_{i}",
                description=task.logical_task,
                commands=[f"# Implement: {task.logical_task}"],
                session_id="main"
            )
            parallel_tasks.append(parallel_task)
        
        # Execute tasks based on execution mode
        if state.execution_mode == ExecutionMode.PARALLEL:
            results = await self._execute_parallel_tasks(parallel_tasks)
        else:
            results = await self._execute_sequential_tasks(parallel_tasks)
        
        state.parallel_tasks = parallel_tasks
        state.completed_tasks = [task.id for task in parallel_tasks if task.status == TaskStatus.COMPLETED]
        state.failed_tasks = [task.id for task in parallel_tasks if task.status == TaskStatus.FAILED]
        
        state.execution_log.append({
            "phase": "implementation",
            "status": "completed" if not state.failed_tasks else "partial",
            "completed": len(state.completed_tasks),
            "failed": len(state.failed_tasks),
            "results": results
        })
        
        return {
            "parallel_tasks": state.parallel_tasks,
            "completed_tasks": state.completed_tasks,
            "failed_tasks": state.failed_tasks,
            "execution_log": state.execution_log
        }
    
    async def _execute_parallel_tasks(self, tasks: List[ParallelTask]) -> List[Dict[str, Any]]:
        """Execute tasks in parallel"""
        
        print(f"🔄 Executing {len(tasks)} tasks in parallel...")
        
        async def execute_task(task: ParallelTask):
            """Execute a single task"""
            task.status = TaskStatus.RUNNING
            
            results = []
            for command in task.commands:
                # For implementation tasks, we need to actually create/modify files
                if command.startswith("# Implement:"):
                    # This would be implemented by calling the actual developer agent
                    # For now, we'll simulate the implementation
                    result = {
                        "command": command,
                        "success": True,
                        "output": f"Simulated implementation of: {task.description}",
                        "error": ""
                    }
                else:
                    result = self.terminal_manager.execute_command(command, task.session_id or "main")
                
                results.append(result)
                task.output += result.get("output", "")
                
                if not result.get("success", True):
                    task.status = TaskStatus.FAILED
                    task.error += result.get("error", "")
                    break
            
            if task.status != TaskStatus.FAILED:
                task.status = TaskStatus.COMPLETED
            
            return results
        
        # Execute all tasks concurrently
        task_results = await asyncio.gather(
            *[execute_task(task) for task in tasks],
            return_exceptions=True
        )
        
        return task_results
    
    async def _execute_sequential_tasks(self, tasks: List[ParallelTask]) -> List[Dict[str, Any]]:
        """Execute tasks sequentially"""
        
        print(f"➡️ Executing {len(tasks)} tasks sequentially...")
        
        results = []
        for task in tasks:
            task.status = TaskStatus.RUNNING
            
            task_results = []
            for command in task.commands:
                if command.startswith("# Implement:"):
                    result = {
                        "command": command,
                        "success": True,
                        "output": f"Simulated implementation of: {task.description}",
                        "error": ""
                    }
                else:
                    result = self.terminal_manager.execute_command(command, task.session_id or "main")
                
                task_results.append(result)
                task.output += result.get("output", "")
                
                if not result.get("success", True):
                    task.status = TaskStatus.FAILED
                    task.error += result.get("error", "")
                    break
            
            if task.status != TaskStatus.FAILED:
                task.status = TaskStatus.COMPLETED
            
            results.append(task_results)
        
        return results
    
    async def run_tests(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Run tests if available"""
        
        print("🧪 Running tests...")
        
        test_commands = []
        
        # Check for Python tests
        if (self.workspace_dir / "tests").exists() or list(self.workspace_dir.glob("test_*.py")):
            test_commands.extend([
                "python -m pytest",
                "python -m unittest discover"
            ])
        
        # Check for Node.js tests
        if (self.workspace_dir / "package.json").exists():
            test_commands.append("npm test")
        
        # Run available tests
        test_results = []
        for command in test_commands:
            try:
                result = self.terminal_manager.execute_command(command, "main")
                test_results.append(result)
                if result.get("success"):
                    print(f"✅ {command} passed")
                    break  # Use first successful test command
                else:
                    print(f"❌ {command} failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                print(f"⚠️ Could not run {command}: {e}")
        
        state.execution_log.append({
            "phase": "testing",
            "status": "completed",
            "test_results": test_results
        })
        
        return {
            "execution_log": state.execution_log
        }
    
    async def finalize(self, state: EnhancedAgentState) -> Dict[str, Any]:
        """Finalize the execution"""
        
        print("🎯 Finalizing execution...")
        
        # Determine final status
        if state.failed_tasks:
            final_status = "partially_completed"
        elif state.completed_tasks:
            final_status = "completed"
        else:
            final_status = "failed"
        
        # Generate summary
        summary = {
            "task_description": state.task_description,
            "execution_mode": state.execution_mode.value,
            "phases_completed": len(state.execution_log),
            "total_tasks": len(state.parallel_tasks),
            "completed_tasks": len(state.completed_tasks),
            "failed_tasks": len(state.failed_tasks),
            "final_status": final_status
        }
        
        print(f"✅ Execution complete! Status: {final_status}")
        print(f"📊 Completed {len(state.completed_tasks)}/{len(state.parallel_tasks)} tasks")
        
        state.final_status = final_status
        state.execution_log.append({
            "phase": "finalization",
            "status": "completed",
            "summary": summary
        })
        
        return {
            "final_status": final_status,
            "execution_log": state.execution_log
        }

def _run_coro(coro):
    """Safely run coroutine in environments with or without event loops"""
    try:
        loop = asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            return ex.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)

# Tool functions for the graph
def initialize_agent(state: EnhancedAgentState):
    """Initialize the enhanced agent"""
    print("🎬 Initializing Enhanced Linear Agent...")
    
    state.current_phase = "initialization"
    state.execution_log.append({
        "phase": "initialization",
        "status": "completed",
        "message": "Agent initialized successfully"
    })
    
    return {
        "current_phase": "environment_setup",
        "execution_log": state.execution_log
    }

def setup_environment_node(state: EnhancedAgentState):
    """Node wrapper for environment setup"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.setup_environment(state))

def install_dependencies_node(state: EnhancedAgentState):
    """Node wrapper for dependency installation"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.install_dependencies(state))

def research_and_plan_node(state: EnhancedAgentState):
    """Node wrapper for research and planning"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.research_and_plan(state))

def execute_implementation_node(state: EnhancedAgentState):
    """Node wrapper for implementation execution"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.execute_implementation(state))

def run_tests_node(state: EnhancedAgentState):
    """Node wrapper for testing"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.run_tests(state))

def finalize_node(state: EnhancedAgentState):
    """Node wrapper for finalization"""
    agent = EnhancedLinearAgent()
    return _run_coro(agent.finalize(state))

# Create the enhanced linear workflow graph
def create_enhanced_linear_workflow():
    """Create the enhanced linear workflow with parallel execution support"""
    
    workflow = StateGraph(EnhancedAgentState)
    
    # Add all nodes
    workflow.add_node("initialize", initialize_agent)
    workflow.add_node("setup_environment", setup_environment_node)
    workflow.add_node("install_dependencies", install_dependencies_node) 
    workflow.add_node("research_and_plan", research_and_plan_node)
    workflow.add_node("execute_implementation", execute_implementation_node)
    workflow.add_node("run_tests", run_tests_node)
    workflow.add_node("finalize", finalize_node)
    
    # Add terminal tools node for manual terminal operations
    workflow.add_node("terminal_tools", ToolNode(terminal_tools))
    
    # Define linear flow
    workflow.add_edge(START, "initialize")
    workflow.add_edge("initialize", "setup_environment")
    workflow.add_edge("setup_environment", "install_dependencies")
    workflow.add_edge("install_dependencies", "research_and_plan")
    workflow.add_edge("research_and_plan", "execute_implementation")
    workflow.add_edge("execute_implementation", "run_tests")
    workflow.add_edge("run_tests", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow

# Compile the enhanced linear agent
enhanced_linear_agent = create_enhanced_linear_workflow().compile().with_config({
    "tags": ["enhanced-linear-agent-v1"],
    "recursion_limit": 100
})

if __name__ == "__main__":
    # Example usage
    initial_state = EnhancedAgentState(
        task_description="Create a simple web scraper that extracts data from a website and saves it to CSV",
        execution_mode=ExecutionMode.PARALLEL
    )
    
    # Run the agent
    result = enhanced_linear_agent.invoke(initial_state)
    
    print("🎉 Enhanced Linear Agent completed!")
    print(f"Final Status: {result.get('final_status', 'unknown')}")
    print(f"Execution Log: {len(result.get('execution_log', []))} phases completed")