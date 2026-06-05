"""米游社與 HoYoLAB 服務"""

import json
import os
from typing import Optional, Any
import asyncio
from cryptography.fernet import Fernet
import genshin

_DATA_FILE = "data/storage/genshin_accounts.json"


class GenshinService:
    """米游社與 HoYoLAB 帳號管理、數據獲取與每日自動簽到服務"""

    def __init__(self) -> None:
        self._key = self._get_encryption_key()
        self._fernet = Fernet(self._key)
        self._accounts: dict = self._load_accounts()

    def _get_encryption_key(self) -> bytes:
        """獲取或生成加密密鑰，並安全地寫入 .env 檔案中"""
        env_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        )
        key_str = os.getenv("GENSHIN_ENCRYPTION_KEY")
        if not key_str:
            key_bytes = Fernet.generate_key()
            key_str = key_bytes.decode()
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    key_exists = False
                    for i, line in enumerate(lines):
                        if line.startswith("GENSHIN_ENCRYPTION_KEY="):
                            lines[i] = f"GENSHIN_ENCRYPTION_KEY={key_str}\n"
                            key_exists = True
                            break
                    if not key_exists:
                        if lines and not lines[-1].endswith("\n"):
                            lines.append("\n")
                        lines.append(f"GENSHIN_ENCRYPTION_KEY={key_str}\n")
                    with open(env_path, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                except Exception as e:
                    print(f"[警告] 無法將加密密鑰寫入 .env: {e}")
            os.environ["GENSHIN_ENCRYPTION_KEY"] = key_str
            return key_str.encode()
        return key_str.encode()

    def _load_accounts(self) -> dict:
        """載入本地帳號檔案"""
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        if not os.path.exists(_DATA_FILE):
            return {}
        try:
            with open(_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_accounts(self) -> None:
        """儲存本地帳號檔案"""
        os.makedirs(os.path.dirname(_DATA_FILE), exist_ok=True)
        try:
            with open(_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self._accounts, f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"[錯誤] 無法儲存米游社帳號檔案: {e}")

    def encrypt_cookie(self, cookie: str) -> str:
        """加密 Cookie"""
        return self._fernet.encrypt(cookie.strip().encode()).decode()

    def decrypt_cookie(self, encrypted_cookie: str) -> str:
        """解密 Cookie"""
        return self._fernet.decrypt(encrypted_cookie.encode()).decode()

    def get_client(self, discord_user_id: int) -> genshin.Client:
        """為指定 Discord 用戶初始化並獲取 genshin.Client"""
        user_data = self._accounts.get(str(discord_user_id))
        if not user_data:
            raise ValueError("您尚未綁定 HoYoLAB/米游社 帳號，請使用 `/mhy bind` 指令進行綁定。")

        cookie = self.decrypt_cookie(user_data["encrypted_cookie"])
        region_str = user_data.get("region", "global")
        region = genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS

        client = genshin.Client(cookies=cookie, region=region, lang="zh-tw")
        return client

    def get_bound_user(self, discord_user_id: int) -> Optional[dict]:
        """獲取已綁定的使用者設定"""
        return self._accounts.get(str(discord_user_id))

    def get_all_bound_users(self) -> dict:
        """獲取所有已綁定的使用者"""
        return self._accounts

    async def bind_account(
        self, discord_user_id: int, cookie: str, region_str: str
    ) -> list[dict]:
        """驗證並綁定 Cookie"""
        region = genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS
        client = genshin.Client(cookies=cookie, region=region, lang="zh-tw")

        try:
            # 獲取綁定的遊戲帳號列表以驗證 Cookie
            accounts = await client.get_game_accounts()
        except genshin.errors.InvalidCookies:
            raise ValueError("提供的 Cookie 無效或已過期，請重新獲取並輸入。")
        except Exception as e:
            raise ValueError(f"驗證 Cookie 時發生錯誤: {str(e)}")

        game_accounts = []
        for acc in accounts:
            game_accounts.append({
                "game_biz": acc.game_biz,
                "uid": acc.uid,
                "nickname": acc.nickname,
                "level": acc.level,
                "server": acc.server,
                "server_name": acc.server_name,
            })

        encrypted_cookie = self.encrypt_cookie(cookie)
        self._accounts[str(discord_user_id)] = {
            "encrypted_cookie": encrypted_cookie,
            "region": region_str,
            "auto_sign_in": True,
            "game_accounts": game_accounts,
        }
        self._save_accounts()
        return game_accounts

    def unbind_account(self, discord_user_id: int) -> bool:
        """解除綁定帳號"""
        user_key = str(discord_user_id)
        if user_key not in self._accounts:
            return False
        del self._accounts[user_key]
        self._save_accounts()
        return True

    def toggle_auto_sign_in(self, discord_user_id: int, enable: bool) -> bool:
        """開啟或關閉每日自動簽到"""
        user_key = str(discord_user_id)
        if user_key not in self._accounts:
            return False
        self._accounts[user_key]["auto_sign_in"] = enable
        self._save_accounts()
        return True

    # ─────────────── 業務 API ───────────────

    async def get_notes(self, discord_user_id: int, game_str: str) -> dict:
        """獲取指定遊戲的實時便箋"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        
        # 尋找對應遊戲的 UID
        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self._map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        
        uid = uids[0] if uids else None

        if game_str == "genshin":
            notes = await client.get_genshin_notes(uid)
            return {
                "type": "genshin",
                "uid": uid,
                "current_resin": notes.current_resin,
                "max_resin": notes.max_resin,
                "resin_recovery": self._timedelta_to_seconds(notes.remaining_resin_recovery_time),  # int (seconds)
                "current_currency": notes.current_realm_currency,
                "max_currency": notes.max_realm_currency,
                "currency_recovery": self._timedelta_to_seconds(notes.remaining_realm_currency_recovery_time),
                "commissions": notes.completed_commissions,
                "max_commissions": notes.max_commissions,
                "commission_reward_claimed": notes.claimed_commission_reward,
                "weekly_boss_discounts": notes.remaining_resin_discounts,
                "max_weekly_boss_discounts": notes.max_resin_discounts,
            "expeditions": [
                {
                    "character": getattr(exp, "character_icon", ""),
                    "status": getattr(exp, "status", ""),
                    "remained": self._timedelta_to_seconds(getattr(exp, "remaining_time", 0)),
                }
                for exp in notes.expeditions
            ],
                "max_expeditions": notes.max_expeditions,
                "transformer_recovery": self._format_transformer_time(notes.remaining_transformer_recovery_time),
            }
        elif game_str == "starrail":
            notes = await client.get_starrail_notes(uid)
            return {
                "type": "starrail",
                "uid": uid,
                "current_stamina": notes.current_stamina,
                "max_stamina": notes.max_stamina,
                "stamina_recovery": self._timedelta_to_seconds(notes.stamina_recover_time),
                "reserve_stamina": notes.current_reserve_stamina,
                "train_score": notes.current_train_score,
                "max_train_score": notes.max_train_score,
                "rogue_score": notes.current_rogue_score,
                "max_rogue_score": notes.max_rogue_score,
            "expeditions": [
                {
                    "name": getattr(exp, "name", ""),
                    "remained": self._timedelta_to_seconds(getattr(exp, "remaining_time", 0)),
                }
                for exp in notes.expeditions
            ],
                "max_expeditions": notes.total_expedition_num,
            }
        elif game_str == "zzz":
            notes = await client.get_zzz_notes(uid)
            # battery_charge is BatteryCharge object with (current, max, seconds_till_full)
            battery = getattr(notes, "battery_charge", None)
            video = getattr(notes, "video_store_state", None)
            video_str = "未知"
            if video:
                if video.name == "REVENUE_AVAILABLE":
                    video_str = "營業中 (有營業額待整理)"
                elif video.name == "CURRENTLY_OPEN":
                    video_str = "營業中"
                elif video.name == "WAITING_TO_OPEN":
                    video_str = "休息中 (等待開店)"
            
            return {
                "type": "zzz",
                "uid": uid,
                "battery": battery.current if battery else 0,
                "max_battery": battery.max if battery else 240,
                "battery_recovery": battery.seconds_till_full if battery else 0,
                "engagement": notes.engagement,
                "scratch_completed": notes.scratch_card_completed,
                "video_store": video_str,
            }
        elif game_str == "honkai":
            notes = await client.get_honkai_notes(uid)
            return {
                "type": "honkai",
                "uid": uid,
                "current_stamina": notes.current_stamina,
                "max_stamina": notes.max_stamina,
                "stamina_recovery": self._timedelta_to_seconds(notes.stamina_recover_time),
                "train_score": notes.current_train_score,
            }
        else:
            raise ValueError("不支援的遊戲類型。")

    async def redeem_code(self, discord_user_id: int, game_str: str, code: str) -> list[dict]:
        """為使用者在此遊戲的所有繫結 UID 兌換禮包碼"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        
        # 篩選對應遊戲的 UIDs
        game_accs = [
            acc
            for acc in user_data.get("game_accounts", [])
            if self._map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        
        if not game_accs:
            raise ValueError(f"您在此 Bot 中尚未綁定任何 {game_str} 遊戲帳號。")

        results = []
        game_enum = self._get_game_enum(game_str)

        for acc in game_accs:
            uid = acc["uid"]
            try:
                await client.redeem_code(code, uid=uid, game=game_enum)
                results.append({"uid": uid, "nickname": acc["nickname"], "success": True, "message": "兌換成功！"})
            except genshin.errors.RedemptionClaimed:
                results.append({"uid": uid, "nickname": acc["nickname"], "success": False, "message": "該兌換碼已被領取過。"})
            except genshin.errors.RedemptionCooldown:
                results.append({"uid": uid, "nickname": acc["nickname"], "success": False, "message": "兌換頻率太快，請稍後再試。"})
            except genshin.errors.RedemptionInvalid:
                results.append({"uid": uid, "nickname": acc["nickname"], "success": False, "message": "無效的兌換碼或不適用於此伺服器。"})
            except Exception as e:
                results.append({"uid": uid, "nickname": acc["nickname"], "success": False, "message": f"錯誤: {str(e)}"})

        return results

    async def get_stats(self, discord_user_id: int, game_str: str) -> dict:
        """獲取使用者的遊戲統計數據"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        
        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self._map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        uid = uids[0] if uids else None
        if not uid:
            raise ValueError(f"沒有找到已綁定的 {game_str} 帳號。")

        if game_str == "genshin":
            data = await client.get_genshin_user(uid)
            return {
                "nickname": data.info.nickname,
                "level": data.info.level,
                "days_active": data.stats.days_active,
                "achievements": data.stats.achievements,
                "characters": len(data.characters),
                "chests_opened": (
                    data.stats.common_chests
                    + data.stats.exquisite_chests
                    + data.stats.precious_chests
                    + data.stats.luxurious_chests
                    + data.stats.remarkable_chests
                ),
                "teapot_level": data.teapot.level if data.teapot else 0,
            }
        elif game_str == "starrail":
            data = await client.get_starrail_user(uid)
            return {
                "nickname": data.info.nickname,
                "level": data.info.level,
                "days_active": data.stats.active_days,
                "achievements": data.stats.achievement_num,
                "characters": data.stats.avatar_num,
                "chests_opened": data.stats.chest_num,
            }
        elif game_str == "zzz":
            data = await client.get_zzz_user(uid)
            acc_info = next(
                (acc for acc in user_data.get("game_accounts", []) if acc["uid"] == uid),
                None
            )
            nickname = acc_info["nickname"] if acc_info else "未知"
            level = acc_info["level"] if acc_info else 0
            return {
                "nickname": nickname,
                "level": level,
                "days_active": data.stats.active_days,
                "achievements": data.stats.achievement_count,
                "characters": data.stats.character_num,
                "bangboo_obtained": data.stats.bangboo_obtained,
            }
        elif game_str == "honkai":
            data = await client.get_honkai_user(uid)
            return {
                "nickname": data.info.nickname,
                "level": data.info.level,
                "days_active": data.stats.active_days,
                "characters": data.stats.battlesuits,
            }
        else:
            raise ValueError("不支援的遊戲類型")

    async def get_abyss_stats(self, discord_user_id: int, game_str: str) -> dict:
        """獲取深淵數據 (當前期數)"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        
        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self._map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        uid = uids[0] if uids else None
        if not uid:
            raise ValueError(f"沒有找到已綁定的 {game_str} 帳號。")

        if game_str == "genshin":
            abyss = await client.get_spiral_abyss(uid, previous=False)
            return {
                "total_battles": abyss.total_battles,
                "total_wins": abyss.total_wins,
                "total_stars": abyss.total_stars,
                "max_floor": abyss.max_floor,
                "is_unlock": abyss.unlocked,
            }
        elif game_str == "starrail":
            try:
                challenge, pf, shadow, anomaly = await asyncio.gather(
                    client.get_starrail_challenge(uid, previous=False),
                    client.get_starrail_pure_fiction(uid, previous=False),
                    client.get_apocalyptic_shadow(uid, previous=False),
                    client.get_anomaly_arbitration(uid, previous=False),
                    return_exceptions=True
                )
            except Exception as e:
                raise e

            moc_stars = challenge.total_stars if not isinstance(challenge, Exception) and challenge is not None and getattr(challenge, "has_data", False) else 0
            moc_max = challenge.max_floor if not isinstance(challenge, Exception) and challenge is not None and getattr(challenge, "has_data", False) and challenge.max_floor else "無數據"
            moc_name = challenge.name if not isinstance(challenge, Exception) and challenge is not None and getattr(challenge, "has_data", False) else "混沌回憶"

            pf_stars = pf.total_stars if not isinstance(pf, Exception) and pf is not None and getattr(pf, "has_data", False) else 0
            pf_max = pf.max_floor if not isinstance(pf, Exception) and pf is not None and getattr(pf, "has_data", False) and pf.max_floor else "無數據"
            pf_name = pf.name if not isinstance(pf, Exception) and pf is not None and getattr(pf, "has_data", False) else "虛構敘事"

            shadow_stars = shadow.total_stars if not isinstance(shadow, Exception) and shadow is not None and getattr(shadow, "has_data", False) else 0
            shadow_max = shadow.max_floor if not isinstance(shadow, Exception) and shadow is not None and getattr(shadow, "has_data", False) and shadow.max_floor else "無數據"
            
            shadow_name = "末日幻影"
            if not isinstance(shadow, Exception) and shadow is not None and getattr(shadow, "has_data", False):
                if hasattr(shadow, "seasons") and shadow.seasons:
                    shadow_name = shadow.seasons[0].name

            # Anomaly Arbitration (異相仲裁)
            anomaly_stars_val = 0
            anomaly_max = "無數據"
            anomaly_name = "異相仲裁"
            
            anomaly_record = None
            if not isinstance(anomaly, Exception) and anomaly is not None and hasattr(anomaly, "records") and anomaly.records:
                for r in anomaly.records:
                    if getattr(r.season, "status", "") == "active":
                        anomaly_record = r
                        break
                if not anomaly_record:
                    anomaly_record = anomaly.records[0]

            if anomaly_record and getattr(anomaly_record, "has_data", False):
                boss_stars = getattr(anomaly_record, "boss_stars", 0)
                mini_boss_stars = getattr(anomaly_record, "mini_boss_stars", 0)
                total_stars = boss_stars + mini_boss_stars
                
                anomaly_stars_val = f"{total_stars} (騎士 {mini_boss_stars}★ / 首領 {boss_stars}★)"
                
                boss_rec = getattr(anomaly_record, "boss_record", None)
                if boss_rec and getattr(boss_rec, "has_data", False):
                    boss_name = getattr(anomaly_record.boss, "name", "首領")
                    anomaly_max = f"首領 {boss_name} 已擊敗"
                else:
                    cleared_minis = sum(1 for m in getattr(anomaly_record, "mini_boss_records", []) if getattr(m, "has_data", False))
                    anomaly_max = f"騎士挑戰中 ({cleared_minis}/3)"
                
                if hasattr(anomaly_record.season, "name") and anomaly_record.season.name:
                    anomaly_name = anomaly_record.season.name

            return {
                "moc_name": to_traditional_chinese(moc_name),
                "moc_stars": moc_stars,
                "moc_max": to_traditional_chinese(moc_max),
                "pf_name": to_traditional_chinese(pf_name),
                "pf_stars": pf_stars,
                "pf_max": to_traditional_chinese(pf_max),
                "shadow_name": to_traditional_chinese(shadow_name),
                "shadow_stars": shadow_stars,
                "shadow_max": to_traditional_chinese(shadow_max),
                "anomaly_name": to_traditional_chinese(anomaly_name),
                "anomaly_stars": anomaly_stars_val,
                "anomaly_max": to_traditional_chinese(anomaly_max),
            }
        elif game_str == "zzz":
            data = await client.get_zzz_user(uid)
            return {
                "shiyu_defense": data.stats.shiyu_defense_frontiers if data.stats else "未知",
            }
        else:
            raise ValueError("該遊戲不支援或暫無深淵數據統計接口。")

    async def claim_daily_signin_for_user(self, discord_user_id: int) -> list[dict]:
        """手動或定時為單個使用者擁有的所有遊戲帳號簽到"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        results = []

        completed_games = set()
        
        for acc in user_data.get("game_accounts", []):
            game_str = self._map_game_biz_to_str(acc["game_biz"])
            if game_str == "unknown" or game_str in completed_games:
                continue

            game_enum = self._get_game_enum(game_str)
            try:
                reward = await client.claim_daily_reward(game=game_enum)
                results.append({
                    "game": game_str,
                    "nickname": acc["nickname"],
                    "success": True,
                    "message": f"簽到成功！獲得: {reward.name} x{reward.amount}" if reward else "簽到成功！",
                })
            except genshin.errors.AlreadyClaimed:
                results.append({
                    "game": game_str,
                    "nickname": acc["nickname"],
                    "success": True,
                    "message": "今日已簽到過。",
                })
            except Exception as e:
                results.append({
                    "game": game_str,
                    "nickname": acc["nickname"],
                    "success": False,
                    "message": f"簽到失敗: {str(e)}",
                })
            completed_games.add(game_str)

        return results

    async def run_global_auto_sign_in(self) -> dict[int, list[dict]]:
        """定時背景任務：為所有啟用自動簽到的使用者執行簽到"""
        results = {}
        for user_id, info in self._accounts.items():
            if not info.get("auto_sign_in", True):
                continue
            try:
                user_results = await self.claim_daily_signin_for_user(int(user_id))
                results[int(user_id)] = user_results
            except Exception as e:
                results[int(user_id)] = [{"game": "all", "nickname": "N/A", "success": False, "message": f"初始化失敗: {str(e)}"}]
            await asyncio.sleep(10)
        return results

    # ─────────────── 輔助工具 ───────────────

    def _map_game_biz_to_str(self, game_biz: str) -> str:
        """將 game_biz 對應到內部遊戲名稱"""
        game_biz = game_biz.lower()
        if "hk4e" in game_biz:
            return "genshin"
        elif "hkrpg" in game_biz:
            return "starrail"
        elif "nap" in game_biz:
            return "zzz"
        elif "bh3" in game_biz:
            return "honkai"
        elif "nxx" in game_biz:
            return "tot"
        return "unknown"

    def _get_game_enum(self, game_str: str) -> genshin.types.Game:
        """對應遊戲字串為 genshin.types.Game 枚舉"""
        mapping = {
            "genshin": genshin.types.Game.GENSHIN,
            "starrail": genshin.types.Game.STARRAIL,
            "zzz": genshin.types.Game.ZZZ,
            "honkai": genshin.types.Game.HONKAI,
            "tot": genshin.types.Game.TOT,
        }
        return mapping.get(game_str, genshin.types.Game.GENSHIN)

    def _format_transformer_time(self, recovery_time: Any) -> str:
        """格式化參量質變儀的時間"""
        if not recovery_time:
            return "已就緒"
        
        if hasattr(recovery_time, "total_seconds"):
            seconds = int(recovery_time.total_seconds())
        elif hasattr(recovery_time, "value"):
            seconds = int(recovery_time.value)
        else:
            try:
                seconds = int(recovery_time)
            except Exception:
                return str(recovery_time)
                
        if seconds <= 0:
            return "已就緒"
            
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}天")
        if hours > 0:
            parts.append(f"{hours}小時")
        if minutes > 0:
            parts.append(f"{minutes}分鐘")
            
        return "".join(parts) + "後就緒"

    def _timedelta_to_seconds(self, td: Any) -> int:
        """將 timedelta 或整數時間安全轉換為秒數"""
        if not td:
            return 0
        if hasattr(td, "total_seconds"):
            return int(td.total_seconds())
        try:
            return int(td)
        except Exception:
            return 0


def to_traditional_chinese(text: str) -> str:
    """將簡體字與特定星穹鐵道術語轉換為繁體中文"""
    if not text:
        return text
    # Dictionary of specific Star Rail terms and common words
    replacements = {
        "混沌回忆": "混沌回憶",
        "虚构叙事": "虛構敘事",
        "末日幻影": "末日幻影",
        "异相仲裁": "異相仲裁",
        "值日行动": "值日行動",
        "造象立说": "造像立說",
        "造像立说": "造像立說",
        "行动": "行動",
        "战斗": "戰鬥",
        "胜利": "勝利",
        "次数": "次數",
        "难度": "難度",
        "无数据": "無數據",
        "当前赛季": "當前賽季",
        "最深进度": "最深進度",
        "获得星数": "獲得星數",
        "已满": "已滿",
        "约": "約",
        "小时": "小時",
        "分钟": "分鐘",
        "后就绪": "後就緒",
        "已就绪": "已就緒",
        "未知": "未知",
        "无进行中的": "無進行中的",
        "派遣委托": "派遣委託",
        "探索派遣": "探索派遣",
        "委托": "委託",
        "剩余": "剩餘",
        "已完成": "已完成",
        "未完成": "未完成",
        "录像带店状态": "錄影帶店狀態",
        "今日刮刮卡": "今日刮刮卡",
        "每日活跃": "每日活躍",
        "电量": "電量",
        "体力": "體力",
        "每日使命": "每日使命",
        "开拓力": "開拓力",
        "后备开拓力": "後備開拓力",
        "每日实训": "每日實訓",
        "模拟宇宙": "模擬宇宙",
        "分": "分",
        "原神": "原神",
        "崩坏：星穹铁道": "崩壞：星穹鐵道",
        "绝区零": "絕區零",
        "崩坏3rd": "崩壞3rd",
        "未定事件簿": "未定事件簿",
        "角色昵称": "角色暱稱",
        "开拓等级": "開拓等級",
        "绳网等级": "繩網等級",
        "角色等级": "角色等級",
        "活跃天数": "活躍天數",
        "达成成就": "達成成就",
        "角色/代理人数量": "角色/代理人數量",
        "开启宝箱数": "開啟寶箱數",
        "尘歌壶等级": "塵歌壺等級",
        "获得邦布数": "獲得邦布數",
        "最深抵达层数": "最深抵達層數",
        "获得总星数": "獲得總星數",
        "战斗/胜利次数": "戰鬥/勝利次數",
        "胜": "勝",
    }
    
    # Character mapping for dynamic parts
    char_map = {
        "忆": "憶", "动": "動", "难": "難", "关": "關", "层": "層",
        "战": "戰", "斗": "鬥", "记": "記", "说": "說", "构": "構",
        "叙": "敘", "事": "事", "异": "異", "仲": "仲", "裁": "裁",
        "历": "歷", "压": "壓", "厌": "厭", "厂": "廠", "广": "廣",
        "显": "顯", "风": "風", "飞": "飛", "饰": "飾", "馆": "館",
        "马": "馬", "骑": "騎", "骗": "騙", "鱼": "魚", "鸟": "鳥",
        "麦": "麥", "黄": "黃", "黑": "黑", "齐": "齊", "齿": "齒",
        "龙": "龍", "万": "萬", "与": "與", "专": "專", "业": "業",
        "东": "東", "丝": "絲", "丢": "丟", "两": "兩", "严": "嚴",
        "个": "個", "丰": "豐", "临": "臨", "为": "為", "丽": "麗",
        "举": "舉", "么": "麼", "义": "義", "乐": "樂", "习": "習",
        "乡": "鄉", "书": "書", "买": "買", "乱": "亂", "争": "爭",
        "于": "於", "亏": "虧", "亚": "亞", "产": "產", "亲": "親",
        "单": "單", "员": "員", "呗": "唄", "呕": "嘔", "呢": "呢",
        "味": "味", "呼": "呼", "命": "命", "和": "和", "咏": "詠",
        "咙": "嚨", "咛": "嚀", "咤": "吒", "咨": "諮", "哈": "哈",
        "咳": "咳", "咸": "鹹", "响": "響", "哎": "哎", "哑": "啞",
        "哒": "噠", "哔": "嗶", "哙": "噲", "哝": "噥", "哟": "喲",
        "哭": "哭", "哲": "哲", "哺": "哺", "哼": "哼", "哽": "哽",
        "唠": "嘮", "啸": "嘯", "嘲": "嘲", "嘴": "嘴", "嘶": "嘶",
        "嘹": "嘹", "嘻": "嘻", "嘿": "嘿", "嘱": "囑", "嚷": "嚷",
        "嚼": "嚼", "囊": "囊", "嚣": "囂", "囔": "囔", "圣": "聖",
        "执": "執", "坚": "堅", "坛": "壇", "坝": "壩", "报": "報",
        "场": "場", "块": "塊", "尘": "塵", "境": "境", "垫": "墊",
        "墓": "墓", "坠": "墜", "增": "增", "墨": "墨", "墙": "牆",
        "壮": "壯", "声": "聲", "壳": "殼", "破": "破", "韧": "韌",
        "击": "擊", "壶": "壺", "处": "處", "备": "備", "复": "複",
        "头": "頭", "奥": "奧", "夺": "奪", "奋": "奮", "妇": "婦",
        "妈": "媽", "妥": "妥", "姐": "姐", "姑": "姑", "姓": "姓",
        "姿": "姿", "威": "威", "娘": "娘", "娜": "娜", "娟": "娟",
        "娱": "娛", "娶": "娶", "婆": "婆", "婉": "婉", "婚": "婚",
        "媒": "媒", "媚": "媚", "媛": "媛", "媳": "媳", "嫁": "嫁",
        "嫉": "嫉", "嫌": "嫌", "嫩": "嫩", "嬉": "嬉", "娇": "嬌",
        "婶": "嬸", "婵": "嬋", "婴": "嬰", "嬷": "嬤", "孙": "孫",
        "学": "學", "孪": "攣", "宝": "寶", "实": "實", "宠": "寵",
        "审": "審", "宪": "憲", "宫": "宮", "宽": "寬", "宾": "賓",
        "察": "察", "寝": "寢", "对": "對", "寻": "尋", "导": "導",
        "寿": "壽", "封": "封", "射": "射", "将": "將", "尉": "尉",
        "尊": "尊", "小": "小", "少": "少", "尔": "爾", "尖": "尖",
        "尚": "尚", "尝": "嘗", "尤": "尤", "就": "就", "尺": "尺",
        "尼": "尼", "尽": "盡", "尾": "尾", "尿": "尿", "局": "局",
        "屁": "屁", "居": "居", "屈": "屈", "届": "屆", "屋": "屋",
        "屎": "屎", "屏": "屏", "展": "展", "属": "屬", "屠": "屠",
        "屡": "屢", "履": "履", "山": "山", "岁": "歲", "岂": "豈",
        "岗": "崗", "岘": "峴", "岚": "嵐", "岛": "島", "岳": "岳",
        "岸": "岸", "峡": "峽", "峦": "巒", "岩": "岩", "岭": "嶺",
        "岱": "岱", "炭": "炭", "峥": "崢", "崂": "嶗", "崃": "崍",
        "崇": "崇", "崎": "崎", "崔": "崔", "崖": "崖", "崛": "崛",
        "嶂": "嶂", "崭": "嶄", "岖": "嶇", "峭": "峭", "峰": "峰",
        "峻": "峻", "峨": "峨", "峪": "峪", "仑": "崙", "巅": "巔",
        "巢": "巢", "左": "左", "巧": "巧", "巨": "巨", "巩": "鞏",
        "巫": "巫", "差": "差", "己": "己", "已": "已", "巳": "巳",
        "巴": "巴", "巷": "巷", "巽": "巽", "巾": "巾", "币": "幣",
        "市": "市", "布": "布", "帅": "帥", "帆": "帆", "师": "師",
        "希": "希", "帐": "帳", "帕": "帕", "帖": "帖", "帘": "簾",
        "帚": "帚", "帛": "帛", "帜": "幟", "帝": "帝", "带": "帶",
        "帧": "幀", "席": "席", "帮": "幫", "帷": "帷", "常": "常",
        "帽": "帽", "幂": "冪", "幅": "幅", "幌": "幌", "幔": "幔",
        "幕": "幕", "幡": "幡", "幢": "幢", "干": "幹", "平": "平",
        "年": "年", "并": "並", "幸": "幸", "幼": "幼", "幽": "幽",
        "庇": "庇", "床": "床", "序": "序", "庐": "廬", "库": "庫",
        "应": "應", "底": "底", "店": "店", "庙": "廟", "庚": "庚",
        "府": "府", "庞": "龐", "废": "廢", "度": "度", "座": "座",
        "庭": "庭", "庵": "庵", "庶": "庶", "康": "康", "庸": "庸",
        "厢": "廂", "厦": "廈", "廉": "廉", "廊": "廊", "廓": "廓",
        "廖": "廖", "延": "延", "廷": "廷", "建": "建", "廿": "廿",
        "开": "開", "弁": "弁", "弃": "棄", "弄": "弄", "弊": "弊",
        "弋": "弋", "式": "式", "弑": "弒", "弓": "弓", "引": "引",
        "弗": "弗", "弘": "弘", "弛": "弛", "弟": "弟", "张": "張",
        "弥": "彌", "弦": "弦", "弯": "彎", "弱": "弱", "弹": "彈",
        "强": "強", "归": "歸", "当": "當", "录": "錄", "彖": "彖",
        "彗": "彗", "汇": "匯", "彝": "彝", "影": "影", "从": "從",
        "德": "德", "徽": "徽", "心": "心", "必": "必", "忏": "懺",
        "忌": "忌", "忍": "忍", "忐": "忐", "忑": "忑", "忒": "忒",
        "忖": "忖", "志": "志", "忘": "忘", "忙": "忙", "忠": "忠",
        "忡": "忡", "忤": "忤", "忧": "憂", "忪": "忪", "快": "快",
        "怀": "懷", "态": "態", "怂": "慫", "怃": "憮", "怄": "慪",
        "怅": "悵", "怆": "愴", "愧": "愧", "悫": "愨", "愆": "愆",
        "意": "意", "愚": "愚", "爱": "愛", "感": "感", "惬": "愜",
        "愦": "憒", "慨": "慨", "愤": "憤", "憧": "憧", "憨": "憨",
        "憩": "憩", "憬": "憬", "懂": "懂", "懈": "懈", "懊": "懊",
        "懑": "懣", "懒": "懶", "懔": "懍", "懦": "懦", "懵": "懵",
        "懿": "懿", "戈": "戈", "戊": "戊", "戌": "戌", "戍": "戍",
        "戎": "戎", "成": "成", "我": "我", "戒": "戒", "戕": "戕",
        "或": "或", "戗": "戧", "戚": "戚", "戛": "戛", "戟": "戟",
        "戡": "戡", "戢": "戢", "截": "截", "戬": "戩", "戮": "戮",
        "戳": "戳", "戴": "戴", "户": "戶", "房": "房", "所": "所",
        "扁": "扁", "扇": "扇", "手": "手", "才": "才", "扎": "扎",
        "扑": "撲", "打": "打", "扔": "扔", "托": "托", "扛": "扛",
        "扣": "扣", "扦": "扦", "执": "執", "扩": "擴", "扫": "掃",
        "扬": "揚", "扭": "扭", "扮": "扮", "扯": "扯", "扰": "擾",
        "扳": "扳", "扶": "扶", "批": "批", "扼": "扼", "找": "找",
        "承": "承", "技": "技", "抄": "抄", "抉": "抉", "把": "把",
        "抑": "抑", "抒": "抒", "抓": "抓", "投": "投", "抖": "抖",
        "抗": "抗", "折": "折", "抚": "撫", "抛": "拋", "拔": "拔",
        "择": "擇", "抟": "摶", "抠": "摳", "论": "論", "抢": "搶",
        "护": "護", "报": "報", "抬": "抬", "抱": "抱", "抵": "抵",
        "抹": "抹", "押": "押", "抽": "抽", "抿": "抿", "拂": "拂",
        "担": "擔", "拆": "拆", "拇": "拇", "拈": "拈", "拉": "拉",
        "拌": "拌", "拍": "拍", "拎": "拎", "拐": "拐", "拒": "拒",
        "拓": "拓", "拖": "拖", "拗": "拗", "拘": "拘", "拙": "拙",
        "拼": "拼", "招": "招", "拜": "拜", "拟": "擬", "拢": "攏",
        "拣": "揀", "拥": "擁", "拦": "攔", "拧": "擰", "拨": "撥",
        "挂": "掛", "按": "按", "挑": "挑", "挖": "挖", "挚": "摯",
        "挝": "撾", "挞": "撻", "挟": "挾", "挠": "撓", "挡": "擋",
        "挢": "撟", "挣": "掙", "挤": "擠", "挥": "揮", "捞": "撈",
        "损": "損", "捡": "撿", "换": "換", "捣": "搗", "捧": "捧",
        "捩": "捩", "捭": "捭", "据": "據", "掳": "擄", "掴": "摑",
        "掷": "擲", "掸": "撣", "掺": "摻", "掼": "摜", "揽": "攬",
        "提": "提", "插": "插", "揖": "揖", "握": "握", "揣": "揣",
        "揩": "揩", "揪": "揪", "揭": "揭", "援": "援", "摇": "搖",
        "搜": "搜", "搬": "搬", "搭": "搭", "携": "攜", "搽": "搽",
        "榨": "榨", "摄": "攝", "摆": "擺", "摈": "擯", "摊": "攤",
        "攒": "攢", "撵": "攆", "撷": "擷", "撕": "撕", "撒": "撒",
        "撰": "撰", "撑": "撐", "播": "播", "撤": "撤", "阻": "阻",
        "阿": "阿", "陀": "陀", "陈": "陳", "陆": "陸", "险": "險",
        "随": "隨", "隐": "隱", "雅": "雅", "集": "集", "雨": "雨",
        "雪": "雪", "霸": "霸", "青": "青", "静": "靜", "非": "非",
        "面": "面", "革": "革", "韦": "韋", "韩": "韓", "音": "音",
        "页": "頁", "顶": "頂", "项": "項", "顺": "順", "须": "須",
        "预": "預", "顽": "頑", "顧": "顧", "颤": "顫", "首": "首",
        "香": "香", "骨": "骨", "高": "高", "鬼": "鬼", "魂": "魂",
        "魅": "魅", "魔": "魔", "鹿": "鹿", "麻": "麻", "黎": "黎",
        "默": "默", "鼓": "鼓", "鼠": "鼠", "鼻": "鼻",
    }
    
    # 1. Apply string replacements first
    for k, v in replacements.items():
        text = text.replace(k, v)
        
    # 2. Character mapping for the rest
    chars = []
    for c in text:
        chars.append(char_map.get(c, c))
    return "".join(chars)
