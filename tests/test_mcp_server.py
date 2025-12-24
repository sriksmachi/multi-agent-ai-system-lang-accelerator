"""
Quick test script for MCP endpoints.
Run this after starting the FastAPI server to verify MCP functionality.
"""

import requests
import json


BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("Test 1: Health Check")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()
    
    assert response.status_code == 200, "Health check failed"
    print("✅ Health check passed\n")


def test_list_mcp_tools():
    """Test MCP tools listing."""
    print("=" * 60)
    print("Test 2: List MCP Tools")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/mcp/tools")
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Protocol: {data['protocol']}")
        print(f"Number of tools: {len(data['tools'])}")
        
        for tool in data['tools']:
            print(f"\nTool: {tool['name']}")
            print(f"  Streaming: {tool['streaming']}")
            print(f"  Parameters: {len(tool['parameters'])}")
            for param in tool['parameters']:
                req = " (required)" if param['required'] else ""
                print(f"    - {param['name']}: {param['type']}{req}")
        
        assert data['protocol'] == 'mcp-streamable-1.0', "Wrong protocol version"
        assert len(data['tools']) > 0, "No tools found"
        print("\n✅ MCP tools listing passed\n")
    else:
        print(f"❌ Failed with status {response.status_code}")
        print(response.text)
        raise AssertionError("MCP tools listing failed")


def test_mcp_invoke_non_streaming():
    """Test MCP non-streaming invocation."""
    print("=" * 60)
    print("Test 3: MCP Non-Streaming Invocation")
    print("=" * 60)
    
    payload = {
        "tool": "generate_linkedin_post",
        "parameters": {
            "topic": "Testing MCP implementation"
        },
        "user_id": "test_user",
        "stream": False
    }
    
    print(f"Request payload: {json.dumps(payload, indent=2)}")
    print("\nInvoking tool (this may take 30-60 seconds)...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/mcp/invoke",
            json=payload,
            timeout=120
        )
        
        print(f"\nStatus: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Protocol: {data['protocol']}")
            print(f"Tool: {data['tool']}")
            print(f"User ID: {data['user_id']}")
            print(f"Trace ID: {data['trace_id']}")
            
            result = data['result']
            print(f"\nResult keys: {list(result.keys())}")
            print(f"Post length: {len(result.get('post_markdown', ''))} characters")
            print(f"Platform: {result.get('platform')}")
            print(f"Refinement count: {result.get('refinement_count')}")
            
            # Show first 200 chars of post
            post = result.get('post_markdown', '')
            print(f"\nPost preview:")
            print("-" * 60)
            print(post[:200] + "..." if len(post) > 200 else post)
            print("-" * 60)
            
            assert data['protocol'] == 'mcp-streamable-1.0', "Wrong protocol"
            assert 'result' in data, "No result in response"
            assert 'post_markdown' in result, "No post in result"
            print("\n✅ Non-streaming invocation passed\n")
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(response.text)
            raise AssertionError("Non-streaming invocation failed")
            
    except requests.Timeout:
        print("❌ Request timed out (>120s)")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def test_mcp_invoke_streaming():
    """Test MCP streaming invocation."""
    print("=" * 60)
    print("Test 4: MCP Streaming Invocation")
    print("=" * 60)
    
    payload = {
        "tool": "generate_linkedin_post",
        "parameters": {
            "topic": "Benefits of streaming APIs"
        },
        "user_id": "test_user_stream",
        "stream": True
    }
    
    print(f"Request payload: {json.dumps(payload, indent=2)}")
    print("\nStreaming response (this may take 30-60 seconds)...\n")
    
    try:
        response = requests.post(
            f"{BASE_URL}/mcp/invoke",
            json=payload,
            stream=True,
            timeout=120
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            chunk_count = 0
            content_chunks = []
            has_start = False
            has_content = False
            has_metadata = False
            has_end = False
            
            print("\nReceiving chunks:")
            print("-" * 60)
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        try:
                            chunk_data = json.loads(line[6:])
                            chunk_count += 1
                            chunk_type = chunk_data.get('chunk_type', 'unknown')
                            
                            if chunk_type == 'start':
                                has_start = True
                                print(f"[{chunk_count}] START: {chunk_data.get('metadata', {})}")
                            
                            elif chunk_type == 'content':
                                has_content = True
                                content = chunk_data.get('content', '')
                                content_chunks.append(content)
                                preview = content[:50].replace('\n', ' ')
                                print(f"[{chunk_count}] CONTENT: {len(content)} chars - {preview}...")
                            
                            elif chunk_type == 'metadata':
                                has_metadata = True
                                print(f"[{chunk_count}] METADATA: {chunk_data.get('metadata', {})}")
                            
                            elif chunk_type == 'end':
                                has_end = True
                                print(f"[{chunk_count}] END: {chunk_data.get('metadata', {})}")
                            
                            elif chunk_type == 'error':
                                print(f"[{chunk_count}] ERROR: {chunk_data.get('error')}")
                            
                        except json.JSONDecodeError as e:
                            print(f"Failed to parse chunk: {line[:100]}")
            
            print("-" * 60)
            print(f"\nTotal chunks: {chunk_count}")
            print(f"Content chunks: {len(content_chunks)}")
            print(f"Total content length: {sum(len(c) for c in content_chunks)} characters")
            
            # Validation
            assert has_start, "Missing start chunk"
            assert has_content, "Missing content chunks"
            assert has_end, "Missing end chunk"
            
            print("\n✅ Streaming invocation passed\n")
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(response.text)
            raise AssertionError("Streaming invocation failed")
            
    except requests.Timeout:
        print("❌ Request timed out (>120s)")
        raise
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


def test_mcp_invalid_tool():
    """Test MCP with invalid tool name."""
    print("=" * 60)
    print("Test 5: Invalid Tool Name")
    print("=" * 60)
    
    payload = {
        "tool": "nonexistent_tool",
        "parameters": {},
        "user_id": "test_user",
        "stream": False
    }
    
    response = requests.post(f"{BASE_URL}/mcp/invoke", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    assert response.status_code == 400, "Should return 400 for invalid tool"
    print("\n✅ Invalid tool handling passed\n")


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "MCP Server Tests" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print("\nEnsure the FastAPI server is running at http://localhost:8000\n")
    
    try:
        # Quick tests
        test_health()
        test_list_mcp_tools()
        test_mcp_invalid_tool()
        
        # Full workflow tests (slower)
        print("\n⚠️  The following tests invoke the full AI workflow and may take 1-2 minutes each...\n")
        test_mcp_invoke_non_streaming()
        test_mcp_invoke_streaming()
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed!")
        print("=" * 60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        exit(1)
    except requests.ConnectionError:
        print("\n❌ Connection failed. Is the server running at http://localhost:8000?\n")
        print("Start the server with: uvicorn api.main:app --reload\n")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
