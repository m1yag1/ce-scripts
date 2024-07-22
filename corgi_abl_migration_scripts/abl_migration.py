import os
import asyncio
from typing import Optional, List, cast

from httpx import AsyncClient
from sqlalchemy.orm import Session
from app.db.session import Session as SessionMaker
from app.db.schema import Book, Commit, Repository, ApprovedBook
from app.service.repository import repository_service
from app.github import get_book_repository, GitHubRepo, AuthenticatedClient


class RateLimiter:
    def __init__(self, interval: int = 5):
        self.count = 0
        self.interval = interval

    async def wait(self):
        if self.count >= self.interval:
            await asyncio.sleep(2.5)
            self.count = 0
        else:
            self.count += 1


limiter = RateLimiter()


async def fetch_book_data(client, repo_name, repo_owner, sha):
    await limiter.wait()
    return await get_book_repository(client, repo_name, repo_owner, sha)


def get_or_create_repository(
    db: Session, repo_name: str, repo_owner: str, github_repo: GitHubRepo
) -> Repository:
    db_repo = cast(
        Optional[Repository],
        db.query(Repository)
        .filter(Repository.name == repo_name, Repository.owner == repo_owner)
        .first(),
    )
    if db_repo is None:
        db_repo = Repository(
            id=github_repo.database_id, name=repo_name, owner=repo_owner
        )
        repository_service.upsert_repositories(db, [db_repo])
    return db_repo


def add_books_to_commit(
    db: Session, commit: Commit, edition: int, abl_books: List[dict]
):
    for abl_book in abl_books:
        slug = abl_book["slug"]
        style = abl_book["style"]
        uuid = abl_book["uuid"]
        db_book = Book(uuid=uuid, slug=slug, edition=edition, style=style)
        if not any(dbb.uuid == uuid for dbb in commit.books):
            commit.books.append(db_book)
            db.add(db_book)


async def migrate_abl_data(client: AuthenticatedClient, approved_books: List[dict]):
    db = SessionMaker()
    for approved_book in db.query(ApprovedBook).all():
        db.delete(approved_book)
    # db.commit()
    for approved_book in approved_books:
        try:
            await add_approved_book(client, db, approved_book)
            db.commit()
        except Exception as e:
            print(e)


async def add_approved_book(client, db, approved_book):
    fq_repo_name = approved_book["repository_name"]
    if "/" in fq_repo_name:
        repo_owner, repo_name = fq_repo_name.split("/")
    else:
        repo_owner = "openstax"
        repo_name = fq_repo_name
    print(repo_name)
    for version in approved_book["versions"]:
        edition = version["edition"]
        sha = version["commit_sha"]
        commit_metadata = version["commit_metadata"]
        # abl_timestamp = commit_metadata["committed_at"]
        abl_books = commit_metadata["books"]
        commit = cast(
            Optional[Commit],
            db.query(Commit).filter(Commit.sha == sha).first(),
        )
        add_books = False
        if commit is None:
            github_repo, sha, timestamp, repo_books = await fetch_book_data(
                client, repo_name, repo_owner, sha
            )
            db_repo = get_or_create_repository(db, repo_name, repo_owner, github_repo)
            commit = Commit(
                repository_id=db_repo.id,
                sha=sha,
                timestamp=timestamp,
                books=[],
            )
            db.add(commit)
            add_books = True
            print(f"Commit not found: {sha}. Adding...")
        elif len(commit.books) != len(abl_books):
            github_repo, sha, timestamp, repo_books = await fetch_book_data(
                client, repo_name, repo_owner, sha
            )
            add_books = True
            print(
                f"Found commit {commit.sha}, but books did not match. Adding books..."
            )
        else:
            continue
        if add_books:
            is_matching_book_list = all(
                any(
                    repo_book["slug"] == abl_book["slug"]
                    and repo_book["style"] == abl_book["style"]
                    for repo_book in repo_books
                )
                for abl_book in abl_books
            )
            if not is_matching_book_list:
                print(
                    "Oops! Looks like the books do not match!",
                    repo_name,
                    sha,
                    abl_books,
                    repo_books,
                )
                return

            add_books_to_commit(db, commit, int(edition), abl_books)
            print("Inserted version")


async def main():
    token = os.environ["GITHUB_TOKEN"]
    abl_raw_url = os.environ["ABL_RAW_URL"]

    async with AsyncClient() as client:
        response = await client.get(abl_raw_url)
        response.raise_for_status()
        payload = response.json()
        approved_books = payload["approved_books"]
        response.raise_for_status()
        client.headers["Authorization"] = f"Bearer {token}"
        client = cast(AuthenticatedClient, client)
        await migrate_abl_data(client, approved_books)


if __name__ == "__main__":
    asyncio.run(main())
