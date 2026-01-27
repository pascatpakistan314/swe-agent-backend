"""
Multi-Agent Orchestrator - Intelligent task routing and agent coordination
Following Devin's architecture with task assignment and specialized agents
"""
import os
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel, Field

# Agent specializations
class AgentType(Enum):
    ARCHITECT = "architect"       # Research and planning
    DEVELOPER = "developer"       # Code implementation
    TESTER = "tester"            # Test generation and execution
    REVIEWER = "reviewer"        # Code review and quality
    DEBUGGER = "debugger"        # Error analysis and fixes
    DOCUMENTER = "documenter"    # Documentation generation
    DEPLOYER = "deployer"        # Deployment and CI/CD
    BROWSER = "browser"          # Web browsing and research
    TERMINAL = "terminal"        # System commands
    COORDINATOR = "coordinator"  # Task assignment

@dataclass
class Task:
    """Represents a task to be assigned to an agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    type: str = ""
    priority: int = 1  # 1-5, 5 being highest
    dependencies: List[str] = field(default_factory=list)
    assigned_to: Optional[AgentType] = None
    status: str = "pending"  # pending, assigned, in_progress, completed, failed
    result: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    context: Dict[str, Any] = field(default_factory=dict)

class TaskQueue:
    """Priority queue for task management"""
    
    def __init__(self):
        self.tasks: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.task_map: Dict[str, Task] = {}
    
    def add_task(self, task: Task):
        """Add task to queue"""
        self.tasks.append(task)
        self.task_map[task.id] = task
        self._sort_tasks()
    
    def _sort_tasks(self):
        """Sort tasks by priority and dependencies"""
        self.tasks.sort(key=lambda t: (-t.priority, len(t.dependencies)))
    
    def get_next_task(self) -> Optional[Task]:
        """Get next available task"""
        for task in self.tasks:
            # Check if dependencies are completed
            deps_completed = all(
                self.task_map.get(dep_id, Task()).status == "completed"
                for dep_id in task.dependencies
            )
            if deps_completed and task.status == "pending":
                return task
        return None
    
    def complete_task(self, task_id: str, result: Dict[str, Any]):
        """Mark task as completed"""
        if task_id in self.task_map:
            task = self.task_map[task_id]
            task.status = "completed"
            task.result = result
            task.completed_at = datetime.now()
            self.completed_tasks.append(task)
            if task in self.tasks:
                self.tasks.remove(task)

class TaskClassifier:
    """Classifies tasks and determines which agent should handle them"""
    
    def __init__(self):
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Task patterns for each agent type
        self.patterns = {
            AgentType.ARCHITECT: [
                "research", "plan", "design", "architecture", "analyze requirements",
                "investigate", "explore", "understand", "study"
            ],
            AgentType.DEVELOPER: [
                "implement", "code", "write", "create", "build", "develop",
                "add feature", "modify", "refactor", "update"
            ],
            AgentType.TESTER: [
                "test", "verify", "validate", "check", "ensure", "quality",
                "coverage", "unit test", "integration test"
            ],
            AgentType.REVIEWER: [
                "review", "audit", "inspect", "evaluate", "assess",
                "code quality", "security check", "best practices"
            ],
            AgentType.DEBUGGER: [
                "debug", "fix", "resolve", "troubleshoot", "error",
                "bug", "issue", "problem", "crash"
            ],
            AgentType.DOCUMENTER: [
                "document", "readme", "api docs", "comments", "docstring",
                "tutorial", "guide", "explain"
            ],
            AgentType.DEPLOYER: [
                "deploy", "release", "publish", "ci/cd", "pipeline",
                "docker", "kubernetes", "aws", "azure"
            ],
            AgentType.BROWSER: [
                "browse", "search web", "find online", "documentation",
                "api reference", "stackoverflow", "github"
            ],
            AgentType.TERMINAL: [
                "run command", "execute", "terminal", "shell", "system",
                "install", "configure", "setup environment"
            ]
        }
    
    def classify_task(self, task_description: str) -> Tuple[AgentType, float]:
        """
        Classify which agent should handle the task
        Returns (agent_type, confidence_score)
        """
        
        # Use LLM for intelligent classification
        classification_prompt = f"""
        Classify this software development task and determine which specialized agent should handle it.
        
        Task: {task_description}
        
        Available agent types:
        - ARCHITECT: Research, planning, design, requirements analysis
        - DEVELOPER: Code implementation, feature development, refactoring
        - TESTER: Test creation, test execution, quality assurance
        - REVIEWER: Code review, security audit, best practices check
        - DEBUGGER: Bug fixing, error resolution, troubleshooting
        - DOCUMENTER: Documentation, README, API docs, tutorials
        - DEPLOYER: Deployment, CI/CD, containerization, cloud services
        - BROWSER: Web research, documentation lookup, online resources
        - TERMINAL: System commands, environment setup, package installation
        
        Respond with JSON:
        {{
            "agent_type": "AGENT_TYPE",
            "confidence": 0.0-1.0,
            "reasoning": "brief explanation"
        }}
        """
        
        response = self.llm.invoke(classification_prompt)
        
        try:
            result = json.loads(response.content)
            agent_type = AgentType[result["agent_type"]]
            confidence = float(result["confidence"])
            return agent_type, confidence
        except:
            # Fallback to pattern matching
            return self._pattern_match_classify(task_description)
    
    def _pattern_match_classify(self, task_description: str) -> Tuple[AgentType, float]:
        """Fallback pattern-based classification"""
        task_lower = task_description.lower()
        scores = {}
        
        for agent_type, patterns in self.patterns.items():
            score = sum(1 for pattern in patterns if pattern in task_lower)
            scores[agent_type] = score
        
        if scores:
            best_agent = max(scores, key=scores.get)
            max_score = scores[best_agent]
            confidence = min(max_score / 3, 1.0)  # Normalize confidence
            return best_agent, confidence
        
        return AgentType.DEVELOPER, 0.5  # Default

class MultiAgentOrchestrator:
    """
    Main orchestrator that coordinates multiple specialized agents
    Similar to Devin's task_assigner_agent
    """
    
    def __init__(self, workspace_dir: str = "./workspace_repo"):
        self.workspace_dir = workspace_dir
        self.task_queue = TaskQueue()
        self.classifier = TaskClassifier()
        self.agents = {}  # AgentType -> Agent instance mapping
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        
        # Initialize specialized agents
        self._initialize_agents()
    
    def _initialize_agents(self):
        """Initialize all specialized agents"""
        # Import actual agents
        from agent.architect.graph_enhanced import swe_architect
        from agent.developer.graph import swe_developer
        from agent.tester.graph import swe_tester
        from agent.reviewer.graph import swe_reviewer
        
        self.agents = {
            AgentType.ARCHITECT: swe_architect,
            AgentType.DEVELOPER: swe_developer,
            AgentType.TESTER: swe_tester,
            AgentType.REVIEWER: swe_reviewer,
            # Add more agents as they're implemented
        }
    
    def decompose_task(self, main_task: str) -> List[Task]:
        """
        Decompose a main task into subtasks
        This is the intelligent planning step
        """
        
        decomposition_prompt = f"""
        Decompose this software engineering task into specific subtasks that can be handled by specialized agents.
        
        Main Task: {main_task}
        
        Create a structured plan with subtasks. Consider:
        1. What needs to be researched first?
        2. What needs to be implemented?
        3. What needs to be tested?
        4. What needs to be reviewed?
        5. Any documentation needed?
        
        Respond with JSON array of tasks:
        [
            {{
                "description": "task description",
                "type": "task type",
                "priority": 1-5,
                "dependencies": ["task_id"] or [],
                "estimated_agent": "ARCHITECT|DEVELOPER|TESTER|etc"
            }}
        ]
        
        Ensure tasks are ordered logically with proper dependencies.
        """
        
        response = self.llm.invoke(decomposition_prompt)
        
        try:
            task_data = json.loads(response.content)
            tasks = []
            task_id_map = {}
            
            for i, data in enumerate(task_data):
                task = Task(
                    id=f"task_{i:03d}",
                    description=data["description"],
                    type=data["type"],
                    priority=data.get("priority", 3),
                    dependencies=[]  # Will map later
                )
                tasks.append(task)
                task_id_map[i] = task.id
            
            # Map dependencies
            for i, data in enumerate(task_data):
                if "dependencies" in data:
                    for dep_idx in data.get("dependencies", []):
                        if isinstance(dep_idx, int) and dep_idx < i:
                            tasks[i].dependencies.append(task_id_map[dep_idx])
            
            return tasks
            
        except Exception as e:
            print(f"Error decomposing task: {e}")
            # Fallback to single task
            return [Task(description=main_task, type="general", priority=3)]
    
    async def execute_task_async(self, task: Task) -> Dict[str, Any]:
        """Execute a single task with the appropriate agent"""
        
        # Classify task to determine agent
        agent_type, confidence = self.classifier.classify_task(task.description)
        task.assigned_to = agent_type
        task.status = "in_progress"
        
        print(f"\n📋 Task {task.id}: {task.description[:50]}...")
        print(f"   Assigned to: {agent_type.value} (confidence: {confidence:.2f})")
        
        # Get the appropriate agent
        if agent_type in self.agents:
            agent = self.agents[agent_type]
            
            try:
                # Execute with the agent
                result = await asyncio.to_thread(
                    agent.invoke,
                    {
                        "task_description": task.description,
                        "implementation_research_scratchpad": [],
                        "context": task.context
                    }
                )
                
                task.status = "completed"
                task.result = result
                print(f"    Completed successfully")
                
                return {
                    "success": True,
                    "result": result,
                    "agent": agent_type.value
                }
                
            except Exception as e:
                task.status = "failed"
                print(f"    Failed: {str(e)}")
                
                return {
                    "success": False,
                    "error": str(e),
                    "agent": agent_type.value
                }
        else:
            # Fallback to LLM-based execution
            return await self._execute_with_llm(task)
    
    async def _execute_with_llm(self, task: Task) -> Dict[str, Any]:
        """Fallback execution using LLM directly"""
        
        execution_prompt = f"""
        Execute this software engineering task:
        
        Task: {task.description}
        Type: {task.type}
        Context: {json.dumps(task.context, indent=2) if task.context else 'None'}
        
        Provide a detailed response with:
        1. Your approach
        2. Implementation details
        3. Any code or commands needed
        4. Expected outcomes
        """
        
        response = await asyncio.to_thread(
            self.llm.invoke,
            execution_prompt
        )
        
        return {
            "success": True,
            "result": {"response": response.content},
            "agent": "llm_fallback"
        }
    
    async def orchestrate(self, main_task: str) -> Dict[str, Any]:
        """
        Main orchestration method - coordinates all agents
        """
        
        print(f"\n Starting Multi-Agent Orchestration")
        print(f" Main Task: {main_task}")
        
        # Step 1: Decompose into subtasks
        print("\n Decomposing task...")
        subtasks = self.decompose_task(main_task)
        print(f"   Generated {len(subtasks)} subtasks")
        
        # Add all tasks to queue
        for task in subtasks:
            self.task_queue.add_task(task)
        
        # Step 2: Execute tasks respecting dependencies
        results = []
        tasks_in_progress = []
        max_concurrent = 3
        
        while self.task_queue.tasks or tasks_in_progress:
            # Start new tasks if we have capacity
            while len(tasks_in_progress) < max_concurrent:
                next_task = self.task_queue.get_next_task()
                if not next_task:
                    break
                
                # Start task execution
                next_task.status = "assigned"
                task_future = asyncio.create_task(
                    self.execute_task_async(next_task)
                )
                tasks_in_progress.append((next_task, task_future))
            
            # Wait for any task to complete
            if tasks_in_progress:
                done, pending = await asyncio.wait(
                    [t[1] for t in tasks_in_progress],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Process completed tasks
                for task, future in tasks_in_progress[:]:
                    if future in done:
                        result = await future
                        results.append(result)
                        self.task_queue.complete_task(task.id, result)
                        tasks_in_progress.remove((task, future))
            
            # Small delay to prevent busy waiting
            if not tasks_in_progress and self.task_queue.tasks:
                await asyncio.sleep(0.1)
        
        # Step 3: Synthesize results
        print("\n Synthesizing results...")
        
        synthesis_prompt = f"""
        Synthesize the results from multiple agent executions for this task:
        
        Main Task: {main_task}
        
        Subtask Results:
        {json.dumps(results, indent=2)}
        
        Provide a comprehensive summary of:
        1. What was accomplished
        2. Key findings or implementations
        3. Any issues encountered
        4. Next steps or recommendations
        """
        
        synthesis = await asyncio.to_thread(
            self.llm.invoke,
            synthesis_prompt
        )
        
        return {
            "main_task": main_task,
            "subtasks_completed": len(self.task_queue.completed_tasks),
            "subtasks_failed": len([t for t in self.task_queue.completed_tasks if t.status == "failed"]),
            "results": results,
            "synthesis": synthesis.content,
            "execution_time": (
                max(t.completed_at for t in self.task_queue.completed_tasks if t.completed_at) -
                min(t.created_at for t in self.task_queue.completed_tasks)
            ).total_seconds() if self.task_queue.completed_tasks else 0
        }

# LangChain Tools for Orchestration
@tool
def orchestrate_multi_agent_task(task: str, workspace: str = "./workspace_repo") -> str:
    """
    Orchestrate a complex task using multiple specialized agents.
    
    Args:
        task: The main task to accomplish
        workspace: Working directory
        
    Returns:
        Orchestration results with synthesis
    """
    orchestrator = MultiAgentOrchestrator(workspace)
    
    # Run orchestration
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            orchestrator.orchestrate(task)
        )
        
        output = []
        output.append(f" Task Orchestration Complete")
        output.append(f"\nMain Task: {result['main_task']}")
        output.append(f"Subtasks Completed: {result['subtasks_completed']}")
        output.append(f"Subtasks Failed: {result['subtasks_failed']}")
        output.append(f"Execution Time: {result['execution_time']:.2f}s")
        output.append(f"\nSynthesis:")
        output.append(result['synthesis'])
        
        return '\n'.join(output)
        
    finally:
        loop.close()

@tool 
def assign_task_to_agent(task: str) -> str:
    """
    Determine which specialized agent should handle a task.
    
    Args:
        task: Task description
        
    Returns:
        Agent assignment with confidence
    """
    classifier = TaskClassifier()
    agent_type, confidence = classifier.classify_task(task)
    
    return f"""
Task: {task}
Assigned Agent: {agent_type.value}
Confidence: {confidence:.2%}

This task will be handled by the {agent_type.value} agent based on its specialization.
"""

# Export orchestration tools
orchestration_tools = [orchestrate_multi_agent_task, assign_task_to_agent]
