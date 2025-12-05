"""
Azure AI Search Index Creator

Creates an Azure AI Search index with:
- Text search fields
- Vector search configuration
- Semantic search capabilities
"""

import os
import sys
from typing import Optional
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)

load_dotenv()


def create_search_index(
    index_name: str = "documents-index",
    delete_if_exists: bool = False
) -> bool:
    """
    Create Azure AI Search index with text and vector search capabilities.
    
    Args:
        index_name: Name of the index to create
        delete_if_exists: Whether to delete existing index before creating
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Get configuration from environment
    search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
    search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
    
    if not search_endpoint or not search_key:
        print("❌ Error: AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_ADMIN_KEY must be set in .env")
        return False
    
    # Initialize client
    credential = AzureKeyCredential(search_key)
    index_client = SearchIndexClient(endpoint=search_endpoint, credential=credential)
    
    try:
        # Delete existing index if requested
        if delete_if_exists:
            try:
                index_client.delete_index(index_name)
                print(f"🗑️  Deleted existing index: {index_name}")
            except Exception:
                pass  # Index doesn't exist, that's fine
        
        # Check if index already exists
        try:
            existing_index = index_client.get_index(index_name)
            print(f"✅ Index '{index_name}' already exists")
            return True
        except Exception:
            pass  # Index doesn't exist, continue with creation
        
        # Define index fields
        fields = [
            SimpleField(
                name="id",
                type=SearchFieldDataType.String,
                key=True,
                filterable=True,
            ),
            SearchableField(
                name="content",
                type=SearchFieldDataType.String,
                searchable=True,
                retrievable=True,
            ),
            SearchableField(
                name="title",
                type=SearchFieldDataType.String,
                searchable=True,
                retrievable=True,
                filterable=True,
                sortable=True,
            ),
            SimpleField(
                name="source",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
                retrievable=True,
            ),
            SimpleField(
                name="page_number",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
                retrievable=True,
            ),
            SimpleField(
                name="chunk_id",
                type=SearchFieldDataType.Int32,
                filterable=True,
                sortable=True,
                retrievable=True,
            ),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,  # text-embedding-3-small dimension
                vector_search_profile_name="my-vector-profile",
            ),
            SimpleField(
                name="metadata",
                type=SearchFieldDataType.String,
                retrievable=True,
            ),
        ]
        
        # Configure vector search
        vector_search = VectorSearch(
            algorithms=[
                HnswAlgorithmConfiguration(
                    name="my-hnsw-config",
                    parameters={
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine"
                    }
                )
            ],
            profiles=[
                VectorSearchProfile(
                    name="my-vector-profile",
                    algorithm_configuration_name="my-hnsw-config",
                )
            ]
        )
        
        # Configure semantic search
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="title"),
                content_fields=[SemanticField(field_name="content")],
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        # Create the index
        index = SearchIndex(
            name=index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search,
        )
        
        # Create index
        result = index_client.create_index(index)
        print(f"✅ Successfully created index: {result.name}")
        print(f"   - Text search: enabled")
        print(f"   - Vector search: enabled (1536 dimensions)")
        print(f"   - Semantic search: enabled")
        return True
        
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Azure AI Search Index Creator")
    print("=" * 60)
    
    # Parse command line arguments
    delete_existing = "--delete" in sys.argv or "-d" in sys.argv
    index_name = os.getenv("AZURE_SEARCH_INDEX_NAME", "documents-index")
    
    if delete_existing:
        print(f"⚠️  Will delete existing index if it exists")
    
    success = create_search_index(
        index_name=index_name,
        delete_if_exists=delete_existing
    )
    
    if success:
        print("\n✅ Index is ready for data ingestion!")
        print(f"   Run: python datapipeline/run_datapipeline.py")
    else:
        print("\n❌ Index creation failed")
        sys.exit(1)
