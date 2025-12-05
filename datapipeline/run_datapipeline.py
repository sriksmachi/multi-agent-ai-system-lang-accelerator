"""
PDF Data Pipeline for Azure AI Search

This pipeline:
1. Parses PDFs from the data/ folder using Azure Document Intelligence
2. Chunks the content intelligently
3. Generates embeddings using Azure OpenAI
4. Uploads to Azure AI Search with merge-or-upload strategy
"""

import os
import sys
import json
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.search.documents import SearchClient
from azure.search.documents.models import IndexDocumentsAction
from openai import AzureOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter

load_dotenv()


class PDFDataPipeline:
    """
    End-to-end pipeline for processing PDFs and uploading to Azure AI Search.
    """
    
    def __init__(self):
        """Initialize the pipeline with Azure clients."""
        # Azure Document Intelligence
        self.di_endpoint = os.getenv("AZURE_DI_ENDPOINT")
        self.di_key = os.getenv("AZURE_DI_KEY")
        
        # Azure OpenAI
        self.openai_endpoint = os.getenv("AZURE_OPENAI_EMBEDDINGS_ENDPOINT")
        self.openai_key = os.getenv("AZURE_OPENAI_EMBEDDINGS_API_KEY")
        self.openai_api_version = os.getenv("AZURE_OPENAI_EMBEDDINGS_API_VERSION", "2023-05-15")
        self.embeddings_deployment = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "text-embedding-3-small")
        
        # Azure AI Search
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.getenv("AZURE_SEARCH_ADMIN_KEY")
        self.search_index = os.getenv("AZURE_SEARCH_INDEX_NAME", "documents-index")
        
        # Pipeline configuration
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "200"))
        self.embedding_batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE", "50"))
        self.embedding_batch_delay = float(os.getenv("EMBEDDING_BATCH_DELAY", "2.0"))
        
        # Validate configuration
        self._validate_config()
        
        # Initialize clients
        self.di_client = DocumentIntelligenceClient(
            endpoint=self.di_endpoint,
            credential=AzureKeyCredential(self.di_key)
        )
        
        self.openai_client = AzureOpenAI(
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
            api_version=self.openai_api_version
        )
        
        self.search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=self.search_index,
            credential=AzureKeyCredential(self.search_key)
        )
        
        # Text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    
    def _validate_config(self):
        """Validate required environment variables."""
        required_vars = [
            "AZURE_DI_ENDPOINT",
            "AZURE_DI_KEY",
            "AZURE_OPENAI_EMBEDDINGS_ENDPOINT",
            "AZURE_OPENAI_EMBEDDINGS_API_KEY",
            "AZURE_SEARCH_ENDPOINT",
            "AZURE_SEARCH_ADMIN_KEY",
        ]
        
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            print(f"❌ Missing required environment variables: {', '.join(missing)}")
            sys.exit(1)
    
    def parse_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        Parse PDF using Azure Document Intelligence.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with parsed content, pages, and metadata
        """
        print(f"📄 Parsing PDF: {pdf_path.name}")
        
        try:
            with open(pdf_path, "rb") as f:
                pdf_content = f.read()
            
            # Analyze document
            poller = self.di_client.begin_analyze_document(
                "prebuilt-layout",
                pdf_content
            )
            result = poller.result()
            
            # Extract content by page
            pages_content = []
            for page in result.pages:
                page_text = ""
                if hasattr(page, 'lines') and page.lines:
                    page_text = "\n".join([line.content for line in page.lines])
                
                pages_content.append({
                    "page_number": page.page_number,
                    "content": page_text,
                })
            
            # Extract full content
            full_content = result.content if hasattr(result, 'content') else ""
            
            print(f"   ✅ Parsed {len(pages_content)} pages")
            
            return {
                "content": full_content,
                "pages": pages_content,
                "page_count": len(pages_content),
                "source": pdf_path.name,
            }
            
        except Exception as e:
            print(f"   ❌ Error parsing PDF: {e}")
            return None
    
    def chunk_content(self, parsed_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Chunk document content intelligently.
        
        Args:
            parsed_doc: Parsed document from parse_pdf
            
        Returns:
            List of chunks with metadata
        """
        print(f"✂️  Chunking content from {parsed_doc['source']}")
        
        chunks = []
        
        # Process each page
        for page_info in parsed_doc["pages"]:
            page_number = page_info["page_number"]
            page_content = page_info["content"]
            
            if not page_content.strip():
                continue
            
            # Split page into chunks
            page_chunks = self.text_splitter.split_text(page_content)
            
            for idx, chunk_text in enumerate(page_chunks):
                # Generate unique ID
                chunk_id = hashlib.md5(
                    f"{parsed_doc['source']}-{page_number}-{idx}".encode()
                ).hexdigest()
                
                chunks.append({
                    "id": chunk_id,
                    "content": chunk_text,
                    "title": parsed_doc["source"].replace(".pdf", ""),
                    "source": parsed_doc["source"],
                    "page_number": page_number,
                    "chunk_id": idx,
                    "metadata": json.dumps({
                        "total_pages": parsed_doc["page_count"],
                        "chunk_size": len(chunk_text),
                        "processed_at": datetime.utcnow().isoformat(),
                    }),
                })
        
        print(f"   ✅ Created {len(chunks)} chunks")
        return chunks
    
    def generate_embeddings(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate embeddings for chunks using Azure OpenAI.
        
        Args:
            chunks: List of chunks
            
        Returns:
            Chunks with embeddings added
        """
        print(f"🔢 Generating embeddings for {len(chunks)} chunks")
        
        # Process in batches to handle rate limits
        for i in range(0, len(chunks), self.embedding_batch_size):
            batch = chunks[i:i + self.embedding_batch_size]
            batch_texts = [chunk["content"] for chunk in batch]
            
            try:
                # Generate embeddings
                response = self.openai_client.embeddings.create(
                    input=batch_texts,
                    model=self.embeddings_deployment
                )
                
                # Add embeddings to chunks
                for j, embedding_obj in enumerate(response.data):
                    chunks[i + j]["content_vector"] = embedding_obj.embedding
                
                print(f"   ✅ Batch {i // self.embedding_batch_size + 1}/{(len(chunks) - 1) // self.embedding_batch_size + 1} complete")
                
                # Rate limiting delay
                if i + self.embedding_batch_size < len(chunks):
                    time.sleep(self.embedding_batch_delay)
                
            except Exception as e:
                print(f"   ❌ Error generating embeddings for batch: {e}")
                # Continue with next batch
                continue
        
        print(f"   ✅ All embeddings generated")
        return chunks
    
    def upload_to_search(self, chunks: List[Dict[str, Any]]) -> bool:
        """
        Upload chunks to Azure AI Search using merge-or-upload strategy.
        
        Args:
            chunks: List of chunks with embeddings
            
        Returns:
            bool: True if successful
        """
        print(f"☁️  Uploading {len(chunks)} documents to Azure AI Search")
        
        try:
            # Use merge-or-upload action
            # This will update existing documents or create new ones
            result = self.search_client.merge_or_upload_documents(documents=chunks)
            
            successful = sum(1 for r in result if r.succeeded)
            failed = len(result) - successful
            
            print(f"   ✅ Upload complete: {successful} succeeded, {failed} failed")
            
            if failed > 0:
                for r in result:
                    if not r.succeeded:
                        print(f"      ❌ Failed: {r.key} - {r.error_message}")
            
            return failed == 0
            
        except Exception as e:
            print(f"   ❌ Error uploading to search: {e}")
            return False
    
    def process_pdf(self, pdf_path: Path) -> bool:
        """
        Process a single PDF through the entire pipeline.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            bool: True if successful
        """
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_path.name}")
        print(f"{'='*60}")
        
        # Parse PDF
        parsed_doc = self.parse_pdf(pdf_path)
        if not parsed_doc:
            return False
        
        # Chunk content
        chunks = self.chunk_content(parsed_doc)
        if not chunks:
            print("   ⚠️  No chunks created")
            return False
        
        # Generate embeddings
        chunks_with_embeddings = self.generate_embeddings(chunks)
        
        # Filter out chunks without embeddings
        valid_chunks = [c for c in chunks_with_embeddings if "content_vector" in c]
        if len(valid_chunks) < len(chunks):
            print(f"   ⚠️  {len(chunks) - len(valid_chunks)} chunks missing embeddings")
        
        if not valid_chunks:
            print("   ❌ No valid chunks to upload")
            return False
        
        # Upload to search
        success = self.upload_to_search(valid_chunks)
        
        return success
    
    def run(self, data_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Run the pipeline on all PDFs in the data directory.
        
        Args:
            data_dir: Directory containing PDFs (default: ./datapipeline/data)
            
        Returns:
            Dict with processing statistics
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / "data"
        
        data_dir = Path(data_dir)
        
        if not data_dir.exists():
            print(f"❌ Data directory not found: {data_dir}")
            return {"error": "Directory not found"}
        
        # Find all PDFs
        pdf_files = list(data_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"⚠️  No PDF files found in: {data_dir}")
            return {"error": "No PDFs found"}
        
        print(f"\n🚀 Starting PDF Data Pipeline")
        print(f"{'='*60}")
        print(f"Data directory: {data_dir}")
        print(f"PDFs found: {len(pdf_files)}")
        print(f"Target index: {self.search_index}")
        print(f"{'='*60}\n")
        
        # Process each PDF
        results = {
            "total": len(pdf_files),
            "successful": 0,
            "failed": 0,
            "files": []
        }
        
        for pdf_path in pdf_files:
            try:
                success = self.process_pdf(pdf_path)
                
                if success:
                    results["successful"] += 1
                    results["files"].append({"name": pdf_path.name, "status": "success"})
                else:
                    results["failed"] += 1
                    results["files"].append({"name": pdf_path.name, "status": "failed"})
                    
            except Exception as e:
                print(f"❌ Unexpected error processing {pdf_path.name}: {e}")
                results["failed"] += 1
                results["files"].append({"name": pdf_path.name, "status": "error", "error": str(e)})
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Pipeline Complete!")
        print(f"{'='*60}")
        print(f"Total PDFs: {results['total']}")
        print(f"✅ Successful: {results['successful']}")
        print(f"❌ Failed: {results['failed']}")
        print(f"{'='*60}\n")
        
        return results


def main():
    """Main entry point."""
    # Parse command line arguments
    data_dir = None
    if len(sys.argv) > 1:
        data_dir = Path(sys.argv[1])
    
    # Create and run pipeline
    pipeline = PDFDataPipeline()
    results = pipeline.run(data_dir)
    
    # Exit with error code if any failed
    if results.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
