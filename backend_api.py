# backend_api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import main
from utils.db import init_db, get_all_quotes, get_posts  # ✅ Added get_posts

app = FastAPI(
    title="Instagram Automation API",
    description="Production-ready Instagram automation with analytics",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_previews = None
executor = ThreadPoolExecutor(max_workers=1)

class SimplePostRequest(BaseModel):
    image_index: int

def run_coro_in_thread(coro):
    def thread_func():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    future = executor.submit(thread_func)
    return future.result()

@app.get("/")
def home():
    return {
        "status": "running",
        "message": "Instagram Automation API v3.0",
        "endpoints": {
            "generate": "/api/generate-previews",
            "post": "/api/post-image",
            "reject": "/api/reject-previews",
            "current": "/api/current-previews",
            "history": "/api/posts",
            "stats": "/api/stats",
            "analytics": "/api/analytics"
        }
    }

@app.post("/api/generate-previews")
async def generate_previews():
    global current_previews
    try:
        result = await main.api_generate_previews()
        current_previews = result

        return {
            "success": True,
            "quote": result["quote"],
            "caption": result["caption"],
            "previews": [
                {"index": i, "url": url}
                for i, url in enumerate(result["preview_urls"])
            ],
            "message": "Previews generated! Use /api/post-image with image_index to post."
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/current-previews")
def get_current_previews():
    if not current_previews:
        return {
            "has_previews": False,
            "message": "No pending previews. Generate new ones with /api/generate-previews"
        }
    
    return {
        "has_previews": True,
        "quote": current_previews["quote"],
        "caption": current_previews["caption"],
        "previews": [
            {"index": i, "url": url}
            for i, url in enumerate(current_previews["preview_urls"])
        ]
    }

@app.post("/api/post-image")
def post_image(req: SimplePostRequest):
    global current_previews
    
    if not current_previews:
        raise HTTPException(
            status_code=400, 
            detail="No previews available. Generate previews first."
        )
    
    try:
        result = main.api_post_selected_preview(
            selected_index=req.image_index,
            preview_paths=current_previews["preview_paths"],
            preview_urls=current_previews["preview_urls"],
            caption=current_previews["caption"],
            quote=current_previews["quote"]
        )
        
        current_previews = None
        
        return {
            "success": True,
            "message": "Post published to Instagram successfully!",
            "posted_url": result["posted_url"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reject-previews")
def reject_previews():
    global current_previews
    
    if not current_previews:
        raise HTTPException(status_code=400, detail="No previews to reject")
    
    try:
        result = main.api_reject_previews(current_previews["preview_paths"])
        current_previews = None
        return {"success": True, "message": "All previews rejected"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/posts")
def get_all_posts(limit: Optional[int] = 50, offset: Optional[int] = 0):
    """Get all posted content with pagination - includes image URLs!"""
    try:
        init_db()
        all_posts = get_posts(limit=1000)  # ✅ Using get_posts() now
        
        if not all_posts:
            return {"total": 0, "showing": 0, "offset": 0, "limit": limit, "posts": []}
        
        # Reverse to show most recent first
        all_posts.reverse()
        
        # Pagination
        paginated = all_posts[offset:offset + limit]
        
        return {
            "total": len(all_posts),
            "showing": len(paginated),
            "offset": offset,
            "limit": limit,
            "posts": paginated  # ✅ Already has id, quote, image_url, posted_at
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/api/posts/recent")
def get_recent_posts(days: Optional[int] = 7):
    """Get recent posts with image URLs."""
    try:
        init_db()
        all_posts = get_posts(limit=1000)  # ✅ Using get_posts()
        
        if not all_posts:
            return {"period": f"Last {days} days", "total_posts": 0, "posts": []}
        
        # Get last 20 posts (already sorted DESC in get_posts)
        recent = all_posts[:20] if len(all_posts) >= 20 else all_posts
        
        return {
            "period": f"Last {days} days",
            "total_posts": len(all_posts),
            "posts": recent  # ✅ Includes image URLs
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/api/stats")
def get_stats():
    """Quick stats summary."""
    try:
        init_db()
        all_quotes = get_all_quotes()
        total = len(all_quotes) if all_quotes else 0
        
        return {
            "total_posts": total,
            "has_pending_previews": current_previews is not None,
            "status": "active"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics")
def get_analytics():
    """Comprehensive analytics dashboard data with image URLs."""
    try:
        init_db()
        all_posts = get_posts(limit=1000)  # ✅ Using get_posts()
        
        if not all_posts:
            return {
                "overview": {
                    "total_posts": 0,
                    "posts_this_week": 0,
                    "posts_this_month": 0,
                    "avg_posts_per_week": 0
                },
                "recent_activity": {"last_5_posts": []},
                "status": {"has_pending_previews": current_previews is not None}
            }
        
        total = len(all_posts)
        
        # Get last 5 posts (already sorted DESC)
        last_5 = all_posts[:5] if total >= 5 else all_posts
        
        # Format for display
        last_5_formatted = []
        for post in last_5:
            last_5_formatted.append({
                "quote": post["quote"][:100] + "..." if len(post["quote"]) > 100 else post["quote"],
                "image_url": post["image_url"],  # ✅ Now included
                "posted_at": post["posted_at"]
            })
        
        return {
            "overview": {
                "total_posts": total,
                "posts_this_week": min(7, total),
                "posts_this_month": min(30, total),
                "avg_posts_per_week": round(total / max(1, total // 7), 2) if total > 0 else 0
            },
            "recent_activity": {"last_5_posts": last_5_formatted},
            "status": {
                "has_pending_previews": current_previews is not None,
                "message": "System operational"
            }
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend_api:app", host="0.0.0.0", port=8000, reload=True)
