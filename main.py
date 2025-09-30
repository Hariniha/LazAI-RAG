import logging
import sys
import json
import uvicorn
import argparse
import os
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from alith.lazai import Client
from alith.lazai.node.middleware import HeaderValidationMiddleware
from alith.lazai.node.validator import decrypt_file_url
from alith import MilvusStore, chunk_text
from alith.query.types import QueryRequest
from alith.query.settlement import QueryBillingMiddleware

# Get environment variables
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RSA_PRIVATE_KEY_BASE64 = os.getenv("RSA_PRIVATE_KEY_BASE64")


# Set the API key for OpenAI
os.environ["PRIVATE_KEY"] = PRIVATE_KEY
os.environ["RSA_PRIVATE_KEY_BASE64"] = RSA_PRIVATE_KEY_BASE64




# Logging configuration
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
client = Client(private_key=PRIVATE_KEY)
app = FastAPI(title="Alith LazAI Privacy Data Query Node", version="1.0.0")

# Try to initialize MilvusStore with error handling
try:
    store = MilvusStore()
    logger.info("MilvusStore initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize MilvusStore: {e}")
    logger.warning("Running without vector storage - some features may be limited")
    store = None

collection_prefix = "query_"

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Server is running"}

@app.get("/")
async def root():
    return {"message": "Alith LazAI Privacy Data Query Node", "version": "1.0.0"}


@app.post("/query/rag")
async def query_rag(req: QueryRequest):
    try:
        if store is None:
            return Response(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=json.dumps(
                    {
                        "error": {
                            "message": "Vector storage not available - MilvusStore initialization failed",
                            "type": "service_unavailable",
                        }
                    }
                ),
            )
            
        file_id = req.file_id
        if req.file_url:
            file_id = client.get_file_id_by_url(req.file_url)
        if file_id:
            file = client.get_file(file_id)
        else:
            return Response(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=json.dumps(
                    {
                        "error": {
                            "message": "File ID or URL is required",
                            "type": "invalid_request_error",
                        }
                    }
                ),
            )
        owner, file_url, file_hash = file[1], file[2], file[3]
        collection_name = collection_prefix + file_hash
        # Cache data in the vector database
        if not store.has_collection(collection_name):
            encryption_key = client.get_file_permission(
                file_id, client.contract_config.data_registry_address
            )
            data = decrypt_file_url(file_url, encryption_key).decode("utf-8")
            store.create_collection(collection_name=collection_name)
            store.save_docs(chunk_text(data), collection_name=collection_name)
        data = store.search_in(
            req.query, limit=req.limit, collection_name=collection_name
        )
        logger.info(f"Successfully processed request for file: {file}")
        return {
            "data": data,
            "owner": owner,
            "file_id": file_id,
            "file_url": file_url,
            "file_hash": file_hash,
        }
    except Exception as e:
        return Response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=json.dumps(
                {
                    "error": {
                        "message": f"Error processing request for req: {req}. Error: {str(e)}",
                        "type": "internal_error",
                    }
                }
            ),
        )


def run(host: str = "0.0.0.0", port: int = 8000, *, settlement: bool = False):

    # FastAPI app and LazAI client initialization

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settlement:
        app.add_middleware(HeaderValidationMiddleware)
        app.add_middleware(QueryBillingMiddleware)

    return uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    description = "Alith data query server. Host your own embedding models and support language query!"
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--host",
        type=str,
        help="Server host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Server port",
        default=8000,
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model name or path",
        default="/root/models/qwen2.5-1.5b-instruct-q5_k_m.gguf",
    )
    args = parser.parse_args()

    run(host=args.host, port=args.port, settlement=False)
