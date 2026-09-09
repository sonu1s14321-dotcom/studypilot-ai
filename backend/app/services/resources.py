from __future__ import annotations

import asyncio
import httpx

from ..database import settings


async def _open_library(query: str) -> list[dict]:
    headers = {
        "User-Agent": settings.app_user_agent
    }

    if settings.open_library_contact_email:
        headers["User-Agent"] = (
            f"{settings.app_user_agent} "
            f"({settings.open_library_contact_email})"
        )

    async with httpx.AsyncClient(
        timeout=8.0,
        headers=headers,
    ) as client:
        r = await client.get(
            "https://openlibrary.org/search.json",
            params={
                "q": query,
                "limit": 6,
            },
        )

        r.raise_for_status()

        docs = r.json().get(
            "docs",
            [],
        )

    return [
        {
            "source": "Open Library",
            "title": d.get(
                "title",
                "Untitled",
            ),
            "subtitle": ", ".join(
                d.get(
                    "author_name",
                    [],
                )[:2]
            ),
            "year": d.get(
                "first_publish_year"
            ),
            "url": (
                f"https://openlibrary.org{d.get('key', '')}"
                if d.get("key")
                else "https://openlibrary.org"
            ),
            "open_access": None,
        }
        for d in docs[:6]
    ]


async def _openalex(query: str) -> list[dict]:
    params = {
        "search": query,
        "per_page": 6,
        "select": (
            "id,display_name,publication_year,"
            "doi,primary_location,open_access"
        ),
    }

    if settings.openalex_api_key:
        params["api_key"] = (
            settings.openalex_api_key
        )

    headers = {
        "User-Agent": settings.app_user_agent
    }

    last_error = None

    async with httpx.AsyncClient(
        timeout=12.0,
        headers=headers,
    ) as client:

        for attempt in range(3):
            try:
                r = await client.get(
                    "https://api.openalex.org/works",
                    params=params,
                )

                if r.status_code in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    if attempt < 2:
                        await asyncio.sleep(
                            1.5 * (attempt + 1)
                        )
                        continue

                r.raise_for_status()

                works = r.json().get(
                    "results",
                    [],
                )

                results = []

                for w in works[:6]:
                    loc = (
                        w.get(
                            "primary_location"
                        )
                        or {}
                    )

                    oa = (
                        w.get(
                            "open_access"
                        )
                        or {}
                    )

                    results.append(
                        {
                            "source": "OpenAlex",
                            "title": w.get(
                                "display_name",
                                "Untitled",
                            ),
                            "subtitle": "Academic work",
                            "year": w.get(
                                "publication_year"
                            ),
                            "url": (
                                loc.get(
                                    "landing_page_url"
                                )
                                or w.get("doi")
                                or w.get("id")
                            ),
                            "open_access": oa.get(
                                "is_oa"
                            ),
                        }
                    )

                return results

            except (
                httpx.RequestError,
                httpx.HTTPStatusError,
            ) as e:
                last_error = e

                if attempt < 2:
                    await asyncio.sleep(
                        1.5 * (attempt + 1)
                    )
                    continue

    if last_error:
        raise last_error

    return []


async def search_resources(
    query: str,
) -> dict:

    async def safe(
        fn,
        source_name,
    ):
        try:
            return await fn()

        except Exception as e:
            print(
                f"{source_name} resource error: {e}"
            )
            return []

    books, research = await asyncio.gather(
        safe(
            lambda: _open_library(query),
            "Open Library",
        ),
        safe(
            lambda: _openalex(query),
            "OpenAlex",
        ),
    )

    return {
        "books": books,
        "research": research,
    }