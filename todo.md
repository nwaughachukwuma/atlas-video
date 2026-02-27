## TODO

- [x] Implement a simple server with necessary endpoint to be run in the docker container pulled using docker pull nwaughachukwuma/atlas-video, so anyone can start the server as shown in the kreuzberg example below. Let's use FastAPI or a simple python server for this.
- [x] Let's expose all the CLI options as endpoints on the server in the docker container.
- [ ] Allow support for provider and model configuration - QWEN and GEMINI

---

<details>
<summary>Kreuzberg docker server example</summary>

# Run server on port 8000

docker run -d \n -p 8000:8000 \n ghcr.io/kreuzberg-dev/kreuzberg:latest \n serve -H 0.0.0.0 -p 8000

# With environment variables

docker run -d \n -e KREUZBERG_CORS_ORIGINS="https://myapp.com" \n -e KREUZBERG_MAX_UPLOAD_SIZE_MB=200 \n -p 8000:8000 \n ghcr.io/kreuzberg-dev/kreuzberg:latest \n serve -H 0.0.0.0 -p 8000

API Endpoints¶

POST /extract¶

Extract text from uploaded files via multipart form data.

Request Format:

Method: POST
Content-Type: multipart/form-data
Fields:
files (required, repeatable): Files to extract
config (optional): JSON configuration overrides
output_format (optional): Output format for extracted text - plain, markdown, djot, or html (default: plain)
Response: JSON array of extraction results

Example:

Terminal

# Extract a single file via HTTP POST

curl -F "files=@document.pdf" http://localhost:8000/extract

# Extract multiple files in a single request

curl -F "files=@doc1.pdf" -F "files=@doc2.docx" \
 http://localhost:8000/extract

# Extract with custom OCR configuration override

curl -F "files=@scanned.pdf" \
 -F 'config={"ocr":{"language":"eng"},"force_ocr":true}' \
 http://localhost:8000/extract

# Extract with markdown output format

curl -F "files=@document.pdf" \
 -F "output_format=markdown" \
 http://localhost:8000/extract
Response Schema:

Response

[
{
"content": "Extracted text content...",
"mime_type": "application/pdf",
"metadata": {
"page_count": 10,
"author": "John Doe"
},
"tables": [],
"detected_languages": ["eng"],
"chunks": null,
"images": null
}
]
POST /embed¶

Generate embeddings for text strings without document extraction.

Request Format:

Method: POST
Content-Type: application/json
Body:
texts (required): Array of strings to generate embeddings for
config (optional): Embedding configuration overrides
Response: JSON object containing embeddings, model info, dimensions, and count

Example:

Terminal

# Generate embeddings for two text strings

curl -X POST http://localhost:8000/embed \
 -H "Content-Type: application/json" \
 -d '{"texts":["Hello world","Second text"]}'

# Generate embeddings with custom model configuration

curl -X POST http://localhost:8000/embed \
 -H "Content-Type: application/json" \
 -d '{
"texts":["Test text"],
"config":{
"model":{"type":"preset","name":"fast"},
"batch_size":32
}
}'
Response Schema:

Response

{
"embeddings": [
[0.123, -0.456, 0.789, ...], // 384 or 768 or 1024 dimensions
[-0.234, 0.567, -0.891, ...]
],
"model": "balanced",
"dimensions": 768,
"count": 2
}
Available Embedding Presets:

Preset Model Dimensions Use Case
fast AllMiniLML6V2Q 384 Quick prototyping, development
balanced BGEBaseENV15 768 General-purpose RAG, production (default)
quality BGELargeENV15 1024 Complex documents, maximum accuracy
multilingual MultilingualE5Base 768 International documents, 100+ languages
Use Cases:

Generate embeddings for semantic search
Create vector representations for RAG (Retrieval-Augmented Generation) pipelines
Embed text chunks without extracting from documents
Batch embed multiple texts efficiently
Note: This endpoint requires the embeddings feature to be enabled (available in Docker images and most pre-built binaries). ONNX Runtime must be installed on the system.

POST /chunk¶

Chunk text into smaller pieces with configurable overlap for RAG (Retrieval-Augmented Generation) pipelines.

Request Format:

Method: POST
Content-Type: application/json
Body:
text (required): The text string to chunk
chunker_type (optional): Type of chunker to use - "text" (default) or "markdown"
config (optional): Chunking configuration object
Configuration Options:

Field Type Default Description
max_characters integer 2000 Maximum characters per chunk
overlap integer 100 Number of overlapping characters between chunks
trim boolean true Whether to trim whitespace from chunks
Example:

Terminal

# Basic text chunking with defaults

curl -X POST http://localhost:8000/chunk \
 -H "Content-Type: application/json" \
 -d '{"text":"Your long text content here..."}'

# Chunk with custom configuration

curl -X POST http://localhost:8000/chunk \
 -H "Content-Type: application/json" \
 -d '{
"text":"Your long text content here...",
"chunker_type":"text",
"config":{
"max_characters":1000,
"overlap":50,
"trim":true
}
}'

# Markdown-aware chunking (preserves structure)

curl -X POST http://localhost:8000/chunk \
 -H "Content-Type: application/json" \
 -d '{
"text":"# Heading\n\nParagraph content...\n\n## Subheading\n\nMore content...",
"chunker_type":"markdown"
}'
Response Schema:

Response

{
"chunks": [
{
"content": "First chunk of text...",
"byte_start": 0,
"byte_end": 1000,
"chunk_index": 0,
"total_chunks": 3,
"first_page": null,
"last_page": null
},
{
"content": "Second chunk with overlap...",
"byte_start": 900,
"byte_end": 1900,
"chunk_index": 1,
"total_chunks": 3,
"first_page": null,
"last_page": null
}
],
"chunk_count": 3,
"config": {
"max_characters": 1000,
"overlap": 100,
"trim": true,
"chunker_type": "text"
},
"input_size_bytes": 2500,
"chunker_type": "text"
}
Response Fields:

Field Type Description
chunks array Array of chunk objects
chunks[].content string The text content of this chunk
chunks[].byte_start integer Starting byte offset in original text
chunks[].byte_end integer Ending byte offset in original text
chunks[].chunk_index integer Zero-based index of this chunk
chunks[].total_chunks integer Total number of chunks produced
chunks[].first_page integer/null First page number (for PDF sources)
chunks[].last_page integer/null Last page number (for PDF sources)
chunk_count integer Total number of chunks
config object Configuration used for chunking
input_size_bytes integer Size of input text in bytes
chunker_type string Type of chunker used
Use Cases:

Prepare text for vector database insertion
Split documents for embedding generation
Create overlapping chunks for semantic search
Preprocess content for RAG pipelines
Batch process text without full document extraction
Error Responses:

Status Error Type Description
400 ValidationError Empty text or invalid chunker_type
500 Internal errors Server processing errors
Client Examples:

C#
cURL
Go
Java
Python
Ruby
Rust
TypeScript
Python

import httpx

# Basic chunking with defaults

with httpx.Client() as client:
response = client.post(
"http://localhost:8000/chunk",
json={"text": "Your long text content here..."}
)
result = response.json()
for chunk in result["chunks"]:
print(f"Chunk {chunk['chunk_index']}: {chunk['content'][:50]}...")

# Chunking with custom configuration

with httpx.Client() as client:
response = client.post(
"http://localhost:8000/chunk",
json={
"text": "Your long text content here...",
"chunker_type": "text",
"config": {
"max_characters": 1000,
"overlap": 50,
"trim": True
}
}
)
result = response.json()
print(f"Created {result['chunk_count']} chunks")

GET /health¶

Health check endpoint for monitoring and load balancers.

Example:

Terminal

# Check server health status

curl http://localhost:8000/health
Response:

Response

{
"status": "healthy",
"version": "4.3.8"
}
Extended Response (with plugins):

The response may optionally include a plugins object containing information about loaded plugins and backends:

Response with Plugins

{
"status": "healthy",
"version": "4.3.8",
"plugins": {
"ocr_backends_count": 2,
"ocr_backends": ["tesseract"],
"extractors_count": 15,
"post_processors_count": 3
}
}
Plugin Object Fields:

ocr_backends_count: Number of available OCR backends
ocr_backends: List of loaded OCR backend names
extractors_count: Number of available document extractors
post_processors_count: Number of active post-processors
GET /info¶

Server information and capabilities.

Example:

Terminal

# Get server version and capabilities

curl http://localhost:8000/info
Response:

Response

{
"version": "4.3.8",
"rust_backend": true
}
GET /openapi.json¶

Returns the OpenAPI 3.0 schema for the API server.

Example:

Terminal

curl http://localhost:8000/openapi.json
The response is a complete OpenAPI 3.0 specification document describing all available endpoints, request/response formats, and schemas.

GET /cache/stats¶

Get cache statistics.

Example:

Terminal

# Retrieve cache statistics and storage usage

curl http://localhost:8000/cache/stats
Response:

Response

{
"directory": ".kreuzberg",
"total_files": 42,
"total_size_mb": 156.8,
"available_space_mb": 45123.5,
"oldest_file_age_days": 7.2,
"newest_file_age_days": 0.1
}
DELETE /cache/clear¶

Clear all cached files.

Example:

Terminal

# Clear all cached extraction results

curl -X DELETE http://localhost:8000/cache/clear
Response:

Response

{
"directory": ".kreuzberg",
"removed_files": 42,
"freed_mb": 156.8
}

</details>
