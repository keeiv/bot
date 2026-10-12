"""Transactional quotas shared by Discord and the web file tools."""

from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import math
from pathlib import Path
import sqlite3
import time
import uuid

from src.services.tool_protocol import FORMATS
from src.services.tool_protocol import MAX_TOTAL_BYTES
from src.utils.document_store import read_document
from src.utils.document_store import using_mysql
from src.utils.i18n import text as tx
from src.utils.mysql_compat import MySQLConnection

MIB = 1024 * 1024
TAIPEI = timezone(timedelta(hours=8))
TIERS = (
    {
        "name": "Free.",
        "days": 0,
        "weekly": 60,
        "rolling": 12,
        "batch": 1,
        "max_mb": 2,
        "seconds": 4,
        "color": "#94a3b8",
    },
    {
        "name": "Run.",
        "days": 30,
        "weekly": 500,
        "rolling": 80,
        "batch": 1,
        "max_mb": 8,
        "seconds": 15,
        "color": "#38bdf8",
    },
    {
        "name": "Dash.",
        "days": 60,
        "weekly": 1500,
        "rolling": 200,
        "batch": 3,
        "max_mb": 16,
        "seconds": 30,
        "color": "#34d399",
    },
    {
        "name": "Grow.",
        "days": 120,
        "weekly": 4000,
        "rolling": 500,
        "batch": 8,
        "max_mb": 32,
        "seconds": 45,
        "color": "#a78bfa",
    },
    {
        "name": "Ultra.",
        "days": 180,
        "weekly": 10000,
        "rolling": 1200,
        "batch": 16,
        "max_mb": 64,
        "seconds": 60,
        "color": "#fbbf24",
    },
)
# Private entitlement: deliberately excluded from the public progression list.
NOVA_TIER = {
    **TIERS[-1],
    "name": "Nova 20x.",
    "days": 0,
    "weekly": TIERS[-1]["weekly"] * 20,
    "rolling": TIERS[-1]["rolling"] * 20,
    "color": "#67e8f9",
    "hidden": True,
}
RESERVATION_SECONDS = 300


def valid_id(value):
    value = str(value)
    if (
        not value.isascii()
        or not value.isdecimal()
        or not 1 <= len(value) <= 20
        or int(value) == 0
    ):
        raise ValueError(tx("tool_quota.invalid_discord_id"))
    return value


def job_seconds(count):
    return min(60, 15 + count * 5)


def points(size, seconds):
    return max(1, math.ceil(size / MIB + max(0, seconds) * 2))


def week_start(now):
    local = datetime.fromtimestamp(now, TAIPEI)
    return (
        (local - timedelta(days=local.weekday()))
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .timestamp()
    )


class ToolQuota:
    def __init__(self, path="data/storage/tool_quota.sqlite3", clock=time.time):
        self.path = Path(path)
        self.clock = clock
        self.mysql = using_mysql()
        statements = [
            "CREATE TABLE IF NOT EXISTS tool_guard (id INTEGER PRIMARY KEY)",
            "CREATE TABLE IF NOT EXISTS tool_tier_overrides (user_id VARCHAR(20) PRIMARY KEY, tier VARCHAR(16) NOT NULL, expires_at DOUBLE NOT NULL)",
            "CREATE TABLE IF NOT EXISTS tool_tier_grants (user_id VARCHAR(20) PRIMARY KEY, granted_by VARCHAR(20) NOT NULL, granted_at DOUBLE NOT NULL)",
            "CREATE TABLE IF NOT EXISTS tool_users (user_id VARCHAR(20) PRIMARY KEY, first_seen DOUBLE NOT NULL, epoch INTEGER NOT NULL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS tool_jobs (job_id VARCHAR(64) PRIMARY KEY, user_id VARCHAR(20) NOT NULL, epoch INTEGER NOT NULL, created_at DOUBLE NOT NULL, finished_at DOUBLE, expires_at DOUBLE NOT NULL, state VARCHAR(16) NOT NULL, reserved INTEGER NOT NULL, charged INTEGER NOT NULL DEFAULT 0, input_bytes BIGINT NOT NULL, seconds DOUBLE NOT NULL DEFAULT 0)",
            "CREATE TABLE IF NOT EXISTS tool_coupons (coupon_id VARCHAR(128) PRIMARY KEY, user_id VARCHAR(20) NOT NULL, issued_at DOUBLE NOT NULL, used_at DOUBLE)",
            "CREATE TABLE IF NOT EXISTS tool_actions (action_id VARCHAR(64) PRIMARY KEY, actor_id VARCHAR(20) NOT NULL, action VARCHAR(32) NOT NULL, target VARCHAR(32) NOT NULL, created_at DOUBLE NOT NULL, affected INTEGER NOT NULL)",
        ]
        with self.connection() as db:
            for sql in statements:
                db.execute(sql + (" ENGINE=InnoDB" if self.mysql else ""))
            ignore = "INSERT IGNORE" if self.mysql else "INSERT OR IGNORE"
            db.execute(f"{ignore} INTO tool_guard(id) VALUES (1)")
            # Index definitions are portable and checked before creation.
            for table, name, columns in (
                ("tool_jobs", "tool_jobs_user_time", "user_id, finished_at"),
                ("tool_coupons", "tool_coupons_owner", "user_id, issued_at"),
            ):
                if self.mysql:
                    present = db.execute(
                        "SELECT 1 FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name=? AND index_name=?",
                        (table, name),
                    ).fetchone()
                else:
                    present = db.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",
                        (name,),
                    ).fetchone()
                if not present:
                    db.execute(f"CREATE INDEX {name} ON {table} ({columns})")

    @contextmanager
    def connection(self, locked=False):
        if self.mysql:
            db = MySQLConnection()
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(self.path, timeout=10)
        try:
            if locked:
                if self.mysql:
                    db.execute(
                        "SELECT id FROM tool_guard WHERE id=1 FOR UPDATE"
                    ).fetchone()
                else:
                    db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _user(self, db, user_id, first_seen=None):
        uid = valid_id(user_id)
        now = self.clock()
        ignore = "INSERT IGNORE" if self.mysql else "INSERT OR IGNORE"
        db.execute(
            f"{ignore} INTO tool_users(user_id,first_seen,epoch) VALUES (?,?,0)",
            (uid, min(now, first_seen) if first_seen is not None else now),
        )
        if first_seen is not None:
            db.execute(
                "UPDATE tool_users SET first_seen=? WHERE user_id=? AND first_seen>?",
                (min(now, first_seen), uid, min(now, first_seen)),
            )
        return db.execute(
            "SELECT user_id,first_seen,epoch FROM tool_users WHERE user_id=?", (uid,)
        ).fetchone()

    def register(self, user_id):
        with self.connection(locked=True) as db:
            self._user(db, user_id)

    def import_history(self):
        """Seed age from existing achievement timestamps, never account creation age."""
        try:
            history = read_document("data/storage/achievements.json")
        except FileNotFoundError:
            return
        if not isinstance(history, dict):
            return
        with self.connection(locked=True) as db:
            for uid, guilds in history.items():
                if not str(uid).isdecimal() or not isinstance(guilds, dict):
                    continue
                dates = []
                for record in guilds.values():
                    if not isinstance(record, dict):
                        continue
                    for key, value in record.items():
                        if str(key).startswith("unlocked_at_") and isinstance(
                            value, str
                        ):
                            try:
                                parsed = datetime.fromisoformat(value)
                                if parsed.tzinfo is not None:
                                    dates.append(parsed.timestamp())
                            except ValueError:
                                continue
                if dates:
                    self._user(db, uid, min(dates))

    def _snapshot(self, db, user):
        uid, first_seen, epoch = user
        now = self.clock()
        days = max(0, int((now - first_seen) // 86400))
        tier = next((dict(t) for t in reversed(TIERS) if days >= t["days"]), None)
        from src.config.constants import DEVELOPER_IDS

        private_tier = (
            int(uid) in DEVELOPER_IDS
            or db.execute(
                "SELECT 1 FROM tool_tier_grants WHERE user_id=?", (uid,)
            ).fetchone()
        )
        if private_tier:
            tier = dict(NOVA_TIER)
        natural_tier = dict(tier)
        override = None
        if int(uid) in DEVELOPER_IDS:
            override = db.execute(
                "SELECT tier,expires_at FROM tool_tier_overrides WHERE user_id=? AND expires_at>?",
                (uid, now),
            ).fetchone()
            if override:
                tier = next((dict(t) for t in TIERS if t["name"] == override[0]), tier)
        next_tier = (
            None if private_tier else next((t for t in TIERS if days < t["days"]), None)
        )
        start = week_start(now)
        rows = db.execute(
            "SELECT finished_at,charged FROM tool_jobs WHERE user_id=? AND epoch=? AND state='done' AND finished_at>=? ORDER BY finished_at",
            (uid, epoch, min(start, now - 10800)),
        ).fetchall()
        weekly = sum(cost for at, cost in rows if at >= start)
        rolling = sum(cost for at, cost in rows if at > now - 10800)
        pending = db.execute(
            "SELECT COALESCE(SUM(reserved),0) FROM tool_jobs WHERE user_id=? AND state='pending' AND expires_at>?",
            (uid, now),
        ).fetchone()[0]
        coupons = db.execute(
            "SELECT COUNT(*) FROM tool_coupons WHERE user_id=? AND used_at IS NULL",
            (uid,),
        ).fetchone()[0]
        return {
            "userId": uid,
            "days": days,
            "firstSeen": first_seen,
            "tier": tier,
            "naturalTier": natural_tier,
            "testTierExpiresAt": override[1] if override else None,
            "nextTier": dict(next_tier) if next_tier else None,
            "nextUnlockAt": (
                first_seen + next_tier["days"] * 86400 if next_tier else None
            ),
            "weekly": {
                "used": weekly,
                "limit": tier["weekly"] if tier else 0,
                "resetAt": start + 604800,
            },
            "rolling": {
                "used": rolling,
                "limit": tier["rolling"] if tier else 0,
                "nextRestoreAt": next(
                    (at + 10800 for at, cost in rows if cost and at > now - 10800), None
                ),
            },
            "reserved": int(pending),
            "coupons": coupons,
            "tiers": [dict(t) for t in TIERS],
            "formats": list(FORMATS),
            "pricing": tx("tool_quota.points_ceil_input_mib_processing_seconds"),
        }

    def snapshot(self, user_id):
        with self.connection(locked=True) as db:
            return self._snapshot(db, self._user(db, user_id))

    def quote(self, user_id, sizes, operation):
        if (
            operation not in FORMATS
            or not sizes
            or any(type(s) is not int or s <= 0 for s in sizes)
        ):
            raise ValueError(tx("tool_quota.invalid_files_or_output_format"))
        with self.connection(locked=True) as db:
            data = self._snapshot(db, self._user(db, user_id))
            tier = data["tier"]
            if len(sizes) > tier["batch"]:
                raise ValueError(tx("tool_quota.the_batch_exceeds_this_tier_s"))
            if max(sizes) > tier["max_mb"] * MIB or sum(sizes) > MAX_TOTAL_BYTES:
                raise ValueError(tx("tool_quota.the_file_exceeds_the_current_size"))
            timeout = min(tier["seconds"], job_seconds(len(sizes)))
            ceiling = points(sum(sizes), timeout)
            if any(
                data[period]["used"] + data["reserved"] + ceiling
                > data[period]["limit"]
                for period in ("weekly", "rolling")
            ):
                raise ValueError(
                    tx("tool_quota.insufficient_allowance_to_reserve_the_maximum")
                )
            return {
                "maximumPoints": ceiling,
                "inputBytes": sum(sizes),
                "timeout": timeout,
                "count": len(sizes),
                "operation": operation,
                "tierName": tier["name"],
            }

    def reserve(self, user_id, quote, job_id=None):
        job_id = job_id or uuid.uuid4().hex
        with self.connection(locked=True) as db:
            user = self._user(db, user_id)
            data = self._snapshot(db, user)
            if data["tier"]["name"] != quote["tierName"]:
                raise ValueError(tx("tool_quota.the_tier_has_changed_request_a"))
            if db.execute(
                "SELECT 1 FROM tool_jobs WHERE job_id=?", (job_id,)
            ).fetchone():
                raise ValueError(
                    tx("tool_quota.this_processing_request_has_already_been")
                )
            if db.execute(
                "SELECT 1 FROM tool_jobs WHERE user_id=? AND state='pending' AND expires_at>?",
                (user[0], self.clock()),
            ).fetchone():
                raise ValueError(tx("tool_quota.a_file_job_is_already_in"))
            cost = quote["maximumPoints"]
            if any(
                data[period]["used"] + data["reserved"] + cost > data[period]["limit"]
                for period in ("weekly", "rolling")
            ):
                raise ValueError(
                    tx("tool_quota.insufficient_allowance_to_reserve_the_maximum")
                )
            db.execute(
                "INSERT INTO tool_jobs(job_id,user_id,epoch,created_at,expires_at,state,reserved,input_bytes) VALUES (?,?,?,?,?,'pending',?,?)",
                (
                    job_id,
                    user[0],
                    user[2],
                    self.clock(),
                    self.clock() + RESERVATION_SECONDS,
                    cost,
                    quote["inputBytes"],
                ),
            )
        return job_id

    def finish(self, user_id, job_id, seconds=0, success=False, changed=True):
        with self.connection(locked=True) as db:
            user = self._user(db, user_id)
            row = db.execute(
                "SELECT state,reserved,input_bytes,charged,expires_at FROM tool_jobs WHERE job_id=? AND user_id=?",
                (job_id, user[0]),
            ).fetchone()
            if row is None:
                raise ValueError(tx("tool_quota.processing_record_not_found"))
            if row[0] != "pending":
                return row[3]
            success = success and row[4] > self.clock()
            charge = min(row[1], points(row[2], seconds)) if success and changed else 0
            db.execute(
                "UPDATE tool_jobs SET state=?,charged=?,seconds=?,finished_at=?,epoch=? WHERE job_id=?",
                (
                    "done" if success else "failed",
                    charge,
                    max(0, seconds),
                    self.clock(),
                    user[2],
                    job_id,
                ),
            )
            return charge

    def inventory(self, user_id, used=False, page=0):
        uid = valid_id(user_id)
        page = max(0, min(100000, int(page)))
        with self.connection(locked=True) as db:
            self._user(db, uid)
            count = db.execute(
                "SELECT COUNT(*) FROM tool_coupons WHERE user_id=? AND (used_at IS NOT NULL)=?",
                (uid, int(used)),
            ).fetchone()[0]
            rows = db.execute(
                "SELECT coupon_id,issued_at,used_at FROM tool_coupons WHERE user_id=? AND (used_at IS NOT NULL)=? ORDER BY issued_at DESC,coupon_id LIMIT 10 OFFSET ?",
                (uid, int(used), page * 10),
            ).fetchall()
            return {
                "total": count,
                "page": page,
                "items": [{"id": r[0], "issuedAt": r[1], "usedAt": r[2]} for r in rows],
            }

    def redeem(self, user_id, coupon_id):
        with self.connection(locked=True) as db:
            user = self._user(db, user_id)
            coupon = db.execute(
                "SELECT used_at FROM tool_coupons WHERE coupon_id=? AND user_id=?",
                (coupon_id, user[0]),
            ).fetchone()
            if coupon is None or coupon[0] is not None:
                raise ValueError(tx("tool_quota.the_reset_voucher_does_not_exist"))
            state = self._snapshot(db, user)
            if state["weekly"]["used"] == 0 and state["rolling"]["used"] == 0:
                raise ValueError(tx("tool_quota.there_is_no_recorded_usage_to"))
            db.execute(
                "UPDATE tool_coupons SET used_at=? WHERE coupon_id=?",
                (self.clock(), coupon_id),
            )
            db.execute(
                "UPDATE tool_users SET epoch=epoch+1 WHERE user_id=?", (user[0],)
            )
        return self.snapshot(user_id)

    def admin(self, actor_id, action, event_id, user_ids=None, target="all"):
        """Authorization is checked here as well as at the Discord boundary."""
        from src.config.constants import DEVELOPER_IDS

        if int(valid_id(actor_id)) not in DEVELOPER_IDS:
            raise PermissionError(tx("file_tools.developers_only"))
        if action not in ("reset", "issue"):
            raise ValueError(tx("tool_quota.unknown_administration_operation"))
        with self.connection(locked=True) as db:
            prior = db.execute(
                "SELECT affected FROM tool_actions WHERE action_id=?", (str(event_id),)
            ).fetchone()
            if prior:
                return prior[0]
            if user_ids is None:
                ids = [
                    r[0]
                    for r in db.execute("SELECT user_id FROM tool_users").fetchall()
                ]
            else:
                ids = sorted({valid_id(uid) for uid in user_ids})
            for uid in ids:
                self._user(db, uid)
                if action == "reset":
                    db.execute(
                        "UPDATE tool_users SET epoch=epoch+1 WHERE user_id=?", (uid,)
                    )
                else:
                    db.execute(
                        "INSERT INTO tool_coupons(coupon_id,user_id,issued_at) VALUES (?,?,?)",
                        (f"{event_id}-{uid}", uid, self.clock()),
                    )
            db.execute(
                "INSERT INTO tool_actions(action_id,actor_id,action,target,created_at,affected) VALUES (?,?,?,?,?,?)",
                (
                    str(event_id),
                    str(actor_id),
                    action,
                    str(target),
                    self.clock(),
                    len(ids),
                ),
            )
            return len(ids)

    def registered_ids(self):
        with self.connection() as db:
            return [
                r[0] for r in db.execute("SELECT user_id FROM tool_users").fetchall()
            ]

    def set_nova(self, actor_id, user_id, enabled=True, event_id=None):
        """Grant one private tier, without granting any developer permissions."""
        from src.config.constants import DEVELOPER_IDS

        actor, uid = valid_id(actor_id), valid_id(user_id)
        if int(actor) not in DEVELOPER_IDS:
            raise PermissionError(tx("tool_quota.only_developers_can_grant_or_revoke"))
        if not isinstance(enabled, bool):
            raise ValueError(tx("tool_quota.invalid_authorization_operation"))
        if int(uid) in DEVELOPER_IDS:
            raise ValueError(tx("tool_quota.developers_receive_nova_20x_by_default"))
        event = str(event_id) if event_id is not None else uuid.uuid4().hex
        if not 1 <= len(event) <= 64:
            raise ValueError(tx("tool_quota.invalid_operation_id"))
        action = "nova_grant" if enabled else "nova_revoke"
        with self.connection(locked=True) as db:
            prior = db.execute(
                "SELECT actor_id,action,target FROM tool_actions WHERE action_id=?",
                (event,),
            ).fetchone()
            if prior and tuple(prior) != (actor, action, uid):
                raise ValueError(tx("tool_quota.this_operation_id_was_used_for"))
            if not prior:
                self._user(db, uid)
                db.execute("DELETE FROM tool_tier_grants WHERE user_id=?", (uid,))
                if enabled:
                    db.execute(
                        "INSERT INTO tool_tier_grants(user_id,granted_by,granted_at) VALUES (?,?,?)",
                        (uid, actor, self.clock()),
                    )
                db.execute(
                    "INSERT INTO tool_actions(action_id,actor_id,action,target,created_at,affected) VALUES (?,?,?,?,?,?)",
                    (event, actor, action, uid, self.clock(), 1),
                )
        return self.snapshot(uid)

    def set_test_tier(self, actor_id, tier_name):
        """Local developer console only; overrides never alter tenure or usage."""
        from src.config.constants import DEVELOPER_IDS

        uid = valid_id(actor_id)
        if int(uid) not in DEVELOPER_IDS:
            raise PermissionError(tx("tool_quota.only_developer_accounts_can_use_test"))
        normalized = str(tier_name).lower().rstrip(".")
        tier = next(
            (t for t in TIERS if t["name"].lower().rstrip(".") == normalized), None
        )
        restore = normalized in {"auto", "nova", "nova 20x"}
        if tier is None and not restore:
            raise ValueError(tx("tool_quota.tier_free_run_dash_grow_ultra"))
        with self.connection(locked=True) as db:
            self._user(db, uid)
            db.execute("DELETE FROM tool_tier_overrides WHERE user_id=?", (uid,))
            if tier:
                db.execute(
                    "INSERT INTO tool_tier_overrides(user_id,tier,expires_at) VALUES (?,?,?)",
                    (uid, tier["name"], self.clock() + 86400),
                )
            db.execute(
                "INSERT INTO tool_actions(action_id,actor_id,action,target,created_at,affected) VALUES (?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    uid,
                    "test_tier",
                    tier["name"] if tier else "auto",
                    self.clock(),
                    1,
                ),
            )
        return self.snapshot(uid)

    def jobs(self, user_id):
        with self.connection() as db:
            rows = db.execute(
                "SELECT job_id,state,created_at,finished_at,charged,input_bytes,seconds,expires_at FROM tool_jobs WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
                (valid_id(user_id),),
            ).fetchall()
        return [
            {
                "id": r[0],
                "state": (
                    "failed" if r[1] == "pending" and r[7] <= self.clock() else r[1]
                ),
                "createdAt": r[2],
                "finishedAt": r[3],
                "points": r[4],
                "inputBytes": r[5],
                "seconds": r[6],
            }
            for r in rows
        ]
