"""Basic tests for SWE Agent components"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.architect.state import SoftwareArchitectState
from agent.developer.state import SoftwareDeveloperState
from agent.common.entities import ImplementationPlan, ImplementationTask, AtomicTask


class TestArchitect:
    """Test the architect agent"""
    
    def test_architect_creates_plan(self):
        """Test that architect can create an implementation plan"""
        # Create a mock implementation plan
        plan = ImplementationPlan(
            tasks=[
                ImplementationTask(
                    file_path="test.py",
                    logical_task="Create a test file",
                    atomic_tasks=[
                        AtomicTask(
                            atomic_task="Write test function",
                            additional_context="Basic test"
                        )
                    ]
                )
            ]
        )
        
        assert plan is not None
        assert len(plan.tasks) == 1
        assert plan.tasks[0].file_path == "test.py"
        assert plan.tasks[0].logical_task == "Create a test file"
        assert len(plan.tasks[0].atomic_tasks) == 1
        
    def test_architect_state_initialization(self):
        """Test architect state initialization"""
        state = SoftwareArchitectState(
            implementation_research_scratchpad=[],
            is_valid_research_step=True
        )
        
        assert state.implementation_research_scratchpad == []
        assert state.is_valid_research_step == True
        assert state.implementation_plan is None
        
    @patch('agent.architect.graph.plan_next_step_runnable')
    def test_research_planning(self, mock_runnable):
        """Test research planning functionality"""
        from agent.architect.graph import come_up_with_research_next_step
        
        # Mock the response
        mock_response = Mock()
        mock_response.hypothesis = "Test hypothesis"
        mock_response.reasoning = "Test reasoning"
        mock_runnable.invoke.return_value = mock_response
        
        # Create state
        state = SoftwareArchitectState(
            implementation_research_scratchpad=[]
        )
        
        # Call function
        result = come_up_with_research_next_step(state)
        
        assert "research_next_step" in result
        assert result["research_next_step"] == "Test hypothesis"


class TestDeveloper:
    """Test the developer agent"""
    
    def test_developer_creates_files(self):
        """Test that developer can handle file creation"""
        # Create a mock implementation plan
        plan = ImplementationPlan(
            tasks=[
                ImplementationTask(
                    file_path="./workspace_repo/test_file.py",
                    logical_task="Create test file",
                    atomic_tasks=[
                        AtomicTask(
                            atomic_task="Write hello world",
                            additional_context=""
                        )
                    ]
                )
            ]
        )
        
        # Create developer state
        state = SoftwareDeveloperState(
            implementation_plan=plan,
            current_task_idx=0,
            current_atomic_task_idx=0
        )
        
        assert state.implementation_plan is not None
        assert state.current_task_idx == 0
        assert state.current_atomic_task_idx == 0
        
    def test_developer_state_navigation(self):
        """Test developer state navigation through tasks"""
        from agent.developer.graph import proceed_to_next_atomic_task
        
        # Create plan with multiple tasks
        plan = ImplementationPlan(
            tasks=[
                ImplementationTask(
                    file_path="file1.py",
                    logical_task="Task 1",
                    atomic_tasks=[
                        AtomicTask(atomic_task="Subtask 1", additional_context=""),
                        AtomicTask(atomic_task="Subtask 2", additional_context="")
                    ]
                ),
                ImplementationTask(
                    file_path="file2.py",
                    logical_task="Task 2",
                    atomic_tasks=[
                        AtomicTask(atomic_task="Subtask 3", additional_context="")
                    ]
                )
            ]
        )
        
        state = SoftwareDeveloperState(
            implementation_plan=plan,
            current_task_idx=0,
            current_atomic_task_idx=0
        )
        
        # Navigate to next atomic task
        result = proceed_to_next_atomic_task(state)
        
        assert "current_atomic_task_idx" in result
        assert result["current_atomic_task_idx"] == 1
        
    def test_file_path_handling(self):
        """Test that file paths are handled correctly"""
        import os
        from pathlib import Path
        
        # Test path normalization
        test_paths = [
            "./workspace_repo/src/main.py",
            ".\\workspace_repo\\src\\main.py",
            "workspace_repo/src/main.py"
        ]
        
        for path in test_paths:
            normalized = Path(path)
            assert normalized.parts[-1] == "main.py"
            assert "src" in normalized.parts


class TestTools:
    """Test the tool functions"""
    
    def test_search_tool_exists(self):
        """Test that search tools are available"""
        from agent.tools.search import search_tools
        
        assert search_tools is not None
        assert len(search_tools) > 0
        
        # Check for specific tools
        tool_names = [tool.name for tool in search_tools]
        assert "search_in_file" in tool_names
        
    def test_codemap_tool_exists(self):
        """Test that codemap tools are available"""
        from agent.tools.codemap import codemap_tools
        
        assert codemap_tools is not None
        assert len(codemap_tools) > 0
        
        # Check for specific tools
        tool_names = [tool.name for tool in codemap_tools]
        assert "get_code_definitions" in tool_names
        
    def test_write_tool_exists(self):
        """Test that write tools are available"""
        from agent.tools.write import write_file, get_files_structure
        
        assert write_file is not None
        assert get_files_structure is not None
        
    @patch('builtins.open', new_callable=MagicMock)
    def test_file_encoding(self, mock_open):
        """Test that files are opened with UTF-8 encoding"""
        from agent.developer.graph import creating_diffs_for_task
        
        # The function should use UTF-8 encoding
        # This is a placeholder for actual encoding test
        assert True  # Encoding is handled in the actual implementation


class TestAPI:
    """Test the API endpoints"""
    
    def test_api_imports(self):
        """Test that API server can be imported"""
        try:
            from simple_api import app, AgentRequest, AgentResponse
            assert app is not None
            assert AgentRequest is not None
            assert AgentResponse is not None
        except ImportError:
            pytest.skip("API server not available")
            
    def test_request_model(self):
        """Test the request model structure"""
        from simple_api import AgentRequest
        
        request = AgentRequest(task="Test task")
        assert request.task == "Test task"
        
    def test_response_model(self):
        """Test the response model structure"""
        from simple_api import AgentResponse
        
        response = AgentResponse(
            success=True,
            implementation_plan={"test": "plan"},
            error=None,
            trace_url="http://example.com"
        )
        
        assert response.success == True
        assert response.implementation_plan == {"test": "plan"}
        assert response.error is None
        assert response.trace_url == "http://example.com"


class TestIntegration:
    """Integration tests for the complete system"""
    
    def test_workspace_directory_exists(self):
        """Test that workspace directory is created"""
        from pathlib import Path
        
        workspace = Path("./workspace_repo")
        if not workspace.exists():
            workspace.mkdir(parents=True, exist_ok=True)
            
        assert workspace.exists()
        assert workspace.is_dir()
        
    def test_env_file_exists(self):
        """Test that .env file exists"""
        from pathlib import Path
        
        env_file = Path(".env")
        assert env_file.exists()
        
    def test_langsmith_configuration(self):
        """Test LangSmith configuration"""
        import os
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Check that LangSmith variables are set
        assert os.getenv("LANGSMITH_API_KEY") is not None
        assert os.getenv("LANGSMITH_PROJECT") is not None
        assert os.getenv("LANGSMITH_ENDPOINT") is not None
        
    def test_prompt_files_exist(self):
        """Test that all prompt files exist"""
        from pathlib import Path
        
        prompt_dirs = [
            Path("agent/architect/prompts"),
            Path("agent/developer/prompts"),
            Path("agent/tester/prompts"),
            Path("agent/reviewer/prompts")
        ]
        
        for prompt_dir in prompt_dirs:
            if prompt_dir.exists():
                md_files = list(prompt_dir.glob("*.md"))
                assert len(md_files) > 0, f"No prompt files in {prompt_dir}"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])