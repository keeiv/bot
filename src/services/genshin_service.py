"""米游社與 HoYoLAB 服務"""

import asyncio
import copy
import json
import os
import threading
from typing import Any, Optional

from cryptography.fernet import Fernet
from dotenv import dotenv_values
from dotenv import set_key
import genshin

from src.utils.document_store import open_document
from src.utils.document_store import read_document
from src.utils.document_store import write_document
from src.utils.i18n import current_lang
from src.utils.i18n import text as tx
from src.utils.lang_context import localized
from src.utils.storage_worker import run_storage
from src.utils.text_converter import to_traditional_chinese

_DATA_FILE = "data/storage/genshin_accounts.json"
_SIGNIN_LOG_FILE = "data/storage/genshin_signin_log.json"


class GenshinService:
    """米游社與 HoYoLAB 帳號管理、數據獲取與每日自動簽到服務"""

    def __init__(self) -> None:
        self._accounts_lock = threading.RLock()
        self._key = self._get_encryption_key()
        self._fernet = Fernet(self._key)
        self._accounts: dict[Any, Any] = self._load_accounts()

    def _get_encryption_key(self) -> bytes:
        """優先沿用既有金鑰；新金鑰必須成功保存才能啟用。"""
        env_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        )
        key_str = os.getenv("GENSHIN_ENCRYPTION_KEY")
        if key_str:
            return key_str.encode()

        # 不依賴呼叫端是否先執行 load_dotenv，也不展開其他環境變數。
        try:
            with open(env_path, encoding="utf-8") as stream:
                key_str = dotenv_values(stream=stream, interpolate=False).get(
                    "GENSHIN_ENCRYPTION_KEY"
                )
        except FileNotFoundError:
            key_str = None

        if key_str:
            # 驗證後才發布到程序環境，無效設定不能觸發自動換鑰。
            Fernet(key_str.encode())
        else:
            # 既有密文不能用新金鑰復原；讀不到資料也不能假定沒有帳號。
            try:
                with open_document(_DATA_FILE, encoding="utf-8") as stream:
                    accounts = json.load(stream)
            except FileNotFoundError:
                accounts = {}
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    tx("genshin_service.could_not_verify_existing_account_data")
                ) from exc
            if accounts != {}:
                raise RuntimeError(
                    tx("genshin_service.existing_account_data_found_but_genshin")
                )
            key_str = Fernet.generate_key().decode()
            self._write_key_to_env(env_path, key_str)

        os.environ["GENSHIN_ENCRYPTION_KEY"] = key_str
        return key_str.encode()

    def _write_key_to_env(self, env_path: str, key_str: str) -> None:
        """以暫存檔原子替換 .env；保存失敗時中止服務初始化。"""
        try:
            saved, _, _ = set_key(
                env_path, "GENSHIN_ENCRYPTION_KEY", key_str, encoding="utf-8"
            )
            if saved is not True:
                raise OSError("Key persistence was not confirmed")
        except OSError as exc:
            raise RuntimeError(
                tx("genshin_service.could_not_save_genshin_encryption_key")
            ) from exc

    def _load_accounts(self) -> dict[Any, Any]:
        try:
            accounts = read_document(_DATA_FILE)
        except FileNotFoundError:
            return {}
        if not isinstance(accounts, dict):
            raise TypeError("Account storage must be an object")
        return accounts

    def _save_accounts(self, accounts=None) -> None:
        """Persist the proposed snapshot before publishing it to readers."""
        with open_document(_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(
                self._accounts if accounts is None else accounts,
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _update_account(self, user_key, update):
        with self._accounts_lock:
            accounts = copy.deepcopy(self._accounts)
            if not update(accounts, user_key):
                return False
            self._save_accounts(accounts)
            self._accounts = accounts
            return True

    def _bind_verified_account(self, user_key, account):
        def update(accounts, key):
            accounts[key] = account
            return True

        return self._update_account(user_key, update)

    def get_last_signin_date(self) -> str:
        try:
            data = read_document(_SIGNIN_LOG_FILE)
        except FileNotFoundError:
            return ""
        if not isinstance(data, dict):
            raise TypeError("Signin storage must be an object")
        result = data.get("last_run_date", "")
        if not isinstance(result, str):
            raise TypeError("Signin date must be a string")
        return result

    def save_last_signin_date(self, date_str: str) -> None:
        try:
            data = read_document(_SIGNIN_LOG_FILE)
        except FileNotFoundError:
            data = {}
        if not isinstance(data, dict):
            raise TypeError("Signin storage must be an object")
        data["last_run_date"] = date_str
        write_document(_SIGNIN_LOG_FILE, data)

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
                tx("genshin_service.no_hoyolab_miyoushe_account_is_linked")
            )

        cookie = self.decrypt_cookie(user_data["encrypted_cookie"])
        region_str = user_data.get("region", "global")
        region = (
            genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS
        )

        client = genshin.Client(
            cookies=cookie,
            region=region,
            lang="en-us" if current_lang() == "en" else "zh-tw",
        )
        return client

    def get_bound_user(self, discord_user_id: int) -> Optional[dict[Any, Any]]:
        """獲取已綁定的使用者設定"""
        return copy.deepcopy(self._accounts.get(str(discord_user_id)))

    def get_all_bound_users(self) -> dict[Any, Any]:
        """獲取所有已綁定的使用者"""
        return copy.deepcopy(self._accounts)

    async def bind_account(
        self, discord_user_id: int, cookie: str, region_str: str
    ) -> list[dict[Any, Any]]:
        """驗證並綁定 Cookie"""
        region = (
            genshin.Region.CHINESE if region_str == "cn" else genshin.Region.OVERSEAS
        )
        client = genshin.Client(
            cookies=cookie,
            region=region,
            lang="en-us" if current_lang() == "en" else "zh-tw",
        )

        try:
            # 獲取綁定的遊戲帳號列表以驗證 Cookie
            accounts = await client.get_game_accounts()
        except genshin.errors.InvalidCookies:
            raise ValueError(tx("genshin_service.the_supplied_cookie_is_invalid_or"))
        except Exception as e:
            raise ValueError(
                tx("genshin_service.cookie_verification_failed", v0=(str(e)))
            )

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
        account = {
            "encrypted_cookie": encrypted_cookie,
            "region": region_str,
            "auto_sign_in": True,
            "game_accounts": game_accounts,
        }
        await run_storage(self._bind_verified_account, str(discord_user_id), account)
        return game_accounts

    def unbind_account(self, discord_user_id: int) -> bool:
        """解除綁定帳號"""

        def update(accounts, key):
            if key not in accounts:
                return False
            del accounts[key]
            return True

        return self._update_account(str(discord_user_id), update)

    def toggle_auto_sign_in(self, discord_user_id: int, enable: bool) -> bool:
        """開啟或關閉每日自動簽到"""

        def update(accounts, key):
            if key not in accounts:
                return False
            accounts[key]["auto_sign_in"] = enable
            return True

        return self._update_account(str(discord_user_id), update)

    # ─────────────── 業務 API ───────────────

    async def get_notes(self, discord_user_id: int, game_str: str) -> dict[Any, Any]:
        """獲取指定遊戲的實時便箋"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]

        # 尋找對應遊戲的 UID
        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self.map_game_biz_to_str(acc["game_biz"]) == game_str
        ]

        uid = int(uids[0]) if uids else None

        if uid is None:
            raise ValueError(
                tx("genshin_service.no_linked_account_was_found", v0=(game_str))
            )

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
            starrail_notes = await client.get_starrail_notes(uid)
            return {
                "type": "starrail",
                "uid": uid,
                "current_stamina": starrail_notes.current_stamina,
                "max_stamina": starrail_notes.max_stamina,
                "stamina_recovery": self._timedelta_to_seconds(
                    starrail_notes.stamina_recover_time
                ),
                "reserve_stamina": starrail_notes.current_reserve_stamina,
                "train_score": starrail_notes.current_train_score,
                "max_train_score": starrail_notes.max_train_score,
                "rogue_score": starrail_notes.current_rogue_score,
                "max_rogue_score": starrail_notes.max_rogue_score,
                "expeditions": [
                    {
                        "name": getattr(exp, "name", ""),
                        "remained": self._timedelta_to_seconds(
                            getattr(exp, "remaining_time", 0)
                        ),
                    }
                    for exp in starrail_notes.expeditions
                ],
                "max_expeditions": starrail_notes.total_expedition_num,
            }
        elif game_str == "zzz":
            zzz_notes = await client.get_zzz_notes(uid)
            # battery_charge is BatteryCharge object with (current, max, seconds_till_full)
            battery = getattr(zzz_notes, "battery_charge", None)
            video = getattr(zzz_notes, "video_store_state", None)
            video_str = tx("audit_log.unknown")
            if video:
                if video.name == "REVENUE_AVAILABLE":
                    video_str = tx("genshin_service.open_revenue_pending_collection")
                elif video.name == "CURRENTLY_OPEN":
                    video_str = tx("genshin_service.open")
                elif video.name == "WAITING_TO_OPEN":
                    video_str = tx("genshin_service.closed_waiting_to_open")

            return {
                "type": "zzz",
                "uid": uid,
                "battery": battery.current if battery else 0,
                "max_battery": battery.max if battery else 240,
                "battery_recovery": battery.seconds_till_full if battery else 0,
                "engagement": zzz_notes.engagement,
                "scratch_completed": zzz_notes.scratch_card_completed,
                "video_store": video_str,
            }
        elif game_str == "honkai":
            honkai_notes = await client.get_honkai_notes(uid)
            return {
                "type": "honkai",
                "uid": uid,
                "current_stamina": honkai_notes.current_stamina,
                "max_stamina": honkai_notes.max_stamina,
                "stamina_recovery": self._timedelta_to_seconds(
                    honkai_notes.stamina_recover_time
                ),
                "train_score": honkai_notes.current_train_score,
            }
        else:
            raise ValueError(tx("genshin_service.unsupported_game_type"))

    async def redeem_code(
        self, discord_user_id: int, game_str: str, code: str
    ) -> list[dict[Any, Any]]:
        """為使用者在此遊戲的所有繫結 UID 兌換禮包碼"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]

        # 篩選對應遊戲的 UIDs
        game_accs = [
            acc
            for acc in user_data.get("game_accounts", [])
            if self.map_game_biz_to_str(acc["game_biz"]) == game_str
        ]

        if not game_accs:
            raise ValueError(
                tx("genshin_service.no_game_account_is_linked_to", v0=(game_str))
            )

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
                        "message": tx("genshin_service.code_redeemed"),
                    }
                )
            except genshin.errors.RedemptionClaimed:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": tx(
                            "genshin_service.this_code_has_already_been_redeemed"
                        ),
                    }
                )
            except genshin.errors.RedemptionCooldown:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": tx(
                            "genshin_service.redemption_requests_are_too_frequent_retry"
                        ),
                    }
                )
            except genshin.errors.RedemptionInvalid:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": tx("genshin_service.invalid_code_or_the_code_is"),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "uid": uid,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": tx("genshin_service.error", v0=(str(e))),
                    }
                )

        return results

    async def get_stats(self, discord_user_id: int, game_str: str) -> dict[Any, Any]:
        """獲取使用者的遊戲統計數據"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]

        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self.map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        uid = int(uids[0]) if uids else None
        if not uid:
            raise ValueError(
                tx("genshin_service.no_linked_account_was_found", v0=(game_str))
            )

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
            starrail_data = await client.get_starrail_user(uid)
            return {
                "nickname": starrail_data.info.nickname,
                "level": starrail_data.info.level,
                "days_active": starrail_data.stats.active_days,
                "achievements": starrail_data.stats.achievement_num,
                "characters": starrail_data.stats.avatar_num,
                "chests_opened": starrail_data.stats.chest_num,
            }
        elif game_str == "zzz":
            zzz_data = await client.get_zzz_user(uid)
            acc_info = next(
                (
                    acc
                    for acc in user_data.get("game_accounts", [])
                    if acc["uid"] == uid
                ),
                None,
            )
            nickname = acc_info["nickname"] if acc_info else tx("audit_log.unknown")
            level = acc_info["level"] if acc_info else 0
            return {
                "nickname": nickname,
                "level": level,
                "days_active": zzz_data.stats.active_days,
                "achievements": zzz_data.stats.achievement_count,
                "characters": zzz_data.stats.character_num,
                "bangboo_obtained": zzz_data.stats.bangboo_obtained,
            }
        elif game_str == "honkai":
            honkai_data = await client.get_honkai_user(uid)
            return {
                "nickname": honkai_data.info.nickname,
                "level": honkai_data.info.level,
                "days_active": honkai_data.stats.active_days,
                "characters": honkai_data.stats.battlesuits,
            }
        else:
            raise ValueError(tx("genshin_service.unsupported_game_type_fdbb37"))

    async def get_abyss_stats(
        self, discord_user_id: int, game_str: str
    ) -> dict[Any, Any]:
        """獲取深淵數據 (當前期數)"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]

        uids = [
            acc["uid"]
            for acc in user_data.get("game_accounts", [])
            if self.map_game_biz_to_str(acc["game_biz"]) == game_str
        ]
        uid = int(uids[0]) if uids else None
        if not uid:
            raise ValueError(
                tx("genshin_service.no_linked_account_was_found", v0=(game_str))
            )

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
                if not isinstance(challenge, BaseException)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                else 0
            )
            moc_max = (
                challenge.max_floor
                if not isinstance(challenge, BaseException)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                and challenge.max_floor
                else tx("genshin_service.no_data")
            )
            moc_name = (
                challenge.name
                if not isinstance(challenge, BaseException)
                and challenge is not None
                and getattr(challenge, "has_data", False)
                else tx("genshin_service.memory_of_chaos")
            )

            pf_stars = (
                pf.total_stars
                if not isinstance(pf, BaseException)
                and pf is not None
                and getattr(pf, "has_data", False)
                else 0
            )
            pf_max = (
                pf.max_floor
                if not isinstance(pf, BaseException)
                and pf is not None
                and getattr(pf, "has_data", False)
                and pf.max_floor
                else tx("genshin_service.no_data")
            )
            pf_name = (
                pf.name
                if not isinstance(pf, BaseException)
                and pf is not None
                and getattr(pf, "has_data", False)
                else tx("genshin_service.pure_fiction")
            )

            shadow_stars = (
                shadow.total_stars
                if not isinstance(shadow, BaseException)
                and shadow is not None
                and getattr(shadow, "has_data", False)
                else 0
            )
            shadow_max = (
                shadow.max_floor
                if not isinstance(shadow, BaseException)
                and shadow is not None
                and getattr(shadow, "has_data", False)
                and shadow.max_floor
                else tx("genshin_service.no_data")
            )

            shadow_name = tx("genshin_service.apocalyptic_shadow")
            if (
                not isinstance(shadow, BaseException)
                and shadow is not None
                and getattr(shadow, "has_data", False)
            ):
                if hasattr(shadow, "seasons") and shadow.seasons:
                    shadow_name = shadow.seasons[0].name

            # Anomaly Arbitration (異相仲裁)
            anomaly_stars_val: int | str = 0
            anomaly_max = tx("genshin_service.no_data")
            anomaly_name = tx("genshin_service.anomaly_arbitration")

            anomaly_record = None
            if (
                not isinstance(anomaly, BaseException)
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

                anomaly_stars_val = tx(
                    "genshin_service.knight_boss",
                    v0=(total_stars),
                    v1=(mini_boss_stars),
                    v2=(boss_stars),
                )

                boss_rec = getattr(anomaly_record, "boss_record", None)
                if boss_rec and getattr(boss_rec, "has_data", False):
                    boss_name = getattr(
                        anomaly_record.boss, "name", tx("genshin_service.boss")
                    )
                    anomaly_max = tx("genshin_service.boss_defeated", v0=(boss_name))
                else:
                    cleared_minis = sum(
                        1
                        for m in getattr(anomaly_record, "mini_boss_records", [])
                        if getattr(m, "has_data", False)
                    )
                    anomaly_max = tx(
                        "genshin_service.knight_challenge_in_progress_3",
                        v0=(cleared_minis),
                    )

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
            zzz_data = await client.get_zzz_user(uid)
            return {
                "shiyu_defense": (
                    zzz_data.stats.shiyu_defense_frontiers
                    if zzz_data.stats
                    else tx("audit_log.unknown")
                ),
            }
        else:
            raise ValueError(tx("genshin_service.this_game_is_unsupported_or_abyss"))

    async def claim_daily_signin_for_user(
        self, discord_user_id: int
    ) -> list[dict[Any, Any]]:
        """手動或定時為單個使用者擁有的所有遊戲帳號簽到"""
        client = self.get_client(discord_user_id)
        user_data = self._accounts[str(discord_user_id)]
        results = []

        completed_games = set()

        for acc in user_data.get("game_accounts", []):
            game_str = self.map_game_biz_to_str(acc["game_biz"])
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
                            tx(
                                "genshin_service.check_in_successful_reward",
                                v0=(reward.name),
                                v1=(reward.amount),
                            )
                            if reward
                            else tx("genshin_service.check_in_successful")
                        ),
                    }
                )
            except genshin.errors.AlreadyClaimed:
                results.append(
                    {
                        "game": game_str,
                        "nickname": acc["nickname"],
                        "success": True,
                        "message": tx("genshin_service.already_checked_in_today"),
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "game": game_str,
                        "nickname": acc["nickname"],
                        "success": False,
                        "message": tx("genshin_service.check_in_failed", v0=(str(e))),
                    }
                )
            completed_games.add(game_str)

        return results

    async def run_global_auto_sign_in(self) -> dict[int, list[dict[Any, Any]]]:
        """定時背景任務：為所有啟用自動簽到的使用者執行簽到"""
        results = {}
        for user_id, info in self._accounts.items():
            if not info.get("auto_sign_in", True):
                continue
            results[int(user_id)] = await self._background_sign_in(int(user_id))
            await asyncio.sleep(10)
        return results

    @localized("user_id")
    async def _background_sign_in(self, user_id: int) -> list[dict[Any, Any]]:
        try:
            user_results = await self.claim_daily_signin_for_user(int(user_id))
            return user_results
        except Exception as e:
            return [
                {
                    "game": "all",
                    "nickname": "N/A",
                    "success": False,
                    "message": tx("genshin_service.initialization_failed", v0=(str(e))),
                }
            ]

    # ─────────────── 輔助工具 ───────────────

    def map_game_biz_to_str(self, game_biz: str) -> str:
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
            return tx("genshin_service.ready")

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
            return tx("genshin_service.ready")

        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        minutes = (seconds % 3600) // 60

        parts = []
        if days > 0:
            parts.append(tx("genshin_service.d", v0=(days)))
        if hours > 0:
            parts.append(tx("genshin_service.h", v0=(hours)))
        if minutes > 0:
            parts.append(tx("genshin_service.m", v0=(minutes)))

        return "".join(parts) + tx("genshin_service.until_ready")

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
