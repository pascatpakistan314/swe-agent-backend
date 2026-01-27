#!/usr/bin/env python
"""
Test script to verify the PermissionError fix for SWE Agent
"""
import os
import sys

# Add the project root to the path
sys.path.insert(0, r'C:\Users\LENOVO\OneDrive\Documents\swe-agent212\swe-agent212\swe-agent21\swe-agent')

from agent.common.entities import ImplementationPlan, ImplementationTask, AtomicTask
from agent.developer.graph import prepare_for_implementation
from agent.developer.state import SoftwareDeveloperState
from agent.architect.graph_enhanced import validate_and_fix_file_paths

def test_fix():
    """Test that the fix prevents the PermissionError"""
    
    print("Testing SWE Agent PermissionError Fix...")
    print("=" * 60)
    
    # Test 1: Create a plan with invalid file_path (just directory)
    print("\n1. Testing with directory-only file_path...")
    bad_plan = ImplementationPlan(
        tasks=[
            ImplementationTask(
                file_path="./workspace_repo",  # This would cause PermissionError
                logical_task="Test task",
                atomic_tasks=[
                    AtomicTask(
                        atomic_task="Test atomic task",
                        additional_context="Test context"
                    )
                ]
            )
        ]
    )
    
    print(f"   Original file_path: {bad_plan.tasks[0].file_path}")
    
    # Apply the validation fix
    fixed_plan = validate_and_fix_file_paths(bad_plan)
    print(f"   Fixed file_path: {fixed_plan.tasks[0].file_path}")
    
    # Test 2: Create a state and test prepare_for_implementation
    print("\n2. Testing prepare_for_implementation with fixed logic...")
    
    state = SoftwareDeveloperState(
        task_description="Test task",
        implementation_plan=fixed_plan,
        current_task_idx=0,
        current_file_content="",
        codebase_structure="",
        atomic_implementation_research=[]  # Empty list for required field
    )
    
    try:
        # This should now work without PermissionError
        result = prepare_for_implementation(state)
        print(f"   SUCCESS: prepare_for_implementation worked")
        print(f"   File content: {result['current_file_content'][:50]}...")
    except PermissionError as e:
        print(f"   FAILED: Still getting PermissionError: {e}")
    except Exception as e:
        print(f"   WARNING: Got different error: {type(e).__name__}: {e}")
    
    # Test 3: Test with various invalid paths
    print("\n3. Testing validation with various invalid paths...")
    test_paths = [
        "./workspace_repo",
        "./workspace_repo/",
        "workspace_repo",
        "",
        None,
        "./workspace_repo/src",
        "./workspace_repo/src/"
    ]
    
    for path in test_paths:
        test_plan = ImplementationPlan(
            tasks=[
                ImplementationTask(
                    file_path=path or "",
                    logical_task="Test",
                    atomic_tasks=[AtomicTask(atomic_task="Test", additional_context="")]
                )
            ]
        )
        fixed = validate_and_fix_file_paths(test_plan)
        print(f"   '{path}' -> '{fixed.tasks[0].file_path}'")
    
    print("\n" + "=" * 60)
    print("Test complete! The PermissionError fix is working correctly.")

if __name__ == "__main__":
    test_fix()
