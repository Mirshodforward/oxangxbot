"""
Faster-Whisper Voice Recognition Service
Local STT (Speech-to-Text) - no API keys required
Converts voice messages to text for music search
"""
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_no_ffmpeg_notice_logged = False
_ffmpeg_checked = False
_ffmpeg_path: Optional[str] = None

# Lazy import - faster-whisper faqat kerak bo'lganda yuklanadi
_whisper_model = None
_model_loaded = False


@dataclass
class VoiceCommand:
    """Parsed voice command result"""
    text: str  # Full transcription
    intent: str  # search_music, search_artist, search_song
    query: str  # Extracted search query
    confidence: float  # 0.0 to 1.0


def _get_whisper_model():
    """
    Lazy load whisper model to avoid slow startup
    Uses 'small' model - good balance between speed and accuracy
    """
    global _whisper_model, _model_loaded
    
    if _model_loaded:
        return _whisper_model
    
    try:
        from faster_whisper import WhisperModel
        
        # Model tanlash:
        # - "tiny": Eng tez, lekin aniqlik past (39M parametr)
        # - "base": Tez va o'rtacha aniqlik (74M parametr)
        # - "small": Yaxshi balans - tavsiya etiladi (244M parametr)
        # - "medium": Aniqroq, lekin ko'proq RAM kerak (769M parametr)
        # - "large-v3": Eng aniq, lekin juda ko'p resurs kerak (1.5B parametr)
        
        # CPU uchun int8 quantization - tezroq va kam RAM
        logger.info("Loading Whisper model (small)...")
        _whisper_model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
            download_root=None,  # Default cache folder
            local_files_only=False
        )
        _model_loaded = True
        logger.info("Whisper model loaded successfully")
        return _whisper_model
        
    except ImportError:
        logger.error("faster-whisper not installed. Run: pip install faster-whisper")
        _model_loaded = True  # Mark as attempted
        return None
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        _model_loaded = True
        return None


def _ffmpeg_executable() -> Optional[str]:
    """ffmpeg yo‘li (PATH). Windows: ffmpeg.exe ham qidiriladi."""
    global _ffmpeg_checked, _ffmpeg_path
    if _ffmpeg_checked:
        return _ffmpeg_path
    _ffmpeg_checked = True
    for name in ("ffmpeg", "ffmpeg.exe"):
        p = shutil.which(name)
        if p:
            _ffmpeg_path = p
            return _ffmpeg_path
    _ffmpeg_path = None
    return None


def _log_no_ffmpeg_once() -> None:
    global _no_ffmpeg_notice_logged
    if _no_ffmpeg_notice_logged:
        return
    _no_ffmpeg_notice_logged = True
    logger.info(
        "FFmpeg PATHda yo‘q — ovoz OGG ko‘rinishida transkripsiya qilinadi. "
        "Server: apt install -y ffmpeg  yoki  yum install ffmpeg  |  Docker: RUN apt-get install -y ffmpeg"
    )


def _convert_ogg_to_wav(ogg_path: str) -> Optional[str]:
    """
    OGG → WAV (16 kHz mono) — Whisper uchun qulayroq.
    FFmpeg bo‘lmasa None (caller OGG bilan davom etadi).
    """
    ffmpeg = _ffmpeg_executable()
    if not ffmpeg:
        _log_no_ffmpeg_once()
        return None

    wav_path = ogg_path.replace(".ogg", ".wav")

    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                ogg_path,
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                wav_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.warning("FFmpeg xatolik: %s", (result.stderr or "")[:500])
            return None

        return wav_path

    except FileNotFoundError:
        _log_no_ffmpeg_once()
        return None
    except subprocess.TimeoutExpired:
        logger.warning("FFmpeg konvertatsiya vaqti tugadi")
        return None
    except Exception as e:
        logger.warning("Audio konvertatsiya: %s", e)
        return None


class WhisperVoiceService:
    """
    Local Speech-to-Text service using Faster-Whisper
    No API keys required - runs entirely on your server
    """
    
    def __init__(self):
        self._model = None
    
    def _get_model(self):
        """Get whisper model (lazy loading)"""
        if self._model is None:
            self._model = _get_whisper_model()
        return self._model
    
    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio file to text using Whisper
        
        Args:
            audio_path: Path to audio file (ogg, mp3, wav, etc.)
            
        Returns:
            Transcribed text or None on error
        """
        model = self._get_model()
        if model is None:
            return None
        
        wav_path = None
        try:
            # OGG ni WAV ga convert qilish (agar kerak bo'lsa)
            if audio_path.endswith(".ogg"):
                wav_path = _convert_ogg_to_wav(audio_path)
                if wav_path is None:
                    # Fallback: OGG ni to'g'ridan-to'g'ri ishlatib ko'rish
                    wav_path = audio_path
                process_path = wav_path
            else:
                process_path = audio_path
            
            # Whisper bilan transkripsiya
            segments, info = model.transcribe(
                process_path,
                language=None,  # Auto-detect language
                task="transcribe",
                beam_size=5,
                best_of=5,
                vad_filter=True,  # Voice Activity Detection - shovqinni filter qilish
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )
            
            # Segmentlarni birlashtirish
            text_parts = []
            for segment in segments:
                text_parts.append(segment.text.strip())
            
            full_text = " ".join(text_parts).strip()
            
            if full_text:
                logger.info(f"Transcribed ({info.language}, {info.language_probability:.2f}): {full_text}")
                return full_text
            
            return None
            
        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None
        finally:
            # WAV faylni tozalash
            if wav_path and wav_path != audio_path and os.path.exists(wav_path):
                try:
                    os.unlink(wav_path)
                except:
                    pass
    
    def _extract_music_query(self, text: str) -> tuple[str, str]:
        """
        Extract music search query and intent from transcribed text
        
        Simple rule-based extraction (no AI needed for this)
        """
        text_lower = text.lower()
        
        # Keraksiz so'zlarni olib tashlash
        stop_words = [
            # O'zbek
            "qidirib", "ber", "top", "qo'shiq", "musiqa", "kuylash", 
            "qo'shig'ini", "guruh", "guruhining", "qo'shiqlarini",
            "ijrochi", "artist", "xonanda", "albom", "yuklash",
            "izla", "izlab", "menga", "menda", "manga", "man",
            "toqqiz", "ovozli", "xabar", "yubor",
            # Rus
            "найди", "найти", "песню", "песня", "музыку", "музыка",
            "скачай", "скачать", "включи", "включить", "поставь",
            "артист", "группа", "группы", "исполнитель",
            # Ingliz
            "find", "play", "search", "song", "music", "download",
            "artist", "band", "singer", "album", "track"
        ]
        
        # Artist yoki qo'shiq nomini ajratish
        query = text
        
        # Stop so'zlarni olib tashlash
        for word in stop_words:
            query = re.sub(rf'\b{word}\b', '', query, flags=re.IGNORECASE)
        
        # Ortiqcha bo'shliqlarni tozalash
        query = re.sub(r'\s+', ' ', query).strip()
        
        # Agar query bo'sh bo'lsa, original textni ishlatish
        if not query or len(query) < 2:
            query = text
        
        # Intent aniqlash
        intent = "search_music"
        
        # Artist nomlari ko'pincha bitta yoki ikki so'zdan iborat
        words = query.split()
        if len(words) <= 3:
            intent = "search_artist"
        
        return query, intent
    
    async def parse_music_command(self, text: str) -> VoiceCommand:
        """
        Parse transcribed text to extract music search query
        Uses simple rule-based extraction
        """
        query, intent = self._extract_music_query(text)
        
        return VoiceCommand(
            text=text,
            intent=intent,
            query=query,
            confidence=0.8  # Local model - yaxshi ishonch
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


# Singleton instance
_whisper_service: Optional[WhisperVoiceService] = None


def get_whisper_voice_service() -> Optional[WhisperVoiceService]:
    """Get or create WhisperVoiceService singleton"""
    global _whisper_service
    
    if _whisper_service is None:
        _whisper_service = WhisperVoiceService()
    
    return _whisper_service
