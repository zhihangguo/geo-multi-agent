"""
自动驾驶评估 Agent 端到端测试脚本

测试层级：
  L1: MySQL 直连查询 (通过 subprocess 调用 autopilot 模块)
  L2: text2sql 服务  (通过 subprocess 调用 autopilot 模块)
  L3: 8002 HTTP 接口
  L4: agent_factory 工具调用
  L5: 端到端 (Runner.run)

运行：
  cd backend/app
  python multi_agent_autopilot/test_e2e.py
"""
import os, sys
import asyncio
import subprocess
import httpx
from datetime import datetime


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
APP_DIR = os.path.join(PROJECT_ROOT, 'backend', 'app')

# 只加 APP_DIR，不加 AUTOPILOT_DIR（避免 config 冲突）
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def banner(msg: str):
    print(f"\n{'='*70}")
    print(f"  {msg}")
    print(f"{'='*70}")


def ok(msg: str):
    print(f"  [OK] {msg}")


def fail(msg: str):
    print(f"  [FAIL] {msg}")


def _conda_python():
    """找到 conda 环境的 python"""
    base = os.path.dirname(sys.executable)
    return sys.executable  # 当前脚本用的 python


def _run_autopilot_script(code: str) -> tuple[bool, str]:
    """在 autopilot 目录下执行 Python 代码（独立进程，避免 import 冲突）"""
    autopilot_dir = os.path.join(PROJECT_ROOT, 'backend', 'autopilot')
    full_code = f"""
import os, sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, r'{autopilot_dir}')
{code}
"""
    result = subprocess.run(
        [_conda_python(), '-c', full_code],
        capture_output=True, text=True, timeout=120
    )
    return result.returncode == 0, result.stdout + result.stderr


# ============================================================
# L1: MySQL 直连
# ============================================================
async def test_l1_mysql():
    banner("L1: MySQL 直连验证")

    code = """
from config.settings import autopilot_settings
print(f'MYSQL_DATABASE = {autopilot_settings.MYSQL_DATABASE}')

from repositories.mysql_repository import IsolatedMySQLRepository
repo = IsolatedMySQLRepository('tenant_a')

cols = repo.get_table_schema('ad_test_runs')
print(f'ad_test_runs 字段数: {len(cols)}')

rows = repo.query(
    "SELECT run_id, weather, scenario_type FROM ad_test_runs WHERE tenant_id = 'tenant_a'"
)
print(f'ad_test_runs 记录数: {len(rows)}')

join_rows = repo.query(
    "SELECT p.run_id, p.object_type, p.precision_score, t.weather "
    "FROM ad_perception_results p "
    "JOIN ad_test_runs t ON p.run_id = t.run_id "
    "WHERE t.weather = 'rainy' AND p.tenant_id = 'tenant_a' "
    "ORDER BY p.precision_score DESC LIMIT 5"
)
print(f'雨天感知精确率查询: {len(join_rows)} 条')
for r in join_rows:
    print(f"  {r['run_id']} | {r['object_type']} | precision={r['precision_score']} | {r['weather']}")
"""
    ok, output = _run_autopilot_script(code)
    if ok:
        print(f"  {output.strip()}")
        return True
    else:
        fail(f"MySQL 查询失败: {output[:300]}")
        return False


# ============================================================
# L2: text2sql 服务
# ============================================================
async def test_l2_text2sql():
    banner("L2: text2sql 服务")

    code = """
import asyncio
from services.text2sql_service import text2sql

async def main():
    result = await text2sql('雨天场景的感知精确率如何', 'tenant_a')
    print(f'success: {result["success"]}')
    if result.get("sql"):
        print(f'sql: {result["sql"][:150]}')
    if result.get("error"):
        print(f'error: {result["error"]}')
    print(f'data_count: {len(result.get("data", []))}')
    if result.get("data"):
        print(f'first_row: {result["data"][0]}')

asyncio.run(main())
"""
    ok, output = _run_autopilot_script(code)
    if ok:
        print(f"  {output.strip()}")
        return True
    else:
        fail(f"text2sql 失败: {output[:300]}")
        return False


# ============================================================
# L3: 8002 HTTP 接口
# ============================================================
async def test_l3_http():
    banner("L3: 8002 HTTP 接口")

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("http://127.0.0.1:8002/autopilot/health")
            if r.status_code == 200:
                ok(f"health: {r.json()}")
            else:
                fail(f"health 返回 {r.status_code}")
                return False
    except httpx.ConnectError:
        fail("8002 端口未启动，请先启动: cd backend/autopilot && python -m uvicorn api.main:create_fast_api --factory --host 127.0.0.1 --port 8002 --reload")
        return False
    except Exception as e:
        fail(f"health 请求异常: {e}")
        return False

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "http://127.0.0.1:8002/autopilot/query",
                json={
                    "question": "雨天场景的感知精确率如何",
                    "tenant_id": "tenant_a",
                    "search_mode": "auto",
                },
            )
            data = r.json()
            if data.get("success"):
                ok(f"query 成功, mode={data.get('mode')}")
                if data.get("answer"):
                    print(f"  回答: {data['answer'][:300]}")
                if data.get("row_count") is not None:
                    print(f"  数据行数: {data['row_count']}")
                return True
            else:
                fail(f"query 失败: {data.get('error')}")
                return False
    except httpx.TimeoutException:
        fail("query 请求超时（60s），8002 服务可能卡住")
        return False
    except Exception as e:
        fail(f"query 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# L4: agent_factory 工具调用
# ============================================================
async def test_l4_agent_tool():
    """测试主服务中 autopilot 工具通过 HTTP 调用 8002 微服务"""
    banner("L4: autopilot 工具 HTTP 直调（模拟 FunctionTool 内部行为）")

    # FunctionTool 内部就是通过 httpx 调用 8002，我们直接模拟
    import json
    question = "雨天场景的感知精确率如何"
    print(f"  问题: {question}")

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "http://127.0.0.1:8002/autopilot/query",
                json={
                    "question": question,
                    "tenant_id": "tenant_a",
                    "search_mode": "auto",
                },
            )
            data = r.json()
            if data.get("success"):
                ok(f"工具返回成功, mode={data.get('mode')}")
                if data.get("answer"):
                    print(f"  回答: {data['answer'][:300]}")
                return True
            else:
                fail(f"工具返回失败: {data.get('error')}")
                return False
    except Exception as e:
        fail(f"工具调用异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# L5: 端到端 (Runner.run 通过 autopilot_agent)
# ============================================================
async def test_l5_e2e():
    banner("L5: 端到端 Runner.run")
    from multi_agent_autopilot.agent import autopilot_agent
    from agents import Runner, RunConfig

    question = "雨天场景的感知精确率如何"
    print(f"  问题: {question}")

    try:
        result = await Runner.run(
            autopilot_agent,
            input=question,
            run_config=RunConfig(tracing_disabled=True)
        )
        output = str(result.final_output).strip()
        if output and len(output) > 20:
            ok(f"端到端成功")
            print(f"  回答: {output[:500]}")
            return True
        else:
            fail(f"输出过短或为空: {output[:100]}")
            return False
    except Exception as e:
        fail(f"端到端异常: {e}")
        import traceback
        traceback.print_exc()
        return False


# ============================================================
# 主流程
# ============================================================
async def main():
    print(f"\n  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = {}

    # L1: MySQL
    results["L1-MySQL"] = await test_l1_mysql()

    # L2: text2sql
    results["L2-text2sql"] = await test_l2_text2sql()

    # L3: HTTP
    results["L3-HTTP-8002"] = await test_l3_http()

    # L4: agent tool
    results["L4-agent_tool"] = await test_l4_agent_tool()

    # L5: e2e
    results["L5-e2e"] = await test_l5_e2e()

    # 汇总
    banner("测试结果汇总")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\n  总计: {passed}/{total} 通过")
    print()


if __name__ == "__main__":
    asyncio.run(main())
