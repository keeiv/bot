"""Real InnoDB transactions, restricted to a separately provisioned test database."""

from concurrent.futures import ThreadPoolExecutor
import os
import uuid

import pytest

from src.config.constants import DEVELOPER_IDS
from src.services.tool_quota import ToolQuota


@pytest.mark.skipif(
    os.getenv("MYSQL_INTEGRATION_TEST") != "1",
    reason="Requires isolated MySQL test database",
)
def test_mysql_quota_reservation_and_coupon_transactions(monkeypatch):
    database = os.environ.get("MYSQL_TEST_DATABASE", "")
    assert database.endswith("_test"), "Never run against production"
    monkeypatch.setenv("MYSQL_DATABASE", database)
    monkeypatch.setenv("STORAGE_BACKEND", "mysql")
    quota = ToolQuota()
    uid = str(uuid.uuid4().int % 10**18)
    quote = quota.quote(uid, [100], "png")

    def reserve():
        try:
            return quota.reserve(uid, quote)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda _: reserve(), range(2)))
    assert sum(job is not None for job in jobs) == 1
    job = next(job for job in jobs if job)
    charge = quota.finish(uid, job, 0.1, True)
    assert quota.finish(uid, job, 0.1, True) == charge
    assert quota.snapshot(uid)["weekly"]["used"] == charge
    quota.admin(next(iter(DEVELOPER_IDS)), "issue", uuid.uuid4().hex, [uid])
    coupon = quota.inventory(uid)["items"][0]["id"]
    quota.redeem(uid, coupon)
    assert quota.snapshot(uid)["weekly"]["used"] == 0
    assert quota.inventory(uid, used=True)["total"] == 1
    developer = str(next(iter(DEVELOPER_IDS)))
    assert quota.snapshot(developer)["tier"]["name"] == "Nova 20x."
    assert quota.set_test_tier(developer, "Ultra.")["tier"]["name"] == "Ultra."
    assert ToolQuota().snapshot(developer)["testTierExpiresAt"] is not None
    assert quota.set_test_tier(developer, "auto")["testTierExpiresAt"] is None
    assert (
        quota.set_nova(developer, uid, event_id=uuid.uuid4().hex)["tier"]["name"]
        == "Nova 20x."
    )
    assert ToolQuota().snapshot(uid)["tier"]["name"] == "Nova 20x."
    assert quota.set_nova(developer, uid, False)["tier"]["name"] == "Free."
    assert quota.inventory(uid, used=True)["total"] == 1
