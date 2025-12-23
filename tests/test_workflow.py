"""
Quick test script for the post generator workflow.
Runs the workflow without starting the API server.
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# Import after path setup
from workflows import run_post_generator

def test_workflow():
    """Test the complete workflow."""
    print("\n" + "="*80)
    print("🚀 Testing Post Generator Workflow")
    print("="*80 + "\n")
    
    # Test parameters
    user_id = "test-user-001"
    topic = "Benefits of AI in healthcare"
    platform = "linkedin"
    tone = "professional"
    
    print(f"📝 Topic: {topic}")
    print(f"👤 User ID: {user_id}")
    print(f"📱 Platform: {platform}")
    print(f"🎭 Tone: {tone}\n")
    
    try:
        # Run the workflow
        result = run_post_generator(
            user_id=user_id,
            topic=topic,
            platform=platform,
            tone=tone,
            max_refinements=2
        )
        
        print("\n✅ Workflow completed successfully!")
        print(f"📊 Scores: {result.get('scores', {})}")
        print(f"🔄 Refinements: {result.get('refinement_count', 0)}")
        print(f"🔗 Trace ID: {result.get('trace_id', 'N/A')}")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_workflow()
