import asyncio
from datetime import datetime
from datetime import timedelta
from datetime import timezone
import json
import time
from typing import Any, Dict, List, Optional

import aiohttp


class GitHubRateLimitManager:
    def __init__(self):
        self.rate_limits: Dict[str, Dict] = {}
        self.request_queue: List[Dict] = {}
        self.max_retries = 3
        self.base_delay = 1.0
        self.max_delay = 60.0

    def parse_rate_limit_headers(self, headers: Dict) -> Dict:
        return {
            "remaining": int(headers.get("X-RateLimit-Remaining", 5000)),
            "reset_time": int(headers.get("X-RateLimit-Reset", time.time() + 3600)),
            "reset_after": int(headers.get("X-RateLimit-Reset-After", 3600)),
            "used": int(headers.get("X-RateLimit-Used", 0)),
        }

    async def wait_for_rate_limit(self, endpoint: str, headers: Dict) -> None:
        rate_info = self.parse_rate_limit_headers(headers)
        self.rate_limits[endpoint] = rate_info

        if rate_info["remaining"] <= 1:
            current_time = time.time()
            wait_time = max(0, rate_info["reset_time"] - current_time)

            if wait_time > 0:
                print(
                    f"[GitHub] Rate limit reached for {endpoint}, waiting {wait_time:.1f}s"
                )
                await asyncio.sleep(wait_time)

    def get_retry_delay(self, attempt: int) -> float:
        return min(self.base_delay * (2**attempt), self.max_delay)

    def should_retry(self, status_code: int) -> bool:
        return status_code in [403, 429, 500, 502, 503, 504]


class GitHubAPIManager:
    def __init__(self, token: str = None):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_manager = GitHubRateLimitManager()
        self.base_url = "https://api.github.com"
        self.user_agent = "Discord-Bot/1.0"
        self.timeout = aiohttp.ClientTimeout(total=30, connect=10)

    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            if self.token:
                headers["Authorization"] = f"token {self.token}"

            self.session = aiohttp.ClientSession(headers=headers, timeout=self.timeout)

        return self.session

    async def make_request(self, method: str, endpoint: str, **kwargs) -> Dict:
        session = await self.get_session()
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.rate_manager.max_retries):
            try:
                async with session.request(method, url, **kwargs) as response:
                    await self.rate_manager.wait_for_rate_limit(
                        endpoint, response.headers
                    )

                    if response.status == 200:
                        return await response.json()
                    elif response.status == 404:
                        raise Exception(f"Resource not found: {endpoint}")
                    elif self.rate_manager.should_retry(response.status):
                        delay = self.rate_manager.get_retry_delay(attempt)
                        print(
                            f"[GitHub] {response.status} error, retry {attempt + 1}/{self.rate_manager.max_retries} in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        error_text = await response.text()
                        raise Exception(
                            f"GitHub API error {response.status}: {error_text}"
                        )

            except asyncio.TimeoutError:
                delay = self.rate_manager.get_retry_delay(attempt)
                print(
                    f"[GitHub] Timeout error, retry {attempt + 1}/{self.rate_manager.max_retries} in {delay}s"
                )
                await asyncio.sleep(delay)
                continue
            except aiohttp.ClientError as e:
                delay = self.rate_manager.get_retry_delay(attempt)
                print(
                    f"[GitHub] Connection error, retry {attempt + 1}/{self.rate_manager.max_retries} in {delay}s: {e}"
                )
                await asyncio.sleep(delay)
                continue
            except Exception as e:
                if attempt == self.rate_manager.max_retries - 1:
                    raise e
                delay = self.rate_manager.get_retry_delay(attempt)
                print(
                    f"[GitHub] Unexpected error, retry {attempt + 1}/{self.rate_manager.max_retries} in {delay}s: {e}"
                )
                await asyncio.sleep(delay)
                continue

        raise Exception(f"Max retries exceeded for {endpoint}")

    async def get_commits(self, owner: str, repo: str, per_page: int = 1) -> List[Dict]:
        params = {"per_page": per_page}
        return await self.make_request(
            "GET", f"/repos/{owner}/{repo}/commits", params=params
        )

    async def get_pull_requests(
        self, owner: str, repo: str, per_page: int = 1
    ) -> List[Dict]:
        params = {"per_page": per_page, "state": "all"}
        return await self.make_request(
            "GET", f"/repos/{owner}/{repo}/pulls", params=params
        )

    async def get_repo_info(self, owner: str, repo: str) -> Dict:
        return await self.make_request("GET", f"/repos/{owner}/{repo}")

    async def get_rate_limit_status(self) -> Dict:
        return await self.make_request("GET", "/rate_limit")

    def get_rate_limit_info(self, endpoint: str) -> Optional[Dict]:
        return self.rate_manager.rate_limits.get(endpoint)

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


class GitHubRequestQueue:
    def __init__(self, api_manager: GitHubAPIManager):
        self.api_manager = api_manager
        self.queue: List[Dict] = []
        self.processing = False
        self.batch_size = 5
        self.batch_delay = 2.0

    def add_request(self, request_type: str, **kwargs):
        self.queue.append(
            {
                "type": request_type,
                "kwargs": kwargs,
                "timestamp": time.time(),
                "attempts": 0,
            }
        )

    async def process_queue(self):
        if self.processing or not self.queue:
            return

        self.processing = True

        try:
            batch = self.queue[: self.batch_size]
            self.queue = self.queue[self.batch_size :]

            tasks = []
            for request in batch:
                if request["type"] == "commits":
                    task = self.api_manager.get_commits(
                        request["kwargs"]["owner"], request["kwargs"]["repo"]
                    )
                elif request["type"] == "pulls":
                    task = self.api_manager.get_pull_requests(
                        request["kwargs"]["owner"], request["kwargs"]["repo"]
                    )
                elif request["type"] == "repo_info":
                    task = self.api_manager.get_repo_info(
                        request["kwargs"]["owner"], request["kwargs"]["repo"]
                    )
                else:
                    continue

                tasks.append(task)

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        print(f"[GitHub Queue] Request failed: {result}")
                        batch[i]["attempts"] += 1
                        if batch[i]["attempts"] < 3:
                            self.queue.append(batch[i])

        finally:
            self.processing = False

        if self.queue:
            await asyncio.sleep(self.batch_delay)
            asyncio.create_task(self.process_queue())


class GitHubDiagnostics:
    def __init__(self, api_manager: GitHubAPIManager):
        self.api_manager = api_manager

    async def run_diagnostics(self) -> Dict:
        results = {
            "api_status": "unknown",
            "rate_limit": "unknown",
            "token_valid": False,
            "connectivity": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        try:
            rate_limit = await self.api_manager.get_rate_limit_status()
            results["rate_limit"] = "ok"
            results["token_valid"] = True
            results["api_status"] = "operational"
        except Exception as e:
            results["api_status"] = f"error: {str(e)}"
            if "401" in str(e):
                results["token_valid"] = False
            elif "403" in str(e):
                results["rate_limit"] = "limited"

        try:
            await self.api_manager.get_repo_info("octocat", "Hello-World")
            results["connectivity"] = True
        except Exception as e:
            results["connectivity"] = False
            results["connection_error"] = str(e)

        return results

    async def test_specific_repo(self, owner: str, repo: str) -> Dict:
        results = {
            "repo_accessible": False,
            "commits_accessible": False,
            "pulls_accessible": False,
            "errors": [],
        }

        try:
            await self.api_manager.get_repo_info(owner, repo)
            results["repo_accessible"] = True
        except Exception as e:
            results["errors"].append(f"Repo access: {e}")

        try:
            await self.api_manager.get_commits(owner, repo)
            results["commits_accessible"] = True
        except Exception as e:
            results["errors"].append(f"Commits access: {e}")

        try:
            await self.api_manager.get_pull_requests(owner, repo)
            results["pulls_accessible"] = True
        except Exception as e:
            results["errors"].append(f"PRs access: {e}")

        return results


github_api_manager = None


def init_github_manager(token: str = None):
    global github_api_manager
    github_api_manager = GitHubAPIManager(token)


def get_github_manager() -> GitHubAPIManager:
    return github_api_manager
