# Data Pipeline - PDF Ingestion to Azure AI Search

This data pipeline processes PDF documents and ingests them into Azure AI Search for retrieval by the multi-agent system.

## Overview

The pipeline consists of two main steps:

1. **Create Search Index** - Creates the Azure AI Search index with text and vector search capabilities
2. **Process PDFs** - Parses PDFs, chunks content, generates embeddings, and uploads to Azure AI Search

## Prerequisites

### Required Environment Variables

Before running the pipeline, ensure these environment variables are set in your `.env` file:

```bash
# Azure Document Intelligence (for PDF parsing)
AZURE_DI_ENDPOINT=https://your-document-intelligence.cognitiveservices.azure.com/
AZURE_DI_KEY=your-document-intelligence-key

# Azure OpenAI (for embeddings)
AZURE_OPENAI_EMBEDDINGS_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_OPENAI_EMBEDDINGS_API_KEY=your-openai-api-key
AZURE_OPENAI_EMBEDDINGS_API_VERSION=2023-05-15
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-small

# Azure AI Search
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_ADMIN_KEY=your-search-admin-key
AZURE_SEARCH_INDEX_NAME=documents-index

# Optional Pipeline Configuration
CHUNK_SIZE=1000                    # Size of text chunks (default: 1000)
CHUNK_OVERLAP=200                  # Overlap between chunks (default: 200)
EMBEDDING_BATCH_SIZE=50            # Batch size for embeddings (default: 50)
EMBEDDING_BATCH_DELAY=2.0          # Delay between batches in seconds (default: 2.0)
```

### Required Azure Resources

You'll need the following Azure resources provisioned:

- **Azure Document Intelligence** - For parsing PDF files
- **Azure OpenAI** - For generating text embeddings
- **Azure AI Search** - For storing and searching documents

## Setup Instructions

### Step 1: Add Your PDF Files

1. Copy your PDF documents to the `data/` folder:

```bash
# Navigate to the datapipeline directory
cd datapipeline

# Create data folder if it doesn't exist
mkdir data

# Copy your PDFs
cp /path/to/your/documents/*.pdf data/
```

The `data/` folder structure:
```
datapipeline/
├── data/
│   ├── document1.pdf
│   ├── document2.pdf
│   └── document3.pdf
├── create_search_index.py
├── run_datapipeline.py
└── readme.md
```

### Step 2: Create the Azure AI Search Index

Run the index creation script to set up your search index:

```bash
python create_search_index.py
```

**What this does:**
- Creates an Azure AI Search index with the name specified in `AZURE_SEARCH_INDEX_NAME`
- Configures text search, vector search, and semantic search capabilities
- If the index already exists, it will skip creation

**Options:**
```bash
# Delete existing index and recreate (use with caution!)
python create_search_index.py --delete-existing

# Use a custom index name
python create_search_index.py --index-name my-custom-index
```

**Expected Output:**
```
✅ Index 'documents-index' created successfully
```

### Step 3: Run the Data Pipeline

Process your PDFs and ingest them into Azure AI Search:

```bash
python run_datapipeline.py
```

**What this does:**
1. Scans the `data/` folder for PDF files
2. Parses each PDF using Azure Document Intelligence
3. Chunks the text content intelligently
4. Generates embeddings using Azure OpenAI
5. Uploads documents to Azure AI Search with merge-or-upload strategy
6. Tracks processing status in `data/pipeline_state.json`

**Expected Output:**
```
📦 PDF Data Pipeline - Starting...
   Found 3 PDF files in data/

📄 Parsing PDF: document1.pdf
   ✅ Parsed 15 pages
📝 Chunking content...
   ✅ Created 42 chunks
🔢 Generating embeddings...
   ✅ Generated 42 embeddings
☁️  Uploading to Azure AI Search...
   ✅ Uploaded 42 documents

✅ Pipeline completed successfully!
   Total documents: 3
   Total chunks: 156
   Processing time: 45.2 seconds
```

## Pipeline Features

### Intelligent Chunking

The pipeline uses `RecursiveCharacterTextSplitter` to intelligently chunk documents:
- Maintains semantic coherence
- Respects natural boundaries (paragraphs, sentences)
- Configurable chunk size and overlap

### Incremental Processing

- **State Tracking** - Stores processing state in `data/pipeline_state.json`
- **Skip Processed Files** - Avoids reprocessing unchanged PDFs
- **Resume Support** - Can resume from where it left off if interrupted

### Error Handling

- Validates all required environment variables before starting
- Continues processing remaining files if one fails
- Provides detailed error messages with troubleshooting guidance

## Troubleshooting

### Missing Environment Variables

**Error:** `❌ Missing required environment variables: AZURE_DI_ENDPOINT, AZURE_DI_KEY`

**Solution:** Check your `.env` file and ensure all required variables are set.

### No PDF Files Found

**Error:** `❌ No PDF files found in data/`

**Solution:** Copy your PDF files to the `datapipeline/data/` folder.

### Azure Service Errors

**Error:** `Failed to parse PDF: Unauthorized`

**Solution:** Verify your Azure credentials (keys and endpoints) are correct and not expired.

### Rate Limiting

**Error:** `Rate limit exceeded`

**Solution:** Increase `EMBEDDING_BATCH_DELAY` in your `.env` file to add more delay between API calls.

## Pipeline State File

The pipeline maintains state in `data/pipeline_state.json`:

```json
{
  "last_run": "2025-12-19T10:30:00",
  "processed_files": {
    "document1.pdf": {
      "status": "completed",
      "chunks": 42,
      "processed_at": "2025-12-19T10:25:00"
    }
  }
}
```

**To force reprocessing:** Delete `data/pipeline_state.json`

## Advanced Usage

### Custom Chunking Configuration

Adjust chunking parameters in `.env`:

```bash
CHUNK_SIZE=1500          # Larger chunks for more context
CHUNK_OVERLAP=300        # More overlap for better retrieval
```

### Batch Processing Control

Control embedding generation rate:

```bash
EMBEDDING_BATCH_SIZE=100    # Process more per batch
EMBEDDING_BATCH_DELAY=1.0   # Faster processing (if rate limits allow)
```

### Index Management

```bash
# Delete and recreate index
python create_search_index.py --delete-existing

# Create with different name
export AZURE_SEARCH_INDEX_NAME=production-index
python create_search_index.py
```

## Next Steps

After ingesting your documents:

1. **Test Search** - Use Azure Portal to query your index
2. **Run the Agent** - Start the multi-agent system to generate posts using your data
3. **Monitor Usage** - Check Azure Portal for search and embedding usage metrics

## Support

For issues or questions:
- Check the main project README.md
- Review Azure service logs in Azure Portal
- Verify all environment variables are correctly set
