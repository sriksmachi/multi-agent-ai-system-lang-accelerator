# multi-agent-ai-system-lang-accelerator
A solution accelerator for building scalable, observable, reliable Multi-Agent systems.

## PDF Data Pipeline

This project includes a data pipeline for processing PDFs and uploading them to Azure AI Search with text and vector search capabilities.

### Pipeline Features

- **Parse**: Extract text from PDFs using Azure Document Intelligence
- **Chunk**: Intelligently split content with configurable size and overlap
- **Embed**: Generate embeddings using Azure OpenAI (text-embedding-3-small)
- **Upload**: Merge-or-upload strategy to Azure AI Search (idempotent re-ingestion)

### Prerequisites

1. **Azure Services Required**:
   - Azure Document Intelligence (for PDF parsing)
   - Azure OpenAI (for embeddings)
   - Azure AI Search (for storage and retrieval)

2. **Environment Variables**:
   Add the following to your `.env` file:

   ```bash
   # Azure Document Intelligence
   AZURE_DI_ENDPOINT=https://your-di-service.cognitiveservices.azure.com/
   AZURE_DI_KEY=your-di-key

   # Azure OpenAI (Embeddings)
   AZURE_OPENAI_EMBEDDINGS_ENDPOINT=https://your-openai-service.openai.azure.com/
   AZURE_OPENAI_EMBEDDINGS_API_KEY=your-openai-key
   AZURE_OPENAI_EMBEDDINGS_API_VERSION=2023-05-15
   AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT=text-embedding-3-small

   # Azure AI Search
   AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
   AZURE_SEARCH_ADMIN_KEY=your-search-admin-key
   AZURE_SEARCH_INDEX_NAME=documents-index

   # Optional: Pipeline Configuration
   CHUNK_SIZE=1000
   CHUNK_OVERLAP=200
   EMBEDDING_BATCH_SIZE=50
   EMBEDDING_BATCH_DELAY=2.0
   ```

3. **Install Dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

### Running the Pipeline

#### Step 1: Create the Azure AI Search Index

Create the search index with text, vector, and semantic search capabilities:

```powershell
python datapipeline/create_search_index.py
```

**Options**:
- Use `--delete` or `-d` flag to delete and recreate the index:
  ```powershell
  python datapipeline/create_search_index.py --delete
  ```

#### Step 2: Add PDFs

Place your PDF files in the `datapipeline/data/` folder:

```powershell
# Create data folder if it doesn't exist
New-Item -ItemType Directory -Path "datapipeline/data" -Force

# Copy your PDFs to the data folder
Copy-Item "C:\path\to\your\pdfs\*.pdf" "datapipeline/data\"
```

#### Step 3: Run the Data Pipeline

Process all PDFs and upload to Azure AI Search:

```powershell
python datapipeline/run_datapipeline.py
```

**Options**:
- Specify a custom data directory:
  ```powershell
  python datapipeline/run_datapipeline.py "C:\path\to\your\pdfs"
  ```

### How It Works

1. **Index Creation** (`create_search_index.py`):
   - Creates an Azure AI Search index with:
     - Text search fields (content, title, source)
     - Vector search (1536 dimensions for text-embedding-3-small)
     - Semantic search capabilities
     - Metadata fields (page numbers, chunk IDs)
   - Checks if index exists before creating (idempotent)

2. **Data Pipeline** (`run_datapipeline.py`):
   - **Parse**: Uses Azure Document Intelligence to extract text from each page
   - **Chunk**: Splits content using RecursiveCharacterTextSplitter with smart separators
   - **Embed**: Generates embeddings in batches with rate limiting
   - **Upload**: Uses merge-or-upload to handle re-ingestion gracefully

### Re-Running the Pipeline

The pipeline is designed to be **idempotent**:
- Same PDFs will update existing documents (based on document ID hash)
- You can safely re-run the pipeline to update content
- No duplicate documents will be created

### Troubleshooting

**Missing Environment Variables**:
```
❌ Missing required environment variables: AZURE_SEARCH_ENDPOINT, AZURE_SEARCH_ADMIN_KEY
```
→ Check your `.env` file has all required variables

**No PDFs Found**:
```
⚠️  No PDF files found in: datapipeline/data
```
→ Add PDF files to the `datapipeline/data/` folder

**Rate Limiting Errors**:
- Adjust `EMBEDDING_BATCH_SIZE` (reduce from 50 to 25)
- Increase `EMBEDDING_BATCH_DELAY` (increase from 2.0 to 5.0 seconds)

**Index Already Exists**:
- The index creator will skip creation if index exists
- Use `--delete` flag to recreate: `python datapipeline/create_search_index.py --delete`

### Pipeline Output

The pipeline provides detailed progress information:

```
🚀 Starting PDF Data Pipeline
============================================================
Data directory: C:\code\project\datapipeline\data
PDFs found: 3
Target index: documents-index
============================================================

============================================================
Processing: document1.pdf
============================================================
📄 Parsing PDF: document1.pdf
   ✅ Parsed 10 pages
✂️  Chunking content from document1.pdf
   ✅ Created 45 chunks
🔢 Generating embeddings for 45 chunks
   ✅ Batch 1/1 complete
   ✅ All embeddings generated
☁️  Uploading 45 documents to Azure AI Search
   ✅ Upload complete: 45 succeeded, 0 failed

============================================================
Pipeline Complete!
============================================================
Total PDFs: 3
✅ Successful: 3
❌ Failed: 0
============================================================
```

