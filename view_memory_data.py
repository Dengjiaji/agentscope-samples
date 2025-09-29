#!/usr/bin/env python3
"""
Memory数据查看器 - 专门查看IA项目的memory_data目录
"""

import os
import sys
import sqlite3
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir) if current_dir.endswith('memory_data') else current_dir
sys.path.append(project_dir)

class MemoryDataViewer:
    """Memory数据查看器"""
    
    def __init__(self, memory_data_dir: str = None):
        """初始化查看器"""
        if memory_data_dir is None:
            memory_data_dir = "/Users/wy/Downloads/Project/IA/memory_data/"
        
        self.memory_data_dir = memory_data_dir
        self.sqlite_db = os.path.join(memory_data_dir, "ia_memory_history.db")
        self.chroma_db = os.path.join(memory_data_dir, "ia_chroma_db")
        
        print(f"🔍 Memory数据查看器")
        print(f"📁 数据目录: {memory_data_dir}")
        print(f"📊 SQLite数据库: {self.sqlite_db}")
        print(f"🗂️  Chroma数据库: {self.chroma_db}")
        print("="*60)
    
    def check_files(self):
        """检查文件状态"""
        print("\n📋 文件状态检查:")
        print("-"*40)
        
        # 检查目录
        if os.path.exists(self.memory_data_dir):
            print(f"✅ 数据目录存在: {self.memory_data_dir}")
            
            # 列出所有文件
            for item in os.listdir(self.memory_data_dir):
                item_path = os.path.join(self.memory_data_dir, item)
                if os.path.isfile(item_path):
                    size = os.path.getsize(item_path)
                    print(f"   📄 {item} ({size} bytes)")
                elif os.path.isdir(item_path):
                    try:
                        sub_items = len(os.listdir(item_path))
                        print(f"   📁 {item}/ ({sub_items} items)")
                    except:
                        print(f"   📁 {item}/ (无法访问)")
        else:
            print(f"❌ 数据目录不存在: {self.memory_data_dir}")
            return False
        
        # 检查SQLite数据库
        if os.path.exists(self.sqlite_db):
            size = os.path.getsize(self.sqlite_db)
            print(f"✅ SQLite数据库存在: {size} bytes")
        else:
            print(f"❌ SQLite数据库不存在")
        
        # 检查Chroma数据库
        if os.path.exists(self.chroma_db):
            print(f"✅ Chroma数据库目录存在")
            try:
                chroma_items = os.listdir(self.chroma_db)
                for item in chroma_items:
                    item_path = os.path.join(self.chroma_db, item)
                    if os.path.isfile(item_path):
                        size = os.path.getsize(item_path)
                        print(f"   📄 {item} ({size} bytes)")
                    elif os.path.isdir(item_path):
                        sub_items = len(os.listdir(item_path))
                        print(f"   📁 {item}/ ({sub_items} files)")
            except Exception as e:
                print(f"   ❌ 无法访问Chroma目录: {str(e)}")
        else:
            print(f"❌ Chroma数据库目录不存在")
        
        return True
    
    def view_sqlite_data(self):
        """查看SQLite数据"""
        print("\n📊 SQLite数据库内容:")
        print("-"*40)
        
        if not os.path.exists(self.sqlite_db):
            print("❌ SQLite数据库文件不存在")
            return
        
        try:
            with sqlite3.connect(self.sqlite_db) as conn:
                cursor = conn.cursor()
                
                # 获取所有表
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                
                if not tables:
                    print("❌ 数据库中没有表")
                    return
                
                print(f"📋 找到 {len(tables)} 个表:")
                
                for table_name, in tables:
                    print(f"\n--- 表: {table_name} ---")
                    
                    # 获取表结构
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    if columns:
                        print("列结构:")
                        for col in columns:
                            col_id, name, col_type, not_null, default, pk = col
                            pk_str = " (主键)" if pk else ""
                            print(f"  - {name}: {col_type}{pk_str}")
                    
                    # 获取记录数
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cursor.fetchone()[0]
                    print(f"记录数: {count}")
                    
                    if count > 0:
                        # 显示前几条记录
                        print("前5条记录:")
                        try:
                            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                            rows = cursor.fetchall()
                            
                            if rows:
                                # 获取列名
                                col_names = [desc[1] for desc in columns]
                                
                                # 创建DataFrame显示
                                df = pd.DataFrame(rows, columns=col_names)
                                pd.set_option('display.max_columns', None)
                                pd.set_option('display.width', None)
                                pd.set_option('display.max_colwidth', 50)
                                
                                print(df.to_string(index=False))
                            else:
                                print("  (无数据)")
                                
                        except Exception as e:
                            print(f"  ❌ 查询数据失败: {str(e)}")
                    
                    print()
        
        except Exception as e:
            print(f"❌ 访问SQLite数据库失败: {str(e)}")
    
    def view_chroma_data(self):
        """查看Chroma数据"""
        print("\n🗂️ Chroma向量数据库内容:")
        print("-"*40)
        
        if not os.path.exists(self.chroma_db):
            print("❌ Chroma数据库目录不存在")
            return
        
        try:
            import chromadb
            
            # 连接到Chroma数据库
            client = chromadb.PersistentClient(path=self.chroma_db)
            
            # 获取所有集合
            collections = client.list_collections()
            
            if not collections:
                print("❌ Chroma数据库中没有集合")
                return
            
            print(f"📋 找到 {len(collections)} 个集合:")
            
            for i, collection in enumerate(collections, 1):
                print(f"\n--- 集合 {i}: {collection.name} ---")
                
                try:
                    # 获取集合统计信息
                    count = collection.count()
                    print(f"记录数: {count}")
                    
                    if count > 0:
                        # 获取前几条记录
                        results = collection.get(limit=3)
                        
                        print("前3条记录:")
                        
                        if results['documents']:
                            for j, doc in enumerate(results['documents'], 1):
                                print(f"  记录 {j}:")
                                
                                # 显示文档内容（截断长内容）
                                content = doc[:200] + "..." if len(doc) > 200 else doc
                                print(f"    内容: {content}")
                                
                                # 显示元数据
                                if results['metadatas'] and j-1 < len(results['metadatas']):
                                    metadata = results['metadatas'][j-1]
                                    if metadata:
                                        print(f"    元数据: {json.dumps(metadata, ensure_ascii=False)}")
                                
                                # 显示ID
                                if results['ids'] and j-1 < len(results['ids']):
                                    print(f"    ID: {results['ids'][j-1]}")
                                
                                print()
                        else:
                            print("  (无文档数据)")
                    
                except Exception as e:
                    print(f"  ❌ 访问集合失败: {str(e)}")
        
        except ImportError:
            print("❌ 需要安装chromadb: pip install chromadb")
        except Exception as e:
            print(f"❌ 访问Chroma数据库失败: {str(e)}")
    
    def search_data(self, search_term: str):
        """搜索数据"""
        print(f"\n🔍 搜索包含 '{search_term}' 的数据:")
        print("-"*40)
        
        # 搜索SQLite数据
        print("SQLite搜索结果:")
        if os.path.exists(self.sqlite_db):
            try:
                with sqlite3.connect(self.sqlite_db) as conn:
                    cursor = conn.cursor()
                    
                    # 获取所有表
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    
                    found_any = False
                    for table_name, in tables:
                        try:
                            # 获取表的列信息
                            cursor.execute(f"PRAGMA table_info({table_name});")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            # 搜索所有文本列
                            text_columns = []
                            for col in columns:
                                if any(keyword in col.lower() for keyword in ['content', 'message', 'text', 'data', 'memory']):
                                    text_columns.append(col)
                            
                            if text_columns:
                                where_clauses = [f"{col} LIKE ?" for col in text_columns]
                                where_clause = " OR ".join(where_clauses)
                                
                                query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT 5;"
                                params = [f"%{search_term}%" for _ in text_columns]
                                
                                cursor.execute(query, params)
                                rows = cursor.fetchall()
                                
                                if rows:
                                    print(f"  在表 '{table_name}' 中找到 {len(rows)} 条记录")
                                    found_any = True
                                    
                                    # 获取列名
                                    cursor.execute(f"PRAGMA table_info({table_name});")
                                    col_info = cursor.fetchall()
                                    col_names = [col[1] for col in col_info]
                                    
                                    for i, row in enumerate(rows, 1):
                                        print(f"    记录 {i}:")
                                        for j, value in enumerate(row):
                                            if j < len(col_names):
                                                val_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                                                print(f"      {col_names[j]}: {val_str}")
                                        print()
                        
                        except Exception as e:
                            print(f"  搜索表 '{table_name}' 时出错: {str(e)}")
                    
                    if not found_any:
                        print("  未找到相关记录")
            
            except Exception as e:
                print(f"  SQLite搜索失败: {str(e)}")
        else:
            print("  SQLite数据库不存在")
        
        # 搜索Chroma数据
        print("\nChroma搜索结果:")
        if os.path.exists(self.chroma_db):
            try:
                import chromadb
                
                client = chromadb.PersistentClient(path=self.chroma_db)
                collections = client.list_collections()
                
                found_any = False
                for collection in collections:
                    try:
                        results = collection.query(
                            query_texts=[search_term],
                            n_results=3
                        )
                        
                        if results['documents'] and results['documents'][0]:
                            print(f"  在集合 '{collection.name}' 中找到 {len(results['documents'][0])} 条相关记录")
                            found_any = True
                            
                            for i, doc in enumerate(results['documents'][0], 1):
                                distance = results['distances'][0][i-1] if results['distances'] else "N/A"
                                content = doc[:200] + "..." if len(doc) > 200 else doc
                                print(f"    记录 {i} (相似度: {distance}): {content}")
                    
                    except Exception as e:
                        print(f"  搜索集合 '{collection.name}' 时出错: {str(e)}")
                
                if not found_any:
                    print("  未找到相关记录")
            
            except ImportError:
                print("  需要安装chromadb")
            except Exception as e:
                print(f"  Chroma搜索失败: {str(e)}")
        else:
            print("  Chroma数据库不存在")
    
    def export_all_data(self, output_dir: str = None):
        """导出所有数据"""
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"memory_export_{timestamp}"
        
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\n💾 导出所有数据到目录: {output_dir}")
        print("-"*40)
        
        # 导出SQLite数据
        if os.path.exists(self.sqlite_db):
            try:
                with sqlite3.connect(self.sqlite_db) as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    
                    for table_name, in tables:
                        output_file = os.path.join(output_dir, f"sqlite_{table_name}.json")
                        
                        cursor.execute(f"SELECT * FROM {table_name};")
                        rows = cursor.fetchall()
                        
                        if rows:
                            # 获取列名
                            cursor.execute(f"PRAGMA table_info({table_name});")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            # 转换为字典列表
                            data = []
                            for row in rows:
                                record = {}
                                for i, value in enumerate(row):
                                    if i < len(columns):
                                        record[columns[i]] = value
                                data.append(record)
                            
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                            
                            print(f"✅ 导出SQLite表 '{table_name}': {len(data)} 条记录 -> {output_file}")
                        else:
                            print(f"⚪ SQLite表 '{table_name}' 无数据")
            
            except Exception as e:
                print(f"❌ 导出SQLite数据失败: {str(e)}")
        
        # 导出Chroma数据
        if os.path.exists(self.chroma_db):
            try:
                import chromadb
                
                client = chromadb.PersistentClient(path=self.chroma_db)
                collections = client.list_collections()
                
                for collection in collections:
                    output_file = os.path.join(output_dir, f"chroma_{collection.name}.json")
                    
                    try:
                        results = collection.get()
                        
                        if results['documents']:
                            data = []
                            for i in range(len(results['documents'])):
                                record = {
                                    'id': results['ids'][i] if results['ids'] else None,
                                    'document': results['documents'][i],
                                    'metadata': results['metadatas'][i] if results['metadatas'] else None
                                }
                                data.append(record)
                            
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                            
                            print(f"✅ 导出Chroma集合 '{collection.name}': {len(data)} 条记录 -> {output_file}")
                        else:
                            print(f"⚪ Chroma集合 '{collection.name}' 无数据")
                    
                    except Exception as e:
                        print(f"❌ 导出Chroma集合 '{collection.name}' 失败: {str(e)}")
            
            except ImportError:
                print("❌ 需要安装chromadb才能导出Chroma数据")
            except Exception as e:
                print(f"❌ 导出Chroma数据失败: {str(e)}")
        
        print(f"\n✅ 数据导出完成，保存在目录: {output_dir}")
    
    def interactive_mode(self):
        """交互模式"""
        print("\n🔍 进入交互模式")
        print("="*50)
        print("可用命令:")
        print("  check      - 检查文件状态")
        print("  sqlite     - 查看SQLite数据")
        print("  chroma     - 查看Chroma数据")
        print("  search <term> - 搜索数据")
        print("  export     - 导出所有数据")
        print("  all        - 查看所有数据")
        print("  quit       - 退出")
        print("="*50)
        
        while True:
            try:
                cmd = input("\n🔍 memory> ").strip().split()
                if not cmd:
                    continue
                
                if cmd[0] in ['quit', 'q', 'exit']:
                    print("👋 退出查看器")
                    break
                
                elif cmd[0] == 'check':
                    self.check_files()
                
                elif cmd[0] == 'sqlite':
                    self.view_sqlite_data()
                
                elif cmd[0] == 'chroma':
                    self.view_chroma_data()
                
                elif cmd[0] == 'search':
                    if len(cmd) > 1:
                        search_term = ' '.join(cmd[1:])
                        self.search_data(search_term)
                    else:
                        print("❌ 请提供搜索词: search <term>")
                
                elif cmd[0] == 'export':
                    self.export_all_data()
                
                elif cmd[0] == 'all':
                    self.check_files()
                    self.view_sqlite_data()
                    self.view_chroma_data()
                
                else:
                    print(f"❌ 未知命令: {cmd[0]}")
                    print("输入 'quit' 退出或查看上面的命令列表")
            
            except KeyboardInterrupt:
                print("\n👋 退出查看器")
                break
            except Exception as e:
                print(f"❌ 执行命令出错: {str(e)}")


def main():
    """主函数"""
    print("🔍 Memory数据查看器")
    print("="*60)
    
    # 默认使用IA项目的memory_data目录
    memory_data_dir = "/Users/wy/Downloads/Project/IA/memory_data"
    
    # 如果提供了命令行参数，使用指定的目录
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("用法:")
            print("  python view_memory_data.py [memory_data_dir]")
            print("  python view_memory_data.py check")
            print("  python view_memory_data.py search <term>")
            print("  python view_memory_data.py export")
            return
        elif sys.argv[1] not in ['check', 'search', 'export']:
            memory_data_dir = sys.argv[1]
    
    # 创建查看器
    viewer = MemoryDataViewer(memory_data_dir)
    
    # 根据命令行参数执行不同操作
    if len(sys.argv) > 1:
        if sys.argv[1] == 'check':
            viewer.check_files()
        elif sys.argv[1] == 'search':
            if len(sys.argv) > 2:
                search_term = ' '.join(sys.argv[2:])
                viewer.search_data(search_term)
            else:
                print("❌ 请提供搜索词")
        elif sys.argv[1] == 'export':
            viewer.export_all_data()
        else:
            # 进入交互模式
            viewer.interactive_mode()
    else:
        # 默认显示所有信息然后进入交互模式
        viewer.check_files()
        viewer.view_sqlite_data()
        viewer.view_chroma_data()
        viewer.interactive_mode()


if __name__ == "__main__":
    main()