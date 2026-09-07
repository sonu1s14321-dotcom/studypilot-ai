from __future__ import annotations
import asyncio
import httpx
from ..database import settings

async def _open_library(query: str) -> list[dict]:
    headers = {"User-Agent": settings.app_user_agent}
    if settings.open_library_contact_email:
        headers["User-Agent"] = f"{settings.app_user_agent} ({settings.open_library_contact_email})"
    async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
        r = await client.get("https://openlibrary.org/search.json", params={"q": query, "limit": 6})
        r.raise_for_status(); docs = r.json().get("docs", [])
    return [{"source":"Open Library","title":d.get("title","Untitled"),"subtitle":", ".join(d.get("author_name",[])[:2]),"year":d.get("first_publish_year"),"url":f"https://openlibrary.org{d.get('key','')}" if d.get("key") else "https://openlibrary.org","open_access":None} for d in docs[:6]]

async def _openalex(query: str) -> list[dict]:
    params = {"search": query, "per_page": 6, "select":"id,display_name,publication_year,doi,primary_location,open_access"}
    if settings.openalex_api_key: params["api_key"] = settings.openalex_api_key
    async with httpx.AsyncClient(timeout=8.0) as client:
        r = await client.get("https://api.openalex.org/works", params=params)
        r.raise_for_status(); works = r.json().get("results", [])
    results = []
    for w in works[:6]:
        loc = w.get("primary_location") or {}; oa = w.get("open_access") or {}
        results.append({"source":"OpenAlex","title":w.get("display_name","Untitled"),"subtitle":"Academic work","year":w.get("publication_year"),"url":loc.get("landing_page_url") or w.get("doi") or w.get("id"),"open_access":oa.get("is_oa")})
    return results

async def search_resources(query: str) -> dict:
    async def safe(fn):
        try: return await fn()
        except Exception: return []
    books, research = await asyncio.gather(safe(lambda:_open_library(query)), safe(lambda:_openalex(query)))
    return {"books": books, "research": research}
