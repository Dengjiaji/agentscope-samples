#!/usr/bin/env python3
"""
导出脚本：SQLite -> JSONL
从 ChromaDB SQLite 导出所有数据到 .jsonl 文件
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


def export_sqlite_to_jsonl(config_name: str = "mock", output_dir: str = None):
    """从 SQLite 导出到 JSONL"""
    
    # 源目录（SQLite 位置）
    sqlite_dir = get_logs_and_memory_dir() / config_name / "memory_data" / "reme_vector_store"
    sqlite_file = sqlite_dir / "chroma.sqlite3"
    
    if not sqlite_file.exists():
        print(f"❌ SQLite database not found: {sqlite_file}")
        return
    
    print(f"🗄️  SQLite database: {sqlite_file}")
    print(f"📂 Size: {sqlite_file.stat().st_size:,} bytes\n")
    
    # 输出目录
    if output_dir is None:
        output_dir = sqlite_dir / "exported_jsonl"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Output directory: {output_dir}\n")
    
    # 创建 embedding model
    embedding_model = OpenAICompatibleEmbeddingModel(
        dimensions=int(os.getenv("REME_EMBEDDING_DIMENSIONS", "64")),
        model_name=os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4")
    )
    
    # 创建 vector store
    vector_store = ChromaVectorStore(
        embedding_model=embedding_model,
        store_dir=str(sqlite_dir),
        batch_size=1024
    )
    
    # 替换为 PersistentClient 读取 SQLite
    vector_store.collections.clear()
    vector_store._client = chromadb.PersistentClient(
        path=str(sqlite_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    
    # 列出所有 collections (workspaces)
    all_collections = vector_store._client.list_collections()
    
    if not all_collections:
        print("❌ No workspaces found in SQLite database")
        return
    
    print(f"📊 Found {len(all_collections)} workspaces\n")
    
    # 逐个导出
    total_nodes = 0
    for collection in all_collections:
        workspace_id = collection.name
        node_count = collection.count()
        
        print(f"📤 Exporting: workspace '{workspace_id}' ({node_count} nodes)")
        
        try:
            # 导出到 JSONL
            output_file = output_dir / f"{workspace_id}.jsonl"
            vector_store.dump_workspace(workspace_id, path=str(output_dir))
            
            if output_file.exists():
                file_size = output_file.stat().st_size
                print(f"   ✅ Saved to: {output_file.name} ({file_size:,} bytes)\n")
                total_nodes += node_count
            else:
                print(f"   ⚠️  File not created\n")
                
        except Exception as e:
            print(f"   ❌ Error: {e}\n")
    
    # 显示最终统计
    print(f"=" * 60)
    print(f"✅ Export complete!")
    print(f"📊 Total: {len(all_collections)} workspaces, {total_nodes} nodes")
    print(f"📁 Exported to: {output_dir}")
    print(f"=" * 60)


if __name__ == "__main__":
    # 可以通过命令行参数指定 config_name 和输出目录
    config_name = sys.argv[1] if len(sys.argv) > 1 else "mock"
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"🚀 Starting SQLite -> JSONL export")
    print(f"📦 Config: {config_name}\n")
    
    export_sqlite_to_jsonl(config_name, output_dir)

