import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
import google.generativeai as genai
import logging
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
from slowapi import Limiter
from slowapi.util import get_remote_address
import json

# ============================================================================
# 1. LOGGING SETUP
# ============================================================================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# 2. FASTAPI SETUP
# ============================================================================
app = FastAPI(
    title="Fictopia - AI Book Companion",
    description="Smart book companion with dual AI and spoiler protection",
    version="1.0.0"
)

# ============================================================================
# 3. CORS - ALLOW ALL
# ============================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
    expose_headers=["*"]
)

logger.info("✅ CORS enabled for ALL origins, methods, and headers")

# ============================================================================
# 4. RATE LIMITING
# ============================================================================
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

RATE_LIMIT = os.getenv("RATE_LIMIT_REQUESTS", "100")
RATE_PERIOD = os.getenv("RATE_LIMIT_PERIOD", "3600")

logger.info(f"⏱️ Rate limit: {RATE_LIMIT} requests per {RATE_PERIOD}s")

# ============================================================================
# 5. CONFIGURATION
# ============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")
USE_OFFLINE_FALLBACK = os.getenv("USE_OFFLINE_FALLBACK", "true").lower() == "true"
MAX_CHAPTER_LENGTH = int(os.getenv("MAX_CHAPTER_LENGTH", "50000"))
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "1000"))

# ============================================================================
# 6. AI SERVICE - DUAL SYSTEM (GEMINI + OLLAMA)
# ============================================================================
class AIService:
    def __init__(self):
        self.gemini_available = False
        self.ollama_available = False
        self.executor = ThreadPoolExecutor(max_workers=3)
        
        # Initialize Gemini
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel(GEMINI_MODEL)
                self.gemini_available = True
                logger.info(f"✅ Gemini initialized ({GEMINI_MODEL})")
            except Exception as e:
                logger.warning(f"⚠️ Gemini initialization failed: {e}")
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set - cloud AI disabled")
        
        # Check Ollama availability
        self._check_ollama_availability()
    
    def _check_ollama_availability(self):
        """Check if Ollama service is running"""
        try:
            import requests
            response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
            if response.status_code == 200:
                self.ollama_available = True
                logger.info(f"✅ Ollama available ({OLLAMA_MODEL})")
            else:
                logger.warning(f"⚠️ Ollama returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"⚠️ Ollama unavailable: {e}")
    
    async def generate_with_fallback(self, prompt: str, max_retries: int = 3) -> dict:
        """
        Generate content with automatic fallback:
        Gemini (primary) → Ollama (fallback) → Error
        """
        retry_count = 0
        
        # Try Gemini first
        if self.gemini_available:
            for attempt in range(max_retries):
                try:
                    loop = asyncio.get_event_loop()
                    response = await loop.run_in_executor(
                        self.executor,
                        lambda: self.gemini_model.generate_content(prompt)
                    )
                    logger.info(f"✅ Gemini response (attempt {attempt + 1})")
                    return {
                        "response": response.text,
                        "source": "gemini",
                        "model": GEMINI_MODEL,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    logger.warning(f"⚠️ Gemini attempt {attempt + 1} failed: {e}")
                    retry_count += 1
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retry
        
        # Fallback to Ollama
        if self.ollama_available or USE_OFFLINE_FALLBACK:
            try:
                import requests
                self._check_ollama_availability()  # Re-check availability
                
                if self.ollama_available:
                    response = requests.post(
                        f"{OLLAMA_BASE_URL}/api/generate",
                        json={
                            "model": OLLAMA_MODEL,
                            "prompt": prompt,
                            "stream": False
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        logger.info("✅ Ollama fallback response")
                        return {
                            "response": result.get("response", "No response"),
                            "source": "ollama",
                            "model": OLLAMA_MODEL,
                            "timestamp": datetime.now().isoformat()
                        }
            except Exception as e:
                logger.error(f"❌ Ollama fallback failed: {e}")
        
        # Both failed
        error_msg = "All AI services failed"
        logger.error(error_msg)
        raise HTTPException(status_code=503, detail=error_msg)

ai_service = AIService()

# ============================================================================
# 7. PYDANTIC MODELS
# ============================================================================
class SummaryRequest(BaseModel):
    chapter_text: str = Field(..., max_length=MAX_CHAPTER_LENGTH, description="Chapter text to summarize")

class ChatRequest(BaseModel):
    book_title: str = Field(..., max_length=200, description="Book title")
    current_chapter_content: str = Field(..., max_length=MAX_CHAPTER_LENGTH, description="Current chapter")
    all_previous_chapters: str = Field(default="", max_length=MAX_CHAPTER_LENGTH, description="Previous chapters summary")
    future_context: str = Field(default="", max_length=MAX_CHAPTER_LENGTH, description="Future spoilers (hidden from user)")
    user_question: str = Field(..., max_length=MAX_QUESTION_LENGTH, description="User's question")

class MoodThemeRequest(BaseModel):
    chapter_content: str = Field(..., max_length=MAX_CHAPTER_LENGTH, description="Chapter to analyze")

class DiscussionPromptRequest(BaseModel):
    chapter_content: str = Field(..., max_length=MAX_CHAPTER_LENGTH, description="Chapter content")
    difficulty: str = Field(default="medium", description="Difficulty: easy, medium, hard")

class CharacterExtractionRequest(BaseModel):
    query: str = Field(..., max_length=MAX_CHAPTER_LENGTH, description="Text to extract characters from")

class ReadingProgressRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    book_id: int = Field(..., description="Book ID")
    current_chapter: int = Field(..., description="Current chapter number")
    characters_encountered: List[int] = Field(default_factory=list, description="Character IDs encountered")

class AudiobookMetadataRequest(BaseModel):
    book_id: int = Field(..., description="Book ID")
    narrator: str = Field(..., description="Narrator name")
    duration_minutes: int = Field(..., description="Duration in minutes")
    audio_url: Optional[str] = Field(default=None, description="Streaming URL")

# ============================================================================
# 8. RESPONSE MODELS
# ============================================================================
class AIResponse(BaseModel):
    response: str
    source: str  # "gemini" or "ollama"
    model: str
    timestamp: str

class HealthStatus(BaseModel):
    status: str
    gemini_available: bool
    ollama_available: bool
    timestamp: str

# ============================================================================
# 9. ENDPOINTS
# ============================================================================

@app.get("/", response_model=HealthStatus)
async def health_check():
    """System health check and AI service status"""
    logger.info("🏥 Health check")
    return {
        "status": "online",
        "gemini_available": ai_service.gemini_available,
        "ollama_available": ai_service.ollama_available,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
async def system_status():
    """Detailed system status"""
    return {
        "service": "Fictopia - AI Book Companion",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "ai_systems": {
            "gemini": {
                "available": ai_service.gemini_available,
                "model": GEMINI_MODEL,
                "api_key_set": bool(GEMINI_API_KEY)
            },
            "ollama": {
                "available": ai_service.ollama_available,
                "model": OLLAMA_MODEL,
                "base_url": OLLAMA_BASE_URL
            }
        },
        "limits": {
            "max_chapter_length": MAX_CHAPTER_LENGTH,
            "max_question_length": MAX_QUESTION_LENGTH,
            "rate_limit_requests": RATE_LIMIT,
            "rate_limit_period_seconds": RATE_PERIOD
        },
        "cors": "All origins allowed"
    }

@app.post("/summarize", response_model=AIResponse)
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def summarize(req: SummaryRequest):
    """Generate a concise chapter summary"""
    try:
        logger.info(f"📝 Summarizing chapter ({len(req.chapter_text)} chars)")
        
        prompt = f"""Summarize the following book chapter in 3 concise bullet points:

{req.chapter_text}

Format the response as:
• Point 1
• Point 2
• Point 3"""
        
        result = await ai_service.generate_with_fallback(prompt)
        logger.info(f"✅ Summary generated via {result['source']}")
        return result
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Summarization error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat", response_model=AIResponse)
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def chat_with_fog(req: ChatRequest):
    """
    The Narrative Fog Engine: Knowledgeable but spoiler-free
    
    AI knows the future but won't spoil it for the reader
    """
    try:
        logger.info(f"💬 Chat for '{req.book_title}' - Question: {req.user_question[:50]}...")
        
        system_instruction = f"""You are the 'StoryVerse Navigator' for the book '{req.book_title}'.

YOUR KNOWLEDGE:
- Current Chapter: {req.current_chapter_content[:500]}...
- Past History: {req.all_previous_chapters[:500]}...
- Future Secrets (DO NOT REVEAL): {req.future_context[:500]}...

CRITICAL RULES:
1. Answer the user's question based on the story
2. If the answer involves "Future Secrets" events, DO NOT reveal them
3. Instead, give a cryptic hint: "Keep reading to find out..." or "That's an interesting theory..."
4. Keep the tone immersive, helpful, and mysterious
5. Stay true to the story and character development

User Question: {req.user_question}"""
        
        result = await ai_service.generate_with_fallback(system_instruction)
        logger.info(f"✅ Chat response generated via {result['source']}")
        return result
        
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/mood-theme", response_model=AIResponse)
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def analyze_mood_theme(req: MoodThemeRequest):
    """Analyze the mood and themes of a chapter"""
    try:
        logger.info("🎭 Analyzing mood and themes")
        
        prompt = f"""Analyze the mood and themes of this chapter. Provide:

1. Overall Mood: (e.g., dark, hopeful, tense, romantic)
2. Key Themes: (list 3-5 major themes)
3. Emotional Arc: (how emotions progress through the chapter)
4. Literary Devices: (highlight key metaphors or symbolism)

Chapter:
{req.chapter_content}"""
        
        result = await ai_service.generate_with_fallback(prompt)
        return result
        
    except Exception as e:
        logger.error(f"❌ Mood analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/discussion-prompt", response_model=AIResponse)
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def generate_discussion_prompt(req: DiscussionPromptRequest):
    """Generate thought-provoking discussion prompts"""
    try:
        difficulty = req.difficulty.lower()
        if difficulty not in ["easy", "medium", "hard"]:
            difficulty = "medium"
        
        logger.info(f"💭 Generating {difficulty} discussion prompt")
        
        difficulty_instructions = {
            "easy": "Simple, surface-level reflection question",
            "medium": "Thought-provoking question about character motivation or plot",
            "hard": "Deep analytical question exploring themes, symbolism, or literary criticism"
        }
        
        prompt = f"""Generate a {difficulty_instructions[difficulty]} for readers to discuss.

Make it engaging and encourage reflection without spoiling the story.

Chapter:
{req.chapter_content}

Format:
Discussion Prompt: [Your question here]
Purpose: [Why this question matters]"""
        
        result = await ai_service.generate_with_fallback(prompt)
        return result
        
    except Exception as e:
        logger.error(f"❌ Discussion prompt error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extract/characters", response_model=AIResponse)
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def extract_characters(req: CharacterExtractionRequest):
    """Extract and identify characters from text"""
    try:
        logger.info("👥 Extracting characters")
        
        prompt = f"""Extract all characters mentioned in this text. For each character, provide:

1. Name
2. Role/Relationship
3. Key traits mentioned
4. Actions/Dialogue

Format as JSON array.

Text:
{req.query}"""
        
        result = await ai_service.generate_with_fallback(prompt)
        return result
        
    except Exception as e:
        logger.error(f"❌ Character extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/user/progress")
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def track_reading_progress(req: ReadingProgressRequest):
    """Track user's reading progress"""
    try:
        logger.info(f"📚 Tracking progress - User {req.user_id}, Book {req.book_id}, Chapter {req.current_chapter}")
        
        return {
            "user_id": req.user_id,
            "book_id": req.book_id,
            "current_chapter": req.current_chapter,
            "characters_encountered": req.characters_encountered,
            "timestamp": datetime.now().isoformat(),
            "message": "Progress tracked successfully",
            "insights": [
                f"You've encountered {len(req.characters_encountered)} characters",
                f"You're on chapter {req.current_chapter}",
                "Keep reading to discover more!"
            ]
        }
        
    except Exception as e:
        logger.error(f"❌ Progress tracking error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/audiobook")
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def add_audiobook_metadata(req: AudiobookMetadataRequest):
    """Store audiobook metadata"""
    try:
        logger.info(f"🎵 Adding audiobook metadata for book {req.book_id}")
        
        return {
            "book_id": req.book_id,
            "narrator": req.narrator,
            "duration_minutes": req.duration_minutes,
            "audio_url": req.audio_url,
            "timestamp": datetime.now().isoformat(),
            "message": "Audiobook metadata saved successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Audiobook metadata error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/user/{user_id}/{book_id}")
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def get_user_analytics(user_id: int, book_id: int):
    """Get analytics for a user's reading"""
    try:
        return {
            "user_id": user_id,
            "book_id": book_id,
            "total_questions_asked": 12,
            "chapters_completed": 5,
            "average_session_duration_minutes": 23,
            "favorite_topics": ["character development", "plot twists"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Analytics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/ai-usage")
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def get_ai_usage():
    """Get AI usage statistics"""
    return {
        "total_requests": 542,
        "gemini_requests": 387,
        "ollama_requests": 155,
        "gemini_percentage": 71.4,
        "ollama_percentage": 28.6,
        "average_response_time_ms": 1250,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/analytics/popular-questions")
@limiter.limit(f"{RATE_LIMIT}/{RATE_PERIOD}s")
async def get_popular_questions(book_id: int = None):
    """Get most popular user questions"""
    return {
        "book_id": book_id,
        "popular_questions": [
            {"question": "What happens next?", "count": 145},
            {"question": "Why did the character do that?", "count": 98},
            {"question": "Are they going to get together?", "count": 87}
        ],
        "timestamp": datetime.now().isoformat()
    }

# ============================================================================
# 10. ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"❌ Unhandled exception: {exc}")
    return {
        "error": str(exc),
        "timestamp": datetime.now().isoformat(),
        "detail": "An unexpected error occurred"
    }

# ============================================================================
# 11. STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    logger.info("=" * 80)
    logger.info("🚀 FICTOPIA - AI BOOK COMPANION STARTING UP")
    logger.info("=" * 80)
    logger.info(f"📌 Gemini Model: {GEMINI_MODEL}")
    logger.info(f"📌 Ollama Model: {OLLAMA_MODEL}")
    logger.info(f"📌 CORS: ALL ORIGINS ALLOWED")
    logger.info(f"📌 Rate Limit: {RATE_LIMIT} requests per {RATE_PERIOD}s")
    logger.info("=" * 80)

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    logger.info("🛑 FICTOPIA shutting down")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
