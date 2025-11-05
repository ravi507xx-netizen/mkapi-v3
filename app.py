from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import os
import json

app = FastAPI(
    title="Universal AI API",
    description="Multi-service AI API with credit limits and admin controls",
    version="3.1.0"
)

# In-memory storage for serverless compatibility
API_KEYS_STORAGE = {}
ADMIN_USERS_STORAGE = {}
REQUEST_LOGS_STORAGE = []

# Generate a simpler API key that's more reliable in serverless
def generate_api_key():
    """Generate a simple API key for serverless environment"""
    import time
    timestamp = str(int(time.time()))
    random_part = secrets.token_urlsafe(16)
    return f"api_{timestamp}_{random_part}"

# Initialize storage with default admin - keep it simple for serverless
def init_storage():
    """Initialize in-memory storage for serverless environment"""
    global API_KEYS_STORAGE, ADMIN_USERS_STORAGE, REQUEST_LOGS_STORAGE
    
    try:
        # Default admin with simple password
        password_hash = hashlib.sha256("mk123".encode()).hexdigest()
        ADMIN_USERS_STORAGE['mk'] = password_hash
        
        # Create a default API key for testing
        try:
            default_key = generate_api_key()
            API_KEYS_STORAGE[default_key] = {
                'id': 1,
                'key': default_key,
                'name': 'Test Key',
                'created_at': datetime.utcnow(),
                'is_active': True,
                'total_requests': 0,
                'daily_requests': 0,
                'daily_limit': 30,
                'credits': 50,
                'last_reset': datetime.utcnow(),
                'last_used': None,
                'expires_at': datetime.utcnow() + timedelta(days=365)
            }
            print(f"✅ Default API key created: {default_key[:8]}...")
        except Exception as e:
            print(f"Warning: Could not create default API key: {e}")
    except Exception as e:
        print(f"Warning: Could not initialize storage: {e}")

# Initialize storage on startup
try:
    init_storage()
    print("✅ Storage initialized successfully")
except Exception as e:
    print(f"Storage initialization failed: {e}")

def verify_admin(username: str, password: str) -> bool:
    """Verify admin credentials"""
    try:
        if username in ADMIN_USERS_STORAGE:
            stored_hash = ADMIN_USERS_STORAGE[username]
            return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    except Exception:
        pass
    return False

def check_credits(api_key: str, credits_needed: int = 0) -> bool:
    """Check if user has enough credits"""
    try:
        if api_key not in API_KEYS_STORAGE:
            return False
        
        key_data = API_KEYS_STORAGE[api_key]
        if not key_data['is_active']:
            return False
        
        return key_data['credits'] >= credits_needed
    except Exception:
        return False

def use_credits(api_key: str, credits_used: int):
    """Deduct credits from user's balance"""
    try:
        if api_key in API_KEYS_STORAGE:
            API_KEYS_STORAGE[api_key]['credits'] -= credits_used
    except Exception:
        pass

def log_request(api_key: str, endpoint: str, prompt: str = None, response_time: float = None, credits_used: int = 0):
    """Log API request for analytics"""
    try:
        REQUEST_LOGS_STORAGE.append({
            'id': len(REQUEST_LOGS_STORAGE) + 1,
            'api_key': api_key,
            'endpoint': endpoint,
            'prompt': prompt,
            'response_time': response_time,
            'credits_used': credits_used,
            'created_at': datetime.utcnow()
        })
        
        # Keep only last 100 logs to prevent memory issues
        if len(REQUEST_LOGS_STORAGE) > 100:
            REQUEST_LOGS_STORAGE.pop(0)
    except Exception:
        pass

def update_usage(api_key: str):
    """Update usage statistics"""
    try:
        if api_key in API_KEYS_STORAGE:
            key_data = API_KEYS_STORAGE[api_key]
            key_data['total_requests'] += 1
            key_data['daily_requests'] += 1
            key_data['last_used'] = datetime.utcnow()
            
            # Reset daily counter if it's a new day
            today = datetime.utcnow().date()
            if key_data['last_reset'].date() < today:
                key_data['daily_requests'] = 1
                key_data['last_reset'] = datetime.utcnow()
    except Exception:
        pass

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Universal AI API",
        "version": "3.1.0",
        "status": "running",
        "endpoints": {
            "/image": "Generate images (2 credits)",
            "/video": "Generate videos (2 credits)", 
            "/voice": "Generate voice (1 credit)",
            "/qr": "Generate QR codes (1 credit)",
            "/num": "Number service (5 credits)",
            "/ffinfo": "Info redirect (1 credit)",
            "/health": "Health check",
            "/admin/*": "Admin endpoints"
        }
    }

@app.get("/ffinfo")
async def ffinfo_redirect(
    uid: str = Query(..., description="User ID"),
    api_key: str = Query(..., description="Your API key")
):
    """FF Info redirect - COST: 1 credit"""
    try:
        start_time = datetime.utcnow()
        
        # Check if user has enough credits (1 credit needed)
        if not check_credits(api_key, 1):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 1 credit.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Redirect to the external service with MK_DEVELOPER key
        redirect_url = f"https://danger-info-alpha.vercel.app/accinfo?uid={uid}&key=MK_DEVELOPER"
        
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 1)
        update_usage(api_key)
        log_request(api_key, "/ffinfo", uid, response_time, 1)
        
        return RedirectResponse(redirect_url)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"FF Info redirect error: {str(e)}")

@app.get("/image")
async def image_generation(
    prompt: str = Query(..., description="Image generation prompt"),
    width: int = Query(512, description="Image width"),
    height: int = Query(512, description="Image height"),
    api_key: str = Query(..., description="Your API key")
):
    """Generate images - COST: 2 credits"""
    start_time = datetime.utcnow()
    
    try:
        # Check if user has enough credits (2 credits needed)
        if not check_credits(api_key, 2):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 2 credits.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Generate direct image URL
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        direct_image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"
        
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 2)
        update_usage(api_key)
        log_request(api_key, "/image", prompt, response_time, 2)
        
        return direct_image_url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation error: {str(e)}")

@app.get("/voice")
async def voice_generation(
    text: str = Query(..., description="Text to convert to speech"),
    api_key: str = Query(..., description="Your API key")
):
    """Generate voice from text - COST: 1 credit"""
    start_time = datetime.utcnow()
    
    try:
        # Check if user has enough credits (1 credit needed)
        if not check_credits(api_key, 1):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 1 credit.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Generate voice URL using TTS API
        import urllib.parse
        encoded_text = urllib.parse.quote(text)
        voice_url = f"https://api.murf.ai/api/v1/speech/synthesize/stream?text={encoded_text}&voice=en-US-Standard-B&format=mp3&style=neutral&spokenPacing=medium"
        
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 1)
        update_usage(api_key)
        log_request(api_key, "/voice", text, response_time, 1)
        
        return voice_url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice generation error: {str(e)}")

@app.get("/qr")
async def qr_generation(
    data: str = Query(..., description="Data to encode in QR code"),
    api_key: str = Query(..., description="Your API key")
):
    """Generate QR codes - COST: 1 credit"""
    start_time = datetime.utcnow()
    
    try:
        # Check if user has enough credits (1 credit needed)
        if not check_credits(api_key, 1):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 1 credit.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Generate QR code URL
        import urllib.parse
        encoded_data = urllib.parse.quote(data)
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=200x200&data={encoded_data}&format=svg"
        
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 1)
        update_usage(api_key)
        log_request(api_key, "/qr", data, response_time, 1)
        
        return qr_url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"QR generation error: {str(e)}")

@app.get("/video")
async def video_generation(
    prompt: str = Query(..., description="Video generation prompt"),
    api_key: str = Query(..., description="Your API key")
):
    """Video generation - COST: 2 credits"""
    start_time = datetime.utcnow()
    
    try:
        # Check if user has enough credits (2 credits needed)
        if not check_credits(api_key, 2):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 2 credits.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Generate video using Pollinations.ai
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt)
        video_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&nologo=true&seed=1&model=black-forest-labs/flux"
        
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 2)
        update_usage(api_key)
        log_request(api_key, "/video", prompt, response_time, 2)
        
        return video_url
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Video generation error: {str(e)}")

@app.get("/num")
async def number_service(
    mobile: str = Query(..., description="Mobile number"),
    api_key: str = Query(..., description="Your API key")
):
    """Number service - COST: 5 credits"""
    start_time = datetime.utcnow()
    
    try:
        # Check if user has enough credits (5 credits needed)
        if not check_credits(api_key, 5):
            raise HTTPException(status_code=402, detail="Insufficient credits. This service costs 5 credits.")
        
        # Validate API key
        if api_key not in API_KEYS_STORAGE:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Call number service API
        async with httpx.AsyncClient(timeout=30.0) as client:
            num_url = f"https://nixonsmmapi.s77134867.workers.dev/?mobile={mobile}"
            response = await client.get(num_url)
            response.raise_for_status()
            num_response = response.text
            
        # Deduct credits and log request
        response_time = (datetime.utcnow() - start_time).total_seconds()
        use_credits(api_key, 5)
        update_usage(api_key)
        log_request(api_key, "/num", mobile, response_time, 5)
        
        return num_response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Number service error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        return {
            "status": "healthy", 
            "timestamp": datetime.utcnow().isoformat(),
            "api_keys_count": len(API_KEYS_STORAGE),
            "logs_count": len(REQUEST_LOGS_STORAGE),
            "version": "3.1.0"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Vercel serverless function handler
def handler(request, context=None):
    """Vercel serverless function handler"""
    try:
        return app(request)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Server error: {str(e)}"}
        )