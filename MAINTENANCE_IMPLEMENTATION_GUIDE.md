# 底層維護改進實現指南

## 1. 結構化日誌系統實現

### 新文件：`src/utils/logger_system.py`

```python
import logging
import logging.handlers
import json
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# UTC+8 時區
TZ_OFFSET = timezone(timedelta(hours=8))

class JSONFormatter(logging.Formatter):
    """JSON格式的日誌格式化器"""
    
    def format(self, record: logging.LogRecord) -> str:
        """將日誌記錄轉換為 JSON 格式"""
        log_data = {
            'timestamp': datetime.now(TZ_OFFSET).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'extra': record.__dict__.get('extra', {}),
        }
        
        # 添加異常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class SimpleFormatter(logging.Formatter):
    """簡單的終端日誌格式化器"""
    
    FORMATS = {
        logging.DEBUG: '[%(asctime)s] [DEBUG  ] %(name)s: %(message)s',
        logging.INFO: '[%(asctime)s] [INFO   ] %(name)s: %(message)s',
        logging.WARNING: '[%(asctime)s] [WARNING] %(name)s: %(message)s',
        logging.ERROR: '[%(asctime)s] [ERROR  ] %(name)s: %(message)s',
        logging.CRITICAL: '[%(asctime)s] [CRITICAL] %(name)s: %(message)s',
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日誌"""
        fmt = self.FORMATS.get(record.levelno, self.FORMATS[logging.INFO])
        formatter = logging.Formatter(fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


def setup_logging(
    name: str,
    level: int = logging.INFO,
    log_dir: str = 'data/logs',
    use_json: bool = False,
) -> logging.Logger:
    """
    配置日誌記錄器
    
    Args:
        name: 日誌記錄器名稱
        level: 日誌級別
        log_dir: 日誌文件目錄
        use_json: 是否使用 JSON 格式
    
    Returns:
        配置好的日誌記錄器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重複添加處理程序
    if logger.handlers:
        return logger
    
    # 創建日誌目錄
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 控制台處理程序
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = SimpleFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件處理程序（輪轉）
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / f'{name}.log',
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    if use_json:
        file_formatter = JSONFormatter()
    else:
        file_formatter = SimpleFormatter()
    
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger


# 應用級日誌記錄器
app_logger = setup_logging('bot', logging.INFO)
```

### 使用示例

```python
# 在 src/main.py 中替換
# 舊代碼:
print("[Init] Initializing database manager...")

# 新代碼:
from src.utils.logger_system import app_logger
app_logger.info("Initializing database manager")

# 帶上下文信息:
try:
    init_database_manager()
    app_logger.info("Database manager initialized successfully")
except Exception as e:
    app_logger.error(
        "Failed to initialize database manager",
        extra={'error': str(e), 'type': type(e).__name__},
        exc_info=True
    )
```

---

## 2. 特定化異常捕捉範例

### 改進前後對比

#### 文件：`src/utils/blacklist_manager.py`

```python
# 改進前（通用異常）:
def load_blacklist(self) -> Set[int]:
    try:
        current_time = os.path.getmtime(self.blacklist_file) if os.path.exists(self.blacklist_file) else 0
        if self._blacklist_cache is None or self._last_load_time != current_time:
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._blacklist_cache = set(data.get("blacklisted_users", []))
                self._last_load_time = current_time
        return self._blacklist_cache or set()
    except Exception as e:  # ❌ 太通用
        print(f"[錯誤] 無法載入黑名單: {e}")
        return set()


# 改進後（特定異常）:
def load_blacklist(self) -> Set[int]:
    """
    載入黑名單（帶緩存和完善的錯誤處理）
    
    Returns:
        黑名單用戶 ID 集合
    """
    try:
        current_time = os.path.getmtime(self.blacklist_file) if os.path.exists(self.blacklist_file) else 0
        
        if self._blacklist_cache is None or self._last_load_time != current_time:
            with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._blacklist_cache = set(data.get("blacklisted_users", []))
                self._last_load_time = current_time
        
        return self._blacklist_cache or set()
    
    except FileNotFoundError:
        # 文件不存在，返回空集合
        logger.debug(f"Blacklist file not found: {self.blacklist_file}")
        return set()
    
    except json.JSONDecodeError as e:
        # JSON 解析失敗
        logger.error(
            "Invalid JSON in blacklist file",
            extra={
                'file': self.blacklist_file,
                'error': str(e),
                'line': e.lineno,
                'col': e.colno
            }
        )
        return set()
    
    except PermissionError:
        # 無權限讀取文件
        logger.error(
            "Permission denied reading blacklist file",
            extra={'file': self.blacklist_file}
        )
        return set()
    
    except IsADirectoryError:
        # 路徑是目錄而非文件
        logger.error(
            "Blacklist path is a directory, not a file",
            extra={'path': self.blacklist_file}
        )
        return set()
    
    except Exception as e:
        # 未預期的異常
        logger.critical(
            "Unexpected error loading blacklist",
            extra={
                'file': self.blacklist_file,
                'error': str(e),
                'type': type(e).__name__
            },
            exc_info=True
        )
        return set()
```

---

## 3. 數據驗證層實現

### 新文件：`src/utils/validation.py`

```python
from typing import Any, Dict, Optional
import re

logger = setup_logging('validation', logging.INFO)


class ValidationError(ValueError):
    """數據驗證異常"""
    pass


class UserValidator:
    """用戶數據驗證器"""
    
    @staticmethod
    def validate_user_id(user_id: Any) -> int:
        """
        驗證用戶 ID
        
        Args:
            user_id: 要驗證的用戶 ID
        
        Returns:
            驗證後的用戶 ID
        
        Raises:
            ValidationError: 如果用戶 ID 無效
        """
        if user_id is None:
            raise ValidationError("User ID cannot be None")
        
        if not isinstance(user_id, int):
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                raise ValidationError(f"User ID must be an integer, got {type(user_id).__name__}")
        
        if user_id <= 0:
            raise ValidationError(f"User ID must be positive, got {user_id}")
        
        # Discord 用戶 ID 範圍檢查 (18+ 位數字)
        if user_id > 9223372036854775807:  # 64-bit max
            raise ValidationError(f"User ID exceeds maximum value: {user_id}")
        
        return user_id
    
    @staticmethod
    def validate_username(username: str, min_length: int = 1, max_length: int = 32) -> str:
        """驗證用戶名"""
        if not isinstance(username, str):
            raise ValidationError("Username must be a string")
        
        username = username.strip()
        
        if len(username) < min_length or len(username) > max_length:
            raise ValidationError(
                f"Username length must be between {min_length} and {max_length}, "
                f"got {len(username)}"
            )
        
        # 檢查無效字符
        if not re.match(r'^[a-zA-Z0-9_\-\.]+$', username):
            raise ValidationError("Username contains invalid characters")
        
        return username


class BlacklistValidator:
    """黑名單相關驗證"""
    
    @staticmethod
    def validate_appeal_reason(
        reason: Optional[str],
        min_length: int = 10,
        max_length: int = 1000
    ) -> str:
        """
        驗證申訴原因
        
        Args:
            reason: 申訴原因文本
            min_length: 最小長度
            max_length: 最大長度
        
        Returns:
            驗證並清潔後的原因文本
        
        Raises:
            ValidationError: 如果原因無效
        """
        if reason is None:
            raise ValidationError("Appeal reason cannot be None")
        
        if not isinstance(reason, str):
            raise ValidationError("Appeal reason must be a string")
        
        # 移除前後空白
        reason = reason.strip()
        
        if len(reason) < min_length:
            raise ValidationError(
                f"Appeal reason must be at least {min_length} characters, "
                f"got {len(reason)}"
            )
        
        if len(reason) > max_length:
            raise ValidationError(
                f"Appeal reason cannot exceed {max_length} characters, "
                f"got {len(reason)}"
            )
        
        # 檢查是否為純空白或重複相同字符
        if len(set(reason.replace(' ', ''))) < 3:
            raise ValidationError("Appeal reason must contain meaningful content")
        
        return reason
    
    @staticmethod
    def validate_ban_reason(reason: str, max_length: int = 500) -> str:
        """驗證封禁原因"""
        if not isinstance(reason, str):
            raise ValidationError("Ban reason must be a string")
        
        reason = reason.strip()
        
        if len(reason) > max_length:
            raise ValidationError(
                f"Ban reason cannot exceed {max_length} characters"
            )
        
        return reason


class CommandValidator:
    """命令參數驗證"""
    
    @staticmethod
    def validate_amount(amount: int, min_val: int = 1, max_val: int = 100) -> int:
        """驗證數量參數"""
        if not isinstance(amount, int):
            raise ValidationError("Amount must be an integer")
        
        if not (min_val <= amount <= max_val):
            raise ValidationError(
                f"Amount must be between {min_val} and {max_val}, got {amount}"
            )
        
        return amount


# 驗證裝飾器
def validate_params(**validators):
    """
    參數驗證裝飾器
    
    Args:
        **validators: 參數名稱 -> 驗證函數的映射
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for param, validator in validators.items():
                if param in kwargs:
                    try:
                        kwargs[param] = validator(kwargs[param])
                    except ValidationError as e:
                        logger.warning(f"Validation failed for {param}: {e}")
                        raise
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
```

### 在 Cog 中使用驗證

```python
# src/cogs/core/blacklist.py 中的使用示例

@blacklist_group.command(name="新增", description="將用戶添加到黑名單")
async def blacklist_add(
    self,
    interaction: discord.Interaction,
    user: discord.User,
    reason: str = "未提供原因"
):
    """添加用戶到黑名單"""
    try:
        # 驗證用戶 ID
        validated_user_id = UserValidator.validate_user_id(user.id)
        
        # 驗證原因
        validated_reason = BlacklistValidator.validate_ban_reason(reason)
        
        # 業務邏輯...
        blacklist_manager.add_to_blacklist(validated_user_id)
        
        logger.info(
            "User added to blacklist",
            extra={
                'user_id': validated_user_id,
                'user_name': user.name,
                'reason': validated_reason,
                'executor_id': interaction.user.id
            }
        )
        
    except ValidationError as e:
        logger.warning(
            "Blacklist add validation failed",
            extra={'error': str(e), 'user_id': user.id}
        )
        embed = discord.Embed(
            title="[驗證失敗]",
            description=str(e),
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
```

---

## 4. 健康檢查系統

### 新文件：`src/utils/health_check.py`

```python
import asyncio
import psutil
import os
from typing import Dict, List
from datetime import datetime, timezone, timedelta

TZ_OFFSET = timezone(timedelta(hours=8))
logger = setup_logging('health_check', logging.INFO)


class BotHealthStatus:
    """機器人健康狀態"""
    
    def __init__(self):
        self.checks: Dict[str, bool] = {}
        self.errors: Dict[str, str] = {}
        self.last_check_time = None
        self.check_history: List[Dict] = []
    
    def add_check(self, name: str, passed: bool, error: str = None):
        """添加檢查結果"""
        self.checks[name] = passed
        if error:
            self.errors[name] = error
    
    def is_healthy(self) -> bool:
        """檢查是否健康"""
        return all(self.checks.values())
    
    def get_summary(self) -> Dict:
        """獲取摘要"""
        return {
            'healthy': self.is_healthy(),
            'timestamp': datetime.now(TZ_OFFSET).isoformat(),
            'checks': self.checks,
            'errors': self.errors
        }


class BotHealthChecker:
    """機器人健康檢查器"""
    
    def __init__(self, bot):
        self.bot = bot
        self.status = BotHealthStatus()
    
    async def check_discord_connection(self) -> bool:
        """檢查 Discord 連接"""
        try:
            return self.bot.is_ready() and not self.bot.is_closed()
        except Exception as e:
            self.status.add_check(
                'discord_connection',
                False,
                f"Discord connection check failed: {e}"
            )
            return False
    
    async def check_memory_usage(self, max_percent: float = 80.0) -> bool:
        """檢查記憶體使用"""
        try:
            percent = psutil.virtual_memory().percent
            passed = percent <= max_percent
            
            if not passed:
                self.status.add_check(
                    'memory_usage',
                    False,
                    f"Memory usage {percent}% exceeds limit {max_percent}%"
                )
            else:
                self.status.add_check('memory_usage', True)
            
            return passed
        except Exception as e:
            self.status.add_check('memory_usage', False, str(e))
            return False
    
    async def check_file_system(self) -> bool:
        """檢查文件系統"""
        try:
            required_dirs = ['data', 'logs', 'data/storage', 'data/logs/messages']
            
            for dir_path in required_dirs:
                if not os.path.exists(dir_path):
                    self.status.add_check(
                        'file_system',
                        False,
                        f"Required directory not found: {dir_path}"
                    )
                    return False
            
            self.status.add_check('file_system', True)
            return True
        except Exception as e:
            self.status.add_check('file_system', False, str(e))
            return False
    
    async def check_config_integrity(self) -> bool:
        """檢查配置文件完整性"""
        try:
            import json
            
            config_files = [
                'data/storage/blacklist.json',
                'data/storage/appeals.json'
            ]
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    try:
                        with open(config_file, 'r', encoding='utf-8') as f:
                            json.load(f)
                    except json.JSONDecodeError as e:
                        self.status.add_check(
                            'config_integrity',
                            False,
                            f"Invalid JSON in {config_file}: {e}"
                        )
                        return False
            
            self.status.add_check('config_integrity', True)
            return True
        except Exception as e:
            self.status.add_check('config_integrity', False, str(e))
            return False
    
    async def run_all_checks(self) -> BotHealthStatus:
        """執行所有檢查"""
        self.status = BotHealthStatus()
        
        # 並行執行所有檢查
        await asyncio.gather(
            self.check_discord_connection(),
            self.check_memory_usage(),
            self.check_file_system(),
            self.check_config_integrity()
        )
        
        self.status.last_check_time = datetime.now(TZ_OFFSET)
        
        # 日誌記錄
        if self.status.is_healthy():
            logger.info("Health check passed", extra=self.status.get_summary())
        else:
            logger.warning("Health check failed", extra=self.status.get_summary())
        
        return self.status
    
    async def start_monitoring(self, interval: int = 300):
        """
        定期監控健康狀態
        
        Args:
            interval: 檢查間隔（秒）
        """
        logger.info(f"Starting health check monitoring with {interval}s interval")
        
        while not self.bot.is_closed():
            try:
                await self.run_all_checks()
            except Exception as e:
                logger.error(f"Health check error: {e}", exc_info=True)
            
            await asyncio.sleep(interval)
```

---

## 5. 在 Bot 中集成日誌和健康檢查

### 修改 `src/bot.py`

```python
# 添加到導入
from src.utils.logger_system import app_logger
from src.utils.health_check import BotHealthChecker

class Bot(commands.Bot):
    def __init__(self):
        ...
        self.health_checker = None
    
    async def setup_hook(self):
        """設置鉤子"""
        await self.load_cogs()
        
        # 初始化健康檢查
        self.health_checker = BotHealthChecker(self)
        self.loop.create_task(self.health_checker.start_monitoring())
        
        await self.tree.sync()
    
    async def on_ready(self):
        """機器人準備就緒"""
        app_logger.info(
            "Bot connected to Discord",
            extra={
                'bot_name': self.user.name,
                'bot_id': self.user.id,
                'guilds_count': len(self.guilds)
            }
        )
    
    async def close(self):
        """優雅關閉"""
        app_logger.info("Closing bot and cleaning up resources...")
        await super().close()
```

---

## 推薦實施順序

1. **第 1 天**
   - 創建 `src/utils/logger_system.py`
   - 更新 `src/main.py` 使用新的日誌系統
   - 更新 `src/bot.py` 集成日誌

2. **第 2 天**
   - 創建 `src/utils/validation.py`
   - 更新所有異常捕捉為特定異常
   - 在 `blacklist.py` Cog 中集成驗證

3. **第 3 天**
   - 創建 `src/utils/health_check.py`
   - 在 Bot 中集成健康檢查
   - 測試和調試

4. **第 4 天**
   - 代碼審查
   - 性能測試
   - 文檔更新
