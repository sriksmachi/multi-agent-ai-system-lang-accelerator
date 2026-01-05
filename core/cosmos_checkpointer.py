"""
Simple Cosmos DB checkpoint repository for LangGraph.

This module implements a checkpoint saver for LangGraph that persists graph execution
state to Azure Cosmos DB. Checkpoints are essential for:

1. **State Persistence**: Saves the complete state of a graph at each step
2. **Resume Capability**: Allows resuming interrupted workflows from the last checkpoint
3. **History Tracking**: Maintains a history of state changes for debugging and auditing
4. **Fault Tolerance**: Recovers from failures without losing progress

Architecture:
- Thread ID serves as the Cosmos DB partition key for efficient querying
- Each checkpoint is a JSON document containing:
  * Checkpoint ID (unique identifier for this state snapshot)
  * Graph state (all channel values and execution context)
  * Metadata (timing, version info)
  * Timestamp (creation time for ordering)
  * TTL (auto-delete after 60 days by default)

Configuration (via environment variables):
- COSMOSDB_ENDPOINT: Connection string for Cosmos DB account
- COSMOS_DB_NAME: Database name (default: "content-generation-db")
- COSMOS_CONTAINER_NAME: Container name (default: "chat-history")
- USE_MANAGED_IDENTITY: Use Azure Managed Identity (default: false)
- SESSION_TTL_SECONDS: TTL for checkpoints in seconds (default: 5184000 = 60 days)

Example Usage:
    from lib.cosmos_db_checkpointer import get_checkpointer
    from langgraph.graph import StateGraph
    
    checkpointer = get_checkpointer()
    
    # Create a graph with checkpointer for state persistence
    graph = StateGraph(MyGraphState)
    graph.add_node("process", my_node_function)
    compiled_graph = graph.compile(checkpointer=checkpointer)
    
    # Run graph - state automatically saved at each step
    config = {"configurable": {"thread_id": "user-123"}}
    result = compiled_graph.invoke(input_state, config=config)
    
    # Later: resume from saved state
    result = compiled_graph.invoke(input_state, config=config)

Stores and retrieves graph execution state from Azure Cosmos DB.
"""

import os
import json
import time
import logging
import asyncio
import traceback
from typing import Optional, Iterator, Dict, Any, AsyncIterator
from datetime import datetime
from dotenv import load_dotenv

from azure.identity import DefaultAzureCredential, ManagedIdentityCredential, AzureCliCredential
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import CosmosHttpResponseError
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    CheckpointTuple,
    CheckpointMetadata,
    Checkpoint,
    ChannelVersions,
    PendingWrite,
    get_checkpoint_id,
)

logger = logging.getLogger(__name__)

load_dotenv()

class CosmosDBCheckpointer(BaseCheckpointSaver):
    """
    Azure Cosmos DB-backed checkpoint saver for LangGraph.
    
    This class implements the LangGraph BaseCheckpointSaver interface to persist
    graph execution state to Azure Cosmos DB. It enables:
    
    1. **Automatic State Persistence**: Every step in the graph execution creates
       a checkpoint in Cosmos DB for recovery and history tracking.
    
    2. **Thread-based Partitioning**: Uses thread_id as the partition key for
       efficient queries and isolation between concurrent users/sessions.
    
    3. **Graceful Degradation**: If Cosmos DB is unavailable, the graph still
       executes but without persistence (checkpoints logged but not saved).
    
    4. **TTL Auto-cleanup**: Checkpoints automatically expire after the configured
       TTL period (default 60 days) to manage storage costs.
    
    Attributes:
        endpoint (str): Cosmos DB account endpoint URL
        database_name (str): Database name containing checkpoints
        container_name (str): Container name for checkpoint documents
        use_managed_identity (bool): Whether to use Azure Managed Identity auth
        ttl_seconds (int): Time-to-live for checkpoints in seconds
        container: Cosmos DB container client (None if connection failed)
    
    Methods:
        put(): Save a checkpoint after a graph step
        get_tuple(): Retrieve a specific checkpoint or the latest one
        list(): List all checkpoints for a thread
        put_writes(): Reserved for future use (not implemented)
    
    Async Methods:
        All methods have async versions (aput, aget_tuple, alist, aput_writes)
        which delegate to their sync counterparts.
    """

    def __init__(self):
        """
        Initialize Cosmos DB checkpointer from environment variables.
        
        This constructor reads all configuration from environment variables,
        making it compatible with Azure App Service, Function Apps, and
        container deployments. It gracefully handles connection failures.
        
        Environment Variables:
            COSMOSDB_ENDPOINT (required): Cosmos DB account endpoint
                Example: https://myaccount.documents.azure.com:443/
            COSMOS_DB_NAME (optional): Database name
                Default: "content-generation-db"
            COSMOS_CONTAINER_NAME (optional): Container name
                Default: "chat-history"
            USE_MANAGED_IDENTITY (optional): Enable managed identity auth
                Default: "false"
                Set to "true" for Azure-hosted deployments
            SESSION_TTL_SECONDS (optional): Checkpoint expiration time
                Default: 5184000 (60 days)
        
        Graceful Degradation:
            If COSMOSDB_ENDPOINT is not set, the checkpointer initializes
            but self.container remains None. The graph can still run, but
            checkpoints won't be persisted to Cosmos DB.
        
        Authentication:
            - With Managed Identity: Uses DefaultAzureCredential with the
              identity assigned to the deployment (App Service, etc.)
            - Without Managed Identity: Still uses DefaultAzureCredential
              which tries multiple auth methods (environment variables,
              local Azure CLI credentials, etc.)
        """
        super().__init__()

        self.endpoint = os.getenv("COSMOS_ENDPOINT")
        self.database_name = os.getenv("COSMOS_DATABASE_NAME", "content-generation-db")
        self.container_name = os.getenv("COSMOS_CHECKPOINTS_CONTAINER", "chat-history")
        self.use_managed_identity = os.getenv("USE_MANAGED_IDENTITY", "false").lower() == "true"
        self.ttl_seconds = int(os.getenv("SESSION_TTL_SECONDS", "5184000"))  # 60 days

        self.client = None
        self.database = None
        self.container = None

        if not self.endpoint:
            logger.warning("COSMOSDB_ENDPOINT not configured. Checkpointer disabled.")
            return

        self._connect()

    def _connect(self):
        """
        Establish connection to Cosmos DB.
        
        This method initializes the Cosmos DB client, database, and container
        clients. It's called only if COSMOSDB_ENDPOINT is configured.
        
        Error Handling:
            If connection fails for any reason (network, credentials,
            invalid endpoint, etc.), all client objects are set to None
            and the checkpointer operates in degraded mode. This allows
            the graph to continue running without persistence.
        
        Connection Flow:
            1. Create CosmosClient with DefaultAzureCredential
            2. Get database client (lazy-initialized)
            3. Get container client (lazy-initialized)
        
        Log Levels:
            - INFO: Successful connection
            - ERROR: Connection failure (with exception details)
        """
        try:
            if self.use_managed_identity:
                logger.info("Connecting to Cosmos DB with managed identity")
                credential = ManagedIdentityCredential()
                self.client = CosmosClient(self.endpoint, credential=credential)
            else:
                logger.info("Connecting to Cosmos DB with key based credentials")
                credential = AzureCliCredential()
                self.client = CosmosClient(self.endpoint, credential=credential)

            self.database = self.client.get_database_client(self.database_name)
            self.container = self.database.get_container_client(self.container_name)

            logger.info(f"Connected to Cosmos DB: {self.database_name}/{self.container_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Cosmos DB: {e}")
            self.client = None
            self.database = None
            self.container = None

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Store a checkpoint in Cosmos DB.
        
        Called by LangGraph after each node execution to save the graph state.
        This enables resuming the workflow later from the exact point of failure.
        
        Args:
            config: LangGraph runtime config containing thread_id in config["configurable"]
            checkpoint: Complete graph state (all channel values)
            metadata: Metadata about this checkpoint (version numbers, step count)
            new_versions: Dictionary tracking which channels changed in this step
        
        Returns:
            RunnableConfig with thread_id and checkpoint_id for future retrieval
        
        Document Structure (saved to Cosmos DB):
            {
                "id": checkpoint["id"],              # Unique checkpoint ID
                "thread_id": thread_id,             # Partition key for queries
                "checkpoint": {...},                # Full graph state
                "metadata": {...},                  # Version info, timing
                "timestamp": int(time.time()),      # Creation timestamp
                "ttl": 5184000                      # Auto-expire after 60 days
            }
        
        Error Handling:
            - 409 Conflict: Checkpoint already exists (idempotent operation)
            - Other errors: Logged but don't prevent graph execution
            - If container is unavailable: Logs warning and continues
        
        Performance:
            Cosmos DB write is synchronous. For high-volume applications,
            consider batching or implementing async writes.
        """
        if not self.container:
            logger.warning("Cosmos container not available. Checkpoint not saved.")
            return config

        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_id = checkpoint["id"]

            # Create document
            doc = {
                "id": checkpoint_id,
                "thread_id": thread_id,
                "checkpoint": checkpoint,
                "metadata": metadata,
                "timestamp": int(time.time()),
                "ttl": self.ttl_seconds,
            }

            self.container.create_item(doc)
            logger.debug(f"Saved checkpoint: thread_id={thread_id}, checkpoint_id={checkpoint_id}")

            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                }
            }
        except CosmosHttpResponseError as e:
            if e.status_code == 409:  # Conflict
                logger.debug(f"Checkpoint already exists: {checkpoint_id}")
            else:
                logger.error(f"Error saving checkpoint: {e}")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")

        return config

    def put_writes(
        self,
        config: RunnableConfig,
        writes,
        task_id: str,
    ) -> None:
        pass

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve a checkpoint tuple from Cosmos DB.
        
        This method fetches either a specific checkpoint by ID or the latest
        checkpoint for a thread. Called when resuming a workflow or accessing
        the current state.
        
        Args:
            config: LangGraph runtime config containing:
                - config["configurable"]["thread_id"]: Thread/session ID
                - config["configurable"].get("checkpoint_id"): Optional specific ID
        
        Returns:
            CheckpointTuple containing:
                - config: Runtime config with thread_id and checkpoint_id
                - checkpoint: The full graph state at this point
                - metadata: Version info and metadata
            Returns None if no checkpoint found or container unavailable
        
        Query Logic:
            If checkpoint_id provided:
                SELECT * FROM c WHERE c.id = @id AND c.thread_id = @thread_id
                Fetches the exact checkpoint (useful for history navigation)
            
            If checkpoint_id not provided:
                SELECT TOP 1 * FROM c 
                WHERE c.thread_id = @thread_id 
                ORDER BY c.timestamp DESC
                Fetches the latest checkpoint (used when resuming)
        
        Error Handling:
            - Missing checkpoint: Returns None (graph starts fresh)
            - Query errors: Logged and return None
            - Container unavailable: Returns None immediately
        
        Performance:
            Partition key (thread_id) is used in WHERE clause for efficient
            single-partition queries. Should complete in <50ms for typical data.
        """
        if not self.container:
            return None

        try:
            thread_id = config["configurable"]["thread_id"]
            checkpoint_id = get_checkpoint_id(config)

            # Build query
            if checkpoint_id:
                query = "SELECT * FROM c WHERE c.id = @id AND c.thread_id = @thread_id"
                parameters = [
                    {"name": "@id", "value": checkpoint_id},
                    {"name": "@thread_id", "value": thread_id},
                ]
            else:
                # Get latest checkpoint
                query = "SELECT TOP 1 * FROM c WHERE c.thread_id = @thread_id ORDER BY c.timestamp DESC"
                parameters = [{"name": "@thread_id", "value": thread_id}]

            items = list(self.container.query_items(
                query=query,
                parameters=parameters,
            ))

            if not items:
                return None

            item = items[0]

            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": item["id"],
                    }
                },
                checkpoint=item["checkpoint"],
                metadata=item["metadata"],
            )
        except Exception as e:
            logger.error(f"Error retrieving checkpoint: {e}")
            return None

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        List all checkpoints for a thread in reverse chronological order.
        
        Returns an iterator of all checkpoints for a thread, most recent first.
        Useful for auditing, debugging, and implementing checkpoint history UIs.
        
        Args:
            config: LangGraph runtime config containing thread_id
            filter: Optional filter dict (not currently implemented)
            before: Optional checkpoint to list before (not currently implemented)
            limit: Maximum number of checkpoints to return
                If None, returns all checkpoints (limited by Cosmos DB max items)
        
        Yields:
            CheckpointTuple for each checkpoint, ordered by timestamp DESC
        
        Query:
            SELECT TOP {limit} * FROM c 
            WHERE c.thread_id = @thread_id 
            ORDER BY c.timestamp DESC
        
        Generator Pattern:
            Uses yield to return checkpoints one at a time, enabling:
            - Memory-efficient processing of many checkpoints
            - Early termination (don't fetch all if only need first N)
            - Streaming to clients without buffering
        
        Error Handling:
            - No checkpoints: Generator returns empty (no exception)
            - Query errors: Logged, generator returns empty
            - Container unavailable: Early return (empty generator)
        
        Performance Considerations:
            - Partition key filter enables single-partition query
            - Cursor automatically pages through results
            - Typical pagination: 100 items per request
        """
        if not self.container or not config:
            return

        try:
            thread_id = config["configurable"]["thread_id"]

            query = "SELECT * FROM c WHERE c.thread_id = @thread_id ORDER BY c.timestamp DESC"
            if limit:
                query = f"SELECT TOP {limit} * FROM c WHERE c.thread_id = @thread_id ORDER BY c.timestamp DESC"

            parameters = [{"name": "@thread_id", "value": thread_id}]

            items = self.container.query_items(
                query=query,
                parameters=parameters,
            )

            for item in items:
                yield CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_id": item["id"],
                        }
                    },
                    checkpoint=item["checkpoint"],
                    metadata=item["metadata"],
                )
        except Exception as e:
            logger.error(f"Error listing checkpoints: {e}")

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        Async version of get_tuple().
        
        Currently delegates to the sync version. In the future, this could be
        implemented with true async I/O for better concurrency handling.
        """
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        Async version of put().
        
        Currently delegates to the sync version. In the future, this could be
        implemented with true async I/O and batching for performance.
        """
        return self.put(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config: RunnableConfig, writes, task_id: str) -> None:
        """Async version of put_writes(). Not implemented."""
        self.put_writes(config, writes, task_id)

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """
        Async version of list().
        
        Returns an async iterator yielding checkpoints one at a time.
        Currently delegates to sync version but provides async interface
        compatible with async LangGraph workflows.
        """
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item


def get_checkpointer() -> CosmosDBCheckpointer:
    """
    Factory function to create a CosmosDBCheckpointer instance.
    
    This is the recommended way to instantiate the checkpointer. It allows
    for easy mocking/substitution in tests and future changes to initialization.
    
    Returns:
        CosmosDBCheckpointer: Initialized checkpointer instance
        
        Important: The returned instance may have self.container = None if:
        - COSMOSDB_ENDPOINT environment variable is not set
        - Connection to Cosmos DB fails
        
        The checkpointer will still function in degraded mode (no persistence)
        but logs a warning so developers know the issue exists.
    
    Usage:
        from lib.cosmos_db_checkpointer import get_checkpointer
        checkpointer = get_checkpointer()
        graph = StateGraph(MyState).compile(checkpointer=checkpointer)
    
    Testing:
        For unit tests, you can mock this function to return a no-op
        checkpointer, or create an instance with COSMOSDB_ENDPOINT unset.
    """
    return CosmosDBCheckpointer()
