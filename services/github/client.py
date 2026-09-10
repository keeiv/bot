"""GitHub API client for repository monitoring."""

from typing import Any, Dict, Optional

import aiohttp


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    async def get_latest_commit(
        self, owner: str, repo: str
    ) -> Optional[Dict[str, Any]]:
        """Get the latest commit from a repository."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits"

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        commits = await response.json()
                        if commits:
                            commit = commits[0]
                            return {
                                "sha": commit["sha"],
                                "message": commit["commit"]["message"],
                                "author": commit["commit"]["author"]["name"],
                                "date": commit["commit"]["author"]["date"],
                                "url": commit["html_url"],
                            }
                    return None
            except Exception as e:
                print(f"Error fetching commits: {e}")
                return None

    async def get_repo_info(self, owner: str, repo: str) -> Optional[Dict[str, Any]]:
        """Get repository information."""
        url = f"{self.base_url}/repos/{owner}/{repo}"

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        result_value = await response.json()
                        if result_value is None:
                            return None
                        if not isinstance(result_value, dict):
                            raise TypeError(
                                "Unexpected stored or API value: expected dict"
                            )
                        return result_value
                    return None
            except Exception as e:
                print(f"Error fetching repo info: {e}")
                return None
