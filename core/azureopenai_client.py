import os
import json
import traceback
import logging
import time
from datetime import date
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
 
from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.core.credentials import TokenCredential
from azure.identity import get_bearer_token_provider
from azure.core.exceptions import ClientAuthenticationError, ServiceRequestError
from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
 
# Load environment variables
load_dotenv()
 
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
 
logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
 
@dataclass
class AzureOpenAIConfig:
    """Configuration settings for Azure OpenAI client"""
    # TODO: Load from environment variables
    max_tokens: int = 4096
    temperature: float = 1
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 30
    max_retry_attempts: int = 3
    retry_delay: float = 1.0
 
class AzureOpenAIClient:
    def __init__(self, use_managed_identity=False, use_api_key=True):
        """Initialize the Azure OpenAI client with environment variables."""
        # Load environment variables from .env file
        load_dotenv()
        self.deployment_name = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        self.use_managed_identity = use_managed_identity
        self.use_api_key = use_api_key
        self.config = AzureOpenAIConfig()
        self._initialize_client()
 
    def _initialize_client(self):
        """Initialize the Azure OpenAI client with API key or managed identity"""
        try:
            # Check if API key authentication should be used
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            
            if self.use_api_key and api_key:
                # Use API key authentication (preferred to avoid tenant issues)
                logger.info("Using API key authentication for Azure OpenAI")
                self._client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    api_key=api_key,
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                    timeout=30
                )
            else:
                # Use token-based authentication (managed identity)
                logger.info("Using token-based authentication for Azure OpenAI")
                credential = self._get_credential()
 
                # Create token provider for Azure Cognitive Services
                token_provider = get_bearer_token_provider(
                    credential,
                    "https://cognitiveservices.azure.com/.default"
                )
 
                # Initialize Azure OpenAI client
                self._client = AzureOpenAI(
                    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
                    azure_ad_token_provider=token_provider,
                    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
                    timeout=30
                )
 
        except Exception as e:
            logger.error(f"Failed to initialize Azure OpenAI client: {e}")
            raise
 
    def _get_credential(self) -> TokenCredential:
        """Get appropriate Azure credential based on configuration"""
        try:
            if self.use_managed_identity:
                # Use managed identity for Azure resources
                logger.info("Using managed identity credential")
                return ManagedIdentityCredential()
            else:
                # Use default credential chain (includes managed identity, CLI, etc.)
                logger.info("Using default Azure credential")
                return DefaultAzureCredential()
 
        except Exception as e:
            logger.error(f"Failed to initialize Azure credential: {e}")
            raise ClientAuthenticationError(f"Authentication setup failed: {e}")    
 
    def _test_connection(self):
        """Test the connection to Azure OpenAI"""
        try:
            logger.info("Testing Azure OpenAI connection...")
            # Simple test message
            test_messages = "Hello, can you respond with 'Connection successful"
            response = self.generate_chat_completion(test_messages)
            logger.info("Azure OpenAI connection test successful")
        except Exception as e:
            logger.error(f"Connection test failed: {traceback.format_exc()}")
            logger.error(f"Azure OpenAI connection test failed, {e}")
 
    def generate_chat_completion(self, prompt, system_prompt="You are a helpful assistant.", max_tokens=None):
        """Generate chat completion using Azure OpenAI with OpenTelemetry GenAI semantic conventions."""
        
        with tracer.start_as_current_span(
            "gen_ai.client.operation",
            attributes={
                "gen_ai.system": "azure_openai",
                "gen_ai.request.model": self.deployment_name,
                "gen_ai.request.temperature": self.config.temperature,
                "gen_ai.request.max_tokens": max_tokens or self.config.max_tokens,
                "gen_ai.request.top_p": self.config.top_p,
                "gen_ai.request.frequency_penalty": self.config.frequency_penalty,
                "gen_ai.request.presence_penalty": self.config.presence_penalty,
                "gen_ai.operation.name": "chat",
            }
        ) as span:
            # Build completion parameters
            completion_params = {
                "model": self.deployment_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": self.config.temperature,
            }
            
            # Add max_completion_tokens if specified (newer models use this instead of max_tokens)
            if max_tokens:
                completion_params["max_completion_tokens"] = max_tokens
            
            # Log system message event with structured content
            span.add_event("gen_ai.system.message", {
                "gen_ai.event.content": json.dumps({"content": system_prompt})
            })
            
            # Log user message event with structured content
            span.add_event("gen_ai.user.message", {
                "gen_ai.event.content": json.dumps({"content": prompt})
            })
            
            # Add prompt preview to span (truncated for large prompts)
            prompt_preview = prompt[:500] if len(prompt) > 500 else prompt
            span.set_attribute("gen_ai.prompt.preview", prompt_preview)
            span.set_attribute("gen_ai.prompt.length", len(prompt))
            span.set_attribute("gen_ai.system_prompt.length", len(system_prompt))
            
            try:
                response = self._client.chat.completions.create(**completion_params)
                content = response.choices[0].message.content
                
                # Add GenAI semantic convention attributes
                if hasattr(response, 'usage') and response.usage:
                    span.set_attribute("gen_ai.usage.input_tokens", response.usage.prompt_tokens)
                    span.set_attribute("gen_ai.usage.output_tokens", response.usage.completion_tokens)
                    # Total tokens is not in GenAI spec but useful for monitoring
                    span.set_attribute("gen_ai.usage.total_tokens", response.usage.total_tokens)
                
                # Response metadata
                if hasattr(response, 'model'):
                    span.set_attribute("gen_ai.response.model", response.model)
                
                if hasattr(response, 'id'):
                    span.set_attribute("gen_ai.response.id", response.id)
                
                if response.choices and hasattr(response.choices[0], 'finish_reason'):
                    span.set_attribute("gen_ai.response.finish_reasons", [response.choices[0].finish_reason])
                
                # Add response preview
                response_preview = content[:500] if len(content) > 500 else content
                span.set_attribute("gen_ai.completion.preview", response_preview)
                span.set_attribute("gen_ai.completion.length", len(content))
                
                # Log assistant completion as gen_ai.choice event with structured content
                span.add_event("gen_ai.choice", {
                    "gen_ai.event.content": json.dumps({"content": content})
                })
                
                span.set_status(Status(StatusCode.OK))
                
                return content
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                logger.error(f"Azure OpenAI completion failed: {e}", exc_info=True)
                raise


def main():
    """
    Test function to verify Azure OpenAI client is working correctly.
    
    Tests:
    1. Environment variable validation
    2. Client initialization
    3. Simple chat completion
    4. Connection test
    """
    print("\n" + "="*80)
    print("AZURE OPENAI CLIENT TEST")
    print("="*80 + "\n")
    
    # Check required environment variables
    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT_NAME",
        "AZURE_OPENAI_API_VERSION",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("   Please check your .env file\n")
        return
    
    print("✅ Environment variables loaded")
    print(f"   Endpoint: {os.getenv('AZURE_OPENAI_ENDPOINT')}")
    print(f"   Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}")
    print(f"   API Version: {os.getenv('AZURE_OPENAI_API_VERSION')}\n")
    
    try:
        # Initialize client
        print("🚀 Initializing Azure OpenAI client...")
        client = AzureOpenAIClient(use_managed_identity=False)
        print("✅ Client initialized successfully\n")
        
        # Test connection
        print("🔍 Testing connection...")
        client._test_connection()
        print()
        
        # Test simple completion
        print("💬 Testing chat completion...")
        test_prompt = "What is artificial intelligence in one sentence?"
        print(f"   Prompt: {test_prompt}")
        
        response = client.generate_chat_completion(
            prompt=test_prompt,
            system_prompt="You are a helpful AI assistant. Be concise.",
        )
        
        print(f"\n   Response:")
        print("   " + "-"*76)
        print(f"   {response}")
        print("   " + "-"*76 + "\n")
        
        print("✅ All tests passed!\n")
        
        # Display configuration
        print("⚙️  Client Configuration:")
        print(f"   Max Tokens: {client.config.max_tokens}")
        print(f"   Temperature: {client.config.temperature}")
        print(f"   Top P: {client.config.top_p}")
        print(f"   Timeout: {client.config.timeout}s\n")
        
    except ClientAuthenticationError as e:
        print(f"\n❌ Authentication Error:")
        print(f"   {str(e)}")
        print("\n   Troubleshooting:")
        print("   - Check if you're logged in: az login")
        print("   - Verify your Azure credentials")
        print("   - Ensure you have access to the Azure OpenAI resource\n")
        
    except ServiceRequestError as e:
        print(f"\n❌ Service Request Error:")
        print(f"   {str(e)}")
        print("\n   Troubleshooting:")
        print("   - Check if the endpoint URL is correct")
        print("   - Verify the deployment name exists")
        print("   - Check network connectivity\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error:")
        print(f"   {type(e).__name__}: {str(e)}\n")
        logger.error("Test failed", exc_info=True)


if __name__ == "__main__":
    main()