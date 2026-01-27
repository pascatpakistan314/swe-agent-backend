#!/usr/bin/env python3
"""
Windows-compatible test for Enhanced SWE Agent
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

def test_terminal_import():
    """Test terminal import"""
    print("Testing terminal import...")
    
    try:
        from agent.tools.terminal import get_terminal_manager, terminal_execute
        print("SUCCESS: Terminal tools imported")
        return True
    except Exception as e:
        print(f"FAILED: Terminal import error: {e}")
        return False

def test_terminal_basic():
    """Test basic terminal functionality"""
    print("Testing basic terminal functionality...")
    
    try:
        from agent.tools.terminal import get_terminal_manager
        
        manager = get_terminal_manager()
        session = manager.create_session("test")
        
        print(f"SUCCESS: Terminal session created: {session['session_id']}")
        
        # Test a simple command
        result = manager.execute_command("echo Hello", "test")
        print(f"SUCCESS: Command executed, got: {len(result.get('output', ''))} chars output")
        
        manager.close_session("test")
        print("SUCCESS: Session closed")
        
        return True
    except Exception as e:
        print(f"FAILED: Terminal test error: {e}")
        return False

def test_agent_imports():
    """Test enhanced agent imports"""
    print("Testing enhanced agent imports...")
    
    try:
        from agent.enhanced_linear_agent import EnhancedLinearAgent, ExecutionMode
        print("SUCCESS: Enhanced linear agent imported")
        
        from agent.integrated_graph import run_integrated_swe_agent
        print("SUCCESS: Integrated graph imported")
        
        return True
    except Exception as e:
        print(f"FAILED: Agent import error: {e}")
        return False

def run_tests():
    """Run all tests"""
    print("Enhanced SWE Agent - Windows Test")
    print("=" * 40)
    
    tests = [
        ("Terminal Import", test_terminal_import),
        ("Terminal Basic", test_terminal_basic),
        ("Agent Imports", test_agent_imports)
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\n--- {name} ---")
        if test_func():
            passed += 1
        else:
            print(f"FAILED: {name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    return passed == total

if __name__ == "__main__":
    success = run_tests()
    if success:
        print("\nAll tests passed! Enhanced SWE Agent is ready.")
    else:
        print("\nSome tests failed. Check configuration.")
    sys.exit(0 if success else 1)
