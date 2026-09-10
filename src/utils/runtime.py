"""管理共享服務的一次性啟動與非同步關閉。"""

import asyncio

from .config_optimizer import get_config_manager
from .config_optimizer import init_config_manager
from .database_manager import get_database_manager
from .database_manager import init_database_manager
from .github_manager import get_github_manager
from .network_optimizer import get_network_optimizer
from .network_optimizer import init_network_optimizer


async def initialize_optimizations() -> None:
    init_database_manager()
    init_config_manager()
    init_network_optimizer()
    manager = get_database_manager()
    assert manager is not None
    await manager.start_cleanup_task(interval=300)


async def close_optimizations() -> None:
    """每個服務都嘗試關閉，任一失敗仍向呼叫者回報。"""
    services = (
        get_config_manager(),
        get_database_manager(),
        get_network_optimizer(),
        get_github_manager(),
    )
    results = await asyncio.gather(
        *(service.close() for service in services if service is not None),
        return_exceptions=True,
    )
    errors = [result for result in results if isinstance(result, BaseException)]
    if errors:
        raise RuntimeError("共享服務清理失敗") from errors[0]
