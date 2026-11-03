from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

import praw
from praw.exceptions import RedditAPIException
from prawcore.exceptions import PrawcoreException

from .config import AppConfig, load_reddit_credentials


@dataclass(frozen=True)
class RedditPost:
    title: str
    body: str
    subreddit: str
    score: int
    comments: int
    permalink: str
    created_utc: float
    post_id: str

    @property
    def age_hours(self) -> float:
        created = datetime.fromtimestamp(self.created_utc, tz=timezone.utc)
        return (datetime.now(timezone.utc) - created).total_seconds() / 3600


def _build_client() -> praw.Reddit:
    credentials = load_reddit_credentials()
    user_agent = (
        f"script:{credentials.app_name}:v{credentials.app_version} "
        f"(by u/{credentials.username or 'local-user'})"
    )
    return praw.Reddit(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        user_agent=user_agent,
    )


def fetch_trending_posts(config: AppConfig) -> list[RedditPost]:
    reddit = _build_client()
    posts: list[RedditPost] = []
    seen_ids: set[str] = set()

    for subreddit_name in config.subreddits:
        subreddit = reddit.subreddit(subreddit_name.strip())
        if config.reddit_sort == "top":
            listing: Iterable = subreddit.top(
                time_filter=config.top_time_filter,
                limit=config.posts_per_subreddit,
            )
        else:
            listing: Iterable = getattr(subreddit, config.reddit_sort)(
                limit=config.posts_per_subreddit
            )

        for item in listing:
            if item.id in seen_ids:
                continue
            seen_ids.add(item.id)

            if item.stickied or (item.over_18 and not config.allow_nsfw):
                continue
            if not getattr(item, "is_self", False):
                continue
            if item.score < config.minimum_score:
                continue

            age_hours = (datetime.now(timezone.utc).timestamp() - item.created_utc) / 3600
            if age_hours > config.maximum_post_age_hours:
                continue

            title = (item.title or "").strip()
            body = (item.selftext or "").strip()
            if not title and not body:
                continue

            posts.append(
                RedditPost(
                    title=title,
                    body=body,
                    subreddit=str(item.subreddit),
                    score=int(item.score),
                    comments=int(item.num_comments),
                    permalink=f"https://www.reddit.com{item.permalink}",
                    created_utc=float(item.created_utc),
                    post_id=str(item.id),
                )
            )

    # Hot posts are already ordered by Reddit. A small score/comment weighting
    # helps compare candidates gathered from multiple selected subreddits.
    posts.sort(key=lambda post: (post.score + post.comments * 0.35), reverse=True)
    return posts


def reddit_error_hint(error: Exception) -> str:
    if isinstance(error, RedditAPIException):
        return f"Reddit API error: {error}"
    if isinstance(error, PrawcoreException):
        return (
            "Reddit could not be reached or rejected the API request. Check your internet, "
            "credentials, app approval, and Reddit Data API access.\n"
            f"Details: {error}"
        )
    return str(error)
