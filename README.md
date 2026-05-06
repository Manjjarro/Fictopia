````markdown
# 📚 Fictopia - AI-Powered Book Companion

Fictopia is an advanced FastAPI-based backend for an intelligent book companion application. It uses AI (Google Gemini + Ollama fallback) to provide chapter summaries, answer questions with spoiler protection, track character development, and engage readers with discussion prompts.

## ✨ Features

### 🤖 Dual AI System
- **Primary**: Google Gemini API (powerful cloud AI)
- **Fallback**: Ollama (offline, privacy-focused AI)
- Automatic fallback when API limits are reached or Gemini is unavailable
- Transparent source tracking (know which AI answered)

### 📖 Core Features
- **Smart Summarization**: Generate concise 3-point summaries of chapters
- **Spoiler-Protected Chat**: "Narrative Fog" system prevents accidental story spoilers
- **Mood & Theme Detection**: Analyze emotional tone and themes of chapters
- **Character Tracking**: Automatically identify and track character appearances
- **Discussion Prompts**: Generate thought-provoking reflection questions
- **Reading Progress**: Track user progress and reading streaks
- **Multi-turn Conversations**: Maintain chat history per session

### 📊 Analytics & Insights
- Popular questions tracking
- AI usage statistics (Gemini vs Ollama)
- User engagement metrics
- Reading patterns and insights
- Personalized reading recommendations

### 🎵 Audiobook Support
- Metadata storage for narrators, duration, URLs
- Integration-ready for audio streaming

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional but recommended)
- Google Gemini API key (free from [Google AI Studio](https://aistudio.google.com))
- Ollama (for offline AI fallback)

### Option 1: Local Setup

1. **Clone and Install**
```bash
git clone https://github.com/Manjjarro/Fictopia.git
cd Fictopia
pip install -r requirements.txt
```

2. **Configure Environment**
```bash
cp .env.example .env
# Edit .env with your settings
# Add your GEMINI_API_KEY
```

3. **Run API**
```bash
python -m uvicorn main:app --reload
```

Server starts at `http://localhost:8000`

### Option 2: Docker Compose (Recommended)

```bash
# Start entire stack
docker-compose up -d

# Check logs
docker-compose logs -f api

# Stop
docker-compose down
```

This sets up:
- FastAPI backend (port 8000)
- PostgreSQL database
- Redis cache
- Ollama (offline AI)

## 📚 API Documentation

### Interactive Docs
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Key Endpoints

#### Health Check
```bash
GET /
```
Returns system status and AI service availability.

#### Summarize Chapter
```bash
POST /summarize
{
  "chapter_text": "The hero began..."
}
```

#### Chat with Spoiler Protection
```bash
POST /chat
{
  "book_title": "The Great Adventure",
  "current_chapter_content": "...",
  "all_previous_chapters": "...",
  "future_context": "...",  # Known to AI, not revealed
  "user_question": "What happens next?"
}
```

#### Analyze Mood & Theme
```bash
POST /analyze/mood-theme
{
  "chapter_content": "..."
}
```

#### Generate Discussion Prompt
```bash
POST /generate/discussion-prompt
{
  "chapter_content": "...",
  "difficulty": "medium"  # easy, medium, hard
}
```

#### Extract Characters
```bash
POST /extract/characters
{
  "query": "Alice met Bob..."
}
```

#### Track Reading Progress
```bash
POST /user/progress
{
  "user_id": 1,
  "book_id": 1,
  "current_chapter": 5,
  "characters_encountered": [1, 2, 3]
}
```

#### Analytics
```bash
GET /analytics/user/{user_id}/{book_id}
GET /analytics/book/{book_id}/popular-questions
GET /analytics/book/{book_id}/ai-usage
GET /analytics/book/{book_id}/engagement
```

## ⚙️ Configuration

### Key Environment Variables
```env
# Gemini API
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-1.5-pro

# Offline AI
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
USE_OFFLINE_FALLBACK=true

# Database
DATABASE_URL=sqlite:///./fictopia.db
# Or PostgreSQL: postgresql://user:password@localhost/fictopia

# API
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

# Input Limits
MAX_CHAPTER_LENGTH=50000
MAX_QUESTION_LENGTH=1000

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

## 🧪 Testing

### Run Tests
```bash
# All tests
pytest test_api.py -v

# With coverage
pytest test_api.py --cov=. --cov-report=html

# Using test runner script
bash run_tests.sh
```

### Test Coverage
- Health checks
- Summarization
- Chat with spoiler protection
- Mood/theme analysis
- Discussion prompts
- Character extraction
- Rate limiting
- Error handling
- 30+ comprehensive tests

## 📖 Usage Examples

### Example 1: Summarize a Chapter
```python
import httpx
import asyncio

async def summarize():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/summarize",
            json={
                "chapter_text": "The hero journeyed through the forest..."
            }
        )
        print(response.json())

asyncio.run(summarize())
```

### Example 2: Chat with Spoiler Protection
```python
async def chat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/chat",
            json={
                "book_title": "The Mystery",
                "current_chapter_content": "The detective found a clue...",
                "all_previous_chapters": "Chapters 1-4 summary...",
                "future_context": "The villain is secretly the friend",
                "user_question": "Who is the villain?"
            }
        )
        data = response.json()
        print(f"Answer: {data['answer']}")
        print(f"Source: {data['source']}")  # "gemini" or "ollama"
```

### Example 3: Track Reading Progress
```python
async def track_progress():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/user/progress",
            json={
                "user_id": 1,
                "book_id": 1,
                "current_chapter": 5,
                "characters_encountered": [1, 2, 3]
            }
        )
        data = response.json()
        print(f"Progress: {data['progress_percentage']}%")
        print(f"Insights: {data['insights']}")
```

## 🗄️ Database Schema

### Tables
- **users**: User accounts
- **books**: Book metadata
- **chapters**: Chapter content and analysis
- **characters**: Character information
- **user_progress**: Reading progress tracking
- **chat_sessions**: Conversation history
- **discussion_prompts**: Generated prompts
- **analytics**: Event tracking
- **audiobook_metadata**: Audiobook info

## 🔒 Security

- Input validation on all endpoints
- Rate limiting (100 requests/hour by default)
- Async/await for non-blocking operations
- SQL injection prevention (SQLAlchemy ORM)
- CORS configured for cross-origin requests
- Environment variables for sensitive data
- Structured logging for monitoring

## 🎯 Performance

- **Caching**: Redis integration ready
- **Database**: Async SQLAlchemy with connection pooling
- **Threading**: Thread executor for sync Gemini API
- **Rate Limiting**: SlowAPI for request throttling
- **Logging**: Structured logs to file and console

## 📈 Scalability

- Stateless API design
- Async/await throughout
- Database-backed sessions
- Redis-ready for caching
- Docker containerization
- Load balancer compatible

## 🐛 Troubleshooting

### Gemini Not Working
```bash
# Check API key
echo $GEMINI_API_KEY

# Verify model name
# Use: gemini-1.5-pro, gemini-2.0-flash
```

### Ollama Not Available
```bash
# Install Ollama from https://ollama.ai
# Start Ollama service
ollama serve

# Pull model
ollama pull mistral
```

### Database Connection Issues
```bash
# Check PostgreSQL is running
psql -U fictopia -d fictopia -c "SELECT 1;"

# Or use SQLite (default)
# Check: sqlite:///./fictopia.db
```

### Rate Limiting Issues
Increase in `.env`:
```env
RATE_LIMIT_REQUESTS=200
RATE_LIMIT_PERIOD=3600
```

## 📝 Logging

Logs are written to:
- **Console**: Real-time output
- **File**: `fictopia.log`

Configure level in `.env`:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## 🚀 Deployment

### Heroku
```bash
git push heroku main
```

### AWS/Docker
```bash
docker build -t fictopia .
docker run -p 8000:8000 --env-file .env fictopia
```

### Kubernetes
```bash
kubectl apply -f k8s-deployment.yaml
```

## 📚 Next: Kotlin Client

Share your **Kotlin Android client code** and I'll:
- Review it for best practices
- Suggest optimizations
- Ensure API integration matches
- Add error handling patterns
- Create comprehensive tests

## 📄 License

MIT License - see LICENSE file

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📞 Support

- GitHub Issues: Report bugs
- Discussions: Ask questions
- Email: manjarro@example.com

---

**Status**: ✅ Production-Ready | **Last Updated**: 2026-05-06
````
