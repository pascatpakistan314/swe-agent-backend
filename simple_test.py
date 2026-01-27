#!/usr/bin/env python3
"""
Simple test script for the Enhanced SWE Agent (Windows compatible)
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

def test_imports():
    """Test basic imports"""
    print("Testing Enhanced Agent Imports...")
    
    try:
        from agent.tools.terminal import get_terminal_manager
        print("✓ Terminal tools imported")
        
        from agent.enhanced_linear_agent import EnhancedLinearAgent, ExecutionMode
        print("✓ Enhanced linear agent imported") 
        
        from agent.integrated_graph import run_integrated_swe_agent
        print("✓ Integrated graph imported")
        
        return True
        
    except Exception as e:
        print(f"X Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_terminal():
    """Test terminal functionality"""
    print("Testing Terminal Functionality...")
    
    try:
        from agent.tools.terminal import get_terminal_manager, terminal_execute
        
        # Test terminal manager
        terminal_manager = get_terminal_manager()
        print("✓ Terminal manager created")
        
        # Test session creation
        session = terminal_manager.create_session("test")
        print(f"✓ Terminal session created: {session}")
        
        # Test command execution
        result = terminal_execute("echo Hello", "test")
        print(f"✓ Command executed: {result[:100]}...")
        
        # Clean up
        terminal_manager.close_session("test")
        print("✓ Session closed")
        
        return True
        
    except Exception as e:
        print(f"X Terminal test failed: {e}")
        return False

def test_agent_state():
    """Test agent state creation"""
    print("Testing Agent State...")
    
    try:
        from agent.enhanced_linear_agent import EnhancedAgentState, ExecutionMode
        
        state = EnhancedAgentState(
            task_description="Test task",
            execution_mode=ExecutionMode.SEQUENTIAL
        )
        
        print(f"✓ Agent state created: {state.task_description}")
        print(f"✓ Execution mode: {state.execution_mode}")
        
        return True
        
    except Exception as e:
        print(f"X Agent state test failed: {e}")
        return False

def run_simple_tests():
    """Run simplified test suite"""
    print("Enhanced SWE Agent - Simple Test Suite")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Terminal Test", test_terminal),
        ("Agent State Test", test_agent_state)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\nRunning: {test_name}")
        print("-" * 30)
        
        try:
            if test_func():
                print(f"✓ {test_name}: PASSED")
                passed += 1
            else:
                print(f"X {test_name}: FAILED")
        except Exception as e:
            print(f"X {test_name}: ERROR - {e}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! Enhanced SWE Agent is ready.")
        return True
    else:
        print("Some tests failed. Check configuration.")
        return False

if __name__ == "__main__":
    success = run_simple_tests()
    sys.exit(0 if success else 1)
