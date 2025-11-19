#!/usr/bin/env python3
"""
一次性迁移脚本：JSONL -> SQLite
将 reme_vector_store 目录下的 .jsonl 文件导入到 ChromaDB SQLite
"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv
load_dotenv()

import chromadb
from chromadb.config import Settings
from flowllm.storage.vector_store import ChromaVectorStore
from flowllm.embedding_model import OpenAICompatibleEmbeddingModel
from backend.config.path_config import get_logs_and_memory_dir

def migrate_jsonl_to_sqlite(config_name: str = "mock"):
    """从 JSONL 迁移到 SQLite"""
    
    # 源目录（JSONL 文件位置）
    source_dir = get_logs_and_memory_dir() / config_name / "memory_data" / "reme_vector_store"
    
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        return
    
    print(f"📂 Source directory: {source_dir}")
    
    # 查找所有 .jsonl 文件
    jsonl_files = list(source_dir.glob("*.jsonl"))
    
    if not jsonl_files:
        print("❌ No .jsonl files found")
        return
    
    print(f"📄 Found {len(jsonl_files)} .jsonl files\n")
    
    # 创建 embedding model
    embedding_model = OpenAICompatibleEmbeddingModel(
        dimensions=int(os.getenv("REME_EMBEDDING_DIMENSIONS", "64")),
        model_name=os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4")
    )
    
    # 创建 vector store
    vector_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir=str(source_dir),
        batch_size=1024
    )
    
    # 替换为 PersistentClient
    vector_store.collections.clear()
    vector_store._client = chromadb.PersistentClient(
        path=str(source_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    
    print(f"🗄️  Using SQLite database: {source_dir}/chroma.sqlite3\n")
    
    # 逐个导入
    for jsonl_file in jsonl_files:
        workspace_id = jsonl_file.stem  # 文件名作为 workspace_id
        
        print(f"📥 Importing: {jsonl_file.name} -> workspace '{workspace_id}'")
        
        try:
            # 加载 JSONL 到 vector store
            vector_store.load_workspace(workspace_id, path=str(source_dir))
            
            # 检查导入的节点数量
            if vector_store.exist_workspace(workspace_id):
                nodes = list(vector_store.iter_workspace_nodes(workspace_id))
                print(f"   ✅ Imported {len(nodes)} nodes\n")
            else:
                print(f"   ⚠️  Workspace not found after import\n")
                
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    # 显示最终统计
    all_collections = vector_store._client.list_collections()
    print(f"=" * 60)
    print(f"✅ Migration complete!")
    print(f"📊 Total workspaces in SQLite: {len(all_collections)}")
    
    for collection in all_collections:
        count = collection.count()
        print(f"   - {collection.name}: {count} nodes")
    
    print(f"\n💾 SQLite database: {source_dir}/chroma.sqlite3")
    print(f"=" * 60)


if __name__ == "__main__":
    # 可以通过命令行参数指定 config_name
    config_name = sys.argv[1] if len(sys.argv) > 1 else "mock"
    
    print(f"🚀 Starting JSONL -> SQLite migration")
    print(f"📦 Config: {config_name}\n")
    
    migrate_jsonl_to_sqlite(config_name)

