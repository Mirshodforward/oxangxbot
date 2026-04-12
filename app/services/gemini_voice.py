"""
Gemini Voice Recognition Service
Converts voice messages to text and extracts music-related commands
"""
import logging
import re
import json
import tempfile
import os
from typing import Optional
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class VoiceCommand:
    """Parsed voice command result"""
    text: str  # Full transcription
    intent: str  # search_music, search_artist, search_song, unknown
    query: str  # Extracted search query (artist name, song name, etc.)
    confidence: float  # 0.0 to 1.0


class GeminiVoiceService:
    """Service for voice-to-text and intent extraction using Gemini API"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self._client: Optional[genai.Client] = None
    
    def _get_client(self) -> genai.Client:
        """Get or create Gemini client"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client
    
    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio file to text using Gemini
        
        Args:
            audio_path: Path to audio file (mp3, ogg, wav, etc.)
            
        Returns:
            Transcribed text or None on error
        """
        try:
            client = self._get_client()
            
            # Upload the audio file
            audio_file = client.files.upload(file=audio_path)
            
            # Generate transcription
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    "Transcribe this audio. Return ONLY the transcribed text, nothing else. "
                    "If the audio is in Uzbek, Russian, or any other language, transcribe it as-is.",
                    audio_file
                ]
            )
            
            return response.text.strip() if response.text else None
            
        except Exception as e:
            logger.error(f"Gemini transcription error: {e}")
            return None
    
    async def parse_music_command(self, text: str) -> VoiceCommand:
        """
        Parse transcribed text to extract music search intent and query
        
        Args:
            text: Transcribed voice message text
            
        Returns:
            VoiceCommand with intent and extracted query
        """
        try:
            client = self._get_client()
            
            prompt = f"""Analyze this voice command for a music bot. The user wants to find music.
Extract the intent and search query.

Voice text: "{text}"

Respond in JSON format:
{{
    "intent": "search_artist" | "search_song" | "search_music",
    "query": "extracted artist name or song name or general search term",
    "confidence": 0.0 to 1.0
}}

Rules:
- "search_artist": User mentions an artist/group name (e.g., "Ummon", "Shahzoda", "BTS")
- "search_song": User mentions a specific song title
- "search_music": General music request without specific artist/song
- Extract the most relevant search term for querying a music database
- Keep the original language of artist/song names

Return ONLY valid JSON, no other text."""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(response.text)
            
            return VoiceCommand(
                text=text,
                intent=result.get("intent", "search_music"),
                query=result.get("query", text),
                confidence=result.get("confidence", 0.5)
            )
            
        except Exception as e:
            logger.error(f"Gemini command parsing error: {e}")
            # Fallback: use the whole text as search query
            return VoiceCommand(
                text=text,
                intent="search_music",
                query=text,
                confidence=0.3
            )
    
    async def process_voice_message(self, audio_path: str) -> Optional[VoiceCommand]:
        """
        Full pipeline: transcribe audio and extract music command
        
        Args:
            audio_path: Path to voice message audio file
            
        Returns:
            VoiceCommand with transcription and parsed intent, or None on error
        """
        # Step 1: Transcribe
        transcription = await self.transcribe_audio(audio_path)
        if not transcription:
            return None
        
        # Step 2: Parse command
        command = await self.parse_music_command(transcription)
        return command


# Global service instance
gemini_voice: Optional[GeminiVoiceService] = None


def get_gemini_voice_service() -> Optional[GeminiVoiceService]:
    """Get Gemini voice service instance (lazy initialization)"""
    global gemini_voice
    
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not configured, voice commands disabled")
        return None
    
    if gemini_voice is None:
        gemini_voice = GeminiVoiceService()
    
    return gemini_voice
