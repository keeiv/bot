"""米游社與 HoYoLAB 服務"""

import asyncio
import json
import os
from typing import Any, Optional

import genshin
from cryptography.fernet import Fernet

from src.utils.text_converter import to_traditional_chinese

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
            self._write_key_to_env(env_path, key_str)
            os.environ["GENSHIN_ENCRYPTION_KEY"] = key_str
            return key_str.encode()
        return key_str.encode()

    def _write_key_to_env(self, env_path: str, key_str: str) -> None:
        """將加密密鑰寫入 .env 檔案"""
        if not os.path.exists(env_path):
            return
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
            raise ValueError(
                "您尚未綁定 HoYoLAB/米游社 帳號，請使用 `/mhy bind` 指令進行綁定。"
            )

        cookie = self.decrypt_cookie(user_data["encrypted_cookie"])
        region_str = user_data.get("region", "global")
        region = (
            genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS
        )

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
        region = (
            genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS
        )
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
            game_accounts.append(
                {
                    "game_biz": acc.game_biz,
                    "uid": acc.uid,
                    "nickname": acc.nickname,
                    "level": acc.level,
                    "server": acc.server,
                    "server_name": acc.server_name,
                }
            )

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
                "resin_recovery": self._timedelta_to_seconds(
                    notes.remaining_resin_recovery_time
                ),  # int (seconds)
                "current_currency": notes.current_realm_currency,
                "max_currency": notes.max_realm_currency,
                "currency_recovery": self._timedelta_to_seconds(
                    notes.remaining_realm_currency_recovery_time
                ),
                "commissions": notes.completed_commissions,
                "max_commissions": notes.max_commissions,
                "commission_reward_claimed": notes.claimed_commission_reward,
                "weekly_boss_discounts": notes.remaining_resin_discounts,
                "max_weekly_boss_discounts": notes.max_resin_discounts,
                "expeditions": [
                    {
                        "character": getattr(exp, "character_icon", ""),
                        "status": getattr(exp, "status", ""),
                        "remained": self._timedelta_to_seconds(
                            getattr(exp, "remaining_time", 0)
                        ),
                    }
                    for exp in notes.expeditions
                ],
                "max_expeditions": notes.max_expeditions,
                "transformer_recovery": self._format_transformer_time(
                    notes.remaining_transformer_recovery_time
                ),
            }
        elif game_str == "starrail":
            notes = await client.get_starrail_notes(uid)
            return {
                "type": "starrail",
                "uid": uid,
                "current_stamina": notes.current_stamina,
                "max_stamina": notes.max_stamina,
                "stamina_recovery": self._timedelta_to_seconds(
                    notes.stamina_recover_time
                ),
                "reserve_stamina": notes.current_reserve_stamina,
                "train_score": notes.current_train_score,
                "max_train_score": notes.max_train_score,
                "rogue_score": notes.current_rogue_score,
                "max_rogue_score": notes.max_rogue_score,
                "expeditions": [
                    {
                        "name": getattr(exp, "name", ""),
                        "remained": self._timedelta_to_seconds(
                            getattr(exp, "remaining_time", 0)
                        ),
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
                "stamina_recovery": self._timedelta_to_seconds(
                    notes.stamina_recover_time
                ),
                "train_score": notes.current_train_score,
            }
        else:
            raise ValueError("不支援的遊戲類型。")

    async def redeem_code(
        self, discord_user_id: int, game_str: str, code: str
    ) -> list[dict]:
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
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": True,
                        "message": "兌換成功！",
                    }
                )
            except genshin.errors.RedemptionClaimed:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": "該兌換碼已被領取過。",
                    }
                )
            except genshin.errors.RedemptionCooldown:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": "兌換頻率太快，請稍後再試。",
                    }
                )
            except genshin.errors.RedemptionInvalid:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": "無效的兌換碼或不適用於此伺服器。",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": f"錯誤: {str(e)}",
                    }
                )

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
                (
                    acc
                    for acc in user_data.get("game_accounts", [])
                    if acc["uid"] == uid
                ),
                None,
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
                    return_exceptions=True,
                )
            except Exception as e:
                raise e

            moc_stars = (
                challenge.total_stars
                if not isinstance(challenge, Exception)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                else 0
            )
            moc_max = (
                challenge.max_floor
                if not isinstance(challenge, Exception)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                and challenge.max_floor
                else "無數據"
            )
            moc_name = (
                challenge.name
                if not isinstance(challenge, Exception)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                else "混沌回憶"
            )

            pf_stars = (
                pf.total_stars
                if not isinstance(pf, Exception)
                and pf is not None
                and getattr(pf, "has_data", False)
                else 0
            )
            pf_max = (
                pf.max_floor
                if not isinstance(pf, Exception)
                and pf is not None
                and getattr(pf, "has_data", False)
                and pf.max_floor
                else "無數據"
            )
            pf_name = (
                pf.name
                if not isinstance(pf, Exception)
                and pf is not None
                and getattr(pf, "has_data", False)
                else "虛構敘事"
            )

            shadow_stars = (
                shadow.total_stars
                if not isinstance(shadow, Exception)
                and shadow is not None
                and getattr(shadow, "has_data", False)
                else 0
            )
            shadow_max = (
                shadow.max_floor
                if not isinstance(shadow, Exception)
                and shadow is not None
                and getattr(shadow, "has_data", False)
                and shadow.max_floor
                else "無數據"
            )

            shadow_name = "末日幻影"
            if (
                not isinstance(shadow, Exception)
                and shadow is not None
                and getattr(shadow, "has_data", False)
            ):
                if hasattr(shadow, "seasons") and shadow.seasons:
                    shadow_name = shadow.seasons[0].name

            # Anomaly Arbitration (異相仲裁)
            anomaly_stars_val = 0
            anomaly_max = "無數據"
            anomaly_name = "異相仲裁"

            anomaly_record = None
            if (
                not isinstance(anomaly, Exception)
                and anomaly is not None
                and hasattr(anomaly, "records")
                and anomaly.records
            ):
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

                anomaly_stars_val = (
                    f"{total_stars} (騎士 {mini_boss_stars} / 首領 {boss_stars})"
                )

                boss_rec = getattr(anomaly_record, "boss_record", None)
                if boss_rec and getattr(boss_rec, "has_data", False):
                    boss_name = getattr(anomaly_record.boss, "name", "首領")
                    anomaly_max = f"首領 {boss_name} 已擊敗"
                else:
                    cleared_minis = sum(
                        1
                        for m in getattr(anomaly_record, "mini_boss_records", [])
                        if getattr(m, "has_data", False)
                    )
                    anomaly_max = f"騎士挑戰中 ({cleared_minis}/3)"

                if (
                    hasattr(anomaly_record.season, "name")
                    and anomaly_record.season.name
                ):
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
                "shiyu_defense": (
                    data.stats.shiyu_defense_frontiers if data.stats else "未知"
                ),
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
                results.append(
                    {
                        "game": game_str,
                        "nickname": acc["nickname"],
                        "success": True,
                        "message": (
                            f"簽到成功！獲得: {reward.name} x{reward.amount}"
                            if reward
                            else "簽到成功！"
                        ),
                    }
                )
            except genshin.errors.AlreadyClaimed:
                results.append(
                    {
                        "game": game_str,
                        "nickname": acc["nickname"],
                        "success": True,
                        "message": "今日已簽到過。",
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "game": game_str,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": f"簽到失敗: {str(e)}",
                    }
                )
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
                results[int(user_id)] = [
                    {
                        "game": "all",
                        "nickname": "N/A",
                        "success": False,
                        "message": f"初始化失敗: {str(e)}",
                    }
                ]
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
