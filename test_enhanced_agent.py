#!/usr/bin/env python3
"""
Test script for the Enhanced SWE Agent with Terminal Control
"""

import os
import sys
import tempfile
from pathlib import Path

# Add agent directory to path
current_dir = Path(__file__).parent
agent_dir = current_dir / "agent"
sys.path.insert(0, str(agent_dir))
sys.path.insert(0, str(current_dir))

def test_terminal_integration():
    """Test terminal integration capabilities"""
    print("🧪 Testing Terminal Integration...")
    
    try:
        from agent.tools.terminal import get_terminal_manager, terminal_execute
        
        # Test terminal manager
        terminal_manager = get_terminal_manager()
        
        # Create a test session
        session_info = terminal_manager.create_session("test")
        print(f"✅ Terminal session created: {session_info}")
        
        # Test command execution
        result = terminal_execute("echo 'Hello from Enhanced SWE Agent!'", "test")
        print(f"✅ Command execution result: {result}")
        
        # Test directory navigation
        temp_dir = tempfile.mkdtemp()
        cd_result = terminal_execute(f"cd {temp_dir}", "test")
        pwd_result = terminal_execute("pwd", "test")
        print(f"✅ Directory navigation: {pwd_result}")
        
        # Clean up
        terminal_manager.close_session("test")
        print("✅ Terminal integration test passed")
        return True
        
    except Exception as e:
        print(f"❌ Terminal integration test failed: {e}")
        return False

def test_enhanced_agent_import():
    """Test importing the enhanced agent components"""
    print("🧪 Testing Enhanced Agent Import...")
    
    try:
        from agent.enhanced_linear_agent import EnhancedLinearAgent, EnhancedAgentState, ExecutionMode
        from agent.integrated_graph import run_integrated_swe_agent, IntegratedSWEState
        from agent.graph import enhanced_swe_agent, run_enhanced_agent
        
        print("✅ All enhanced agent components imported successfully")
        
        # Test state creation
        state = EnhancedAgentState(
            task_description="Test task",
            execution_mode=ExecutionMode.SEQUENTIAL
        )
        print(f"✅ Agent state created: {state.task_description}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced agent import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_workspace_setup():
    """Test workspace setup functionality"""
    print("🧪 Testing Workspace Setup...")
    
    try:
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "test_workspace"
            workspace_path.mkdir(exist_ok=True)
            
            # Test basic workspace creation
            from agent.enhanced_linear_agent import EnhancedLinearAgent
            
            agent = EnhancedLinearAgent(str(workspace_path))
            print(f"✅ Enhanced agent created with workspace: {workspace_path}")
            
            # Test that workspace exists
            assert workspace_path.exists(), "Workspace directory should exist"
            print("✅ Workspace setup test passed")
            
            return True
            
    except Exception as e:
        print(f"❌ Workspace setup test failed: {e}")
        return False

def test_basic_agent_execution():
    """Test basic agent execution with a simple task"""
    print("🧪 Testing Basic Agent Execution...")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_path = Path(temp_dir) / "agent_test"
            
            # Simple test task
            task_description = "Create a simple hello world Python script"
            
            from agent.integrated_graph import run_integrated_swe_agent, ExecutionMode
            
            print(f"🚀 Running agent with task: {task_description}")
            print(f"📁 Workspace: {workspace_path}")
            
            # Run with sequential mode for testing
            result = run_integrated_swe_agent(
                task_description=task_description,
                workspace_dir=str(workspace_path),
                execution_mode=ExecutionMode.SEQUENTIAL
            )
            
            print(f"✅ Agent execution completed with status: {result.get('final_status', 'unknown')}")
            
            # Check if workspace has files
            if workspace_path.exists():
                files = list(workspace_path.glob("*"))
                print(f"📁 Files created: {[f.name for f in files]}")
            
            return result.get('final_status') in ['completed', 'partially_completed']
            
    except Exception as e:
        print(f"❌ Basic agent execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Run all tests"""
    print("🧪 Enhanced SWE Agent - Test Suite")
    print("=" * 50)
    
    tests = [
        ("Terminal Integration", test_terminal_integration),
        ("Enhanced Agent Import", test_enhanced_agent_import), 
        ("Workspace Setup", test_workspace_setup),
        ("Basic Agent Execution", test_basic_agent_execution)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🔍 Running: {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
                
        except Exception as e:
            print(f"💥 {test_name}: CRASHED - {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 50)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\n🏁 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Enhanced SWE Agent is ready to use.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the configuration.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
