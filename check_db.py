"""检查数据库中的任务类型"""
import asyncio
import sqlite3
from pathlib import Path

async def check_database():
    # 找到数据库文件
    db_path = Path(__file__).parent / "android_builder.db"

    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}")
        return

    # 连接数据库
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # 查询最近的5个任务
    cursor.execute("""
        SELECT id, task_type, status, created_at, resource_package_path
        FROM build_tasks
        ORDER BY created_at DESC
        LIMIT 5
    """)

    rows = cursor.fetchall()

    print("\n最近的5个构建任务:")
    print("-" * 100)
    print(f"{'ID':<40} {'任务类型':<20} {'状态':<15} {'创建时间':<25} {'资源包'}")
    print("-" * 100)

    for row in rows:
        task_id, task_type, status, created_at, resource_path = row
        resource_name = Path(resource_path).name if resource_path else "无"
        print(f"{task_id:<40} {task_type:<20} {status:<15} {created_at:<25} {resource_name}")

    print("-" * 100)

    # 统计任务类型分布
    cursor.execute("""
        SELECT task_type, COUNT(*) as count
        FROM build_tasks
        GROUP BY task_type
    """)

    type_counts = cursor.fetchall()
    print("\n任务类型统计:")
    for task_type, count in type_counts:
        print(f"  {task_type}: {count}")

    conn.close()

if __name__ == "__main__":
    asyncio.run(check_database())
