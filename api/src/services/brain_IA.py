"""
src/services/brain_IA.py

AI Service for video processing using Groq API.
Manages titles and analyses with external prompts.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv
from openai import OpenAI

# ── Path Configuration ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from src.utils.logs import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

load_dotenv()


class Brain:
    """Main class for AI interaction (Groq)"""

    def __init__(self):
        self.API_KEY = os.getenv("GLOK_API")

        if not self.API_KEY:
            logger.warning("API_KEY not found - using fallback without AI")
            self.client = None
        else:
            self.client = OpenAI(
                api_key=self.API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )

        logger.info("Brain AI initialized successfully")

    # ──────────────────────────────────────────────────────────────
    #  MAIN METHODS
    # ──────────────────────────────────────────────────────────────

    def _fallback_moments(
        self, transcription: List[Dict], video_duration: float
    ) -> Dict:
        """Fallback: generates moments based on transcription."""
        logger.info("Running moments fallback")

        moments = []

        if transcription:
            # Get the first 3 moments (best ones)
            first = transcription[:3] if len(transcription) >= 3 else transcription

            for i, item in enumerate(first):
                start = item.get("start", 0)
                end = min(item.get("end", start + 8), video_duration)
                text = item.get("text", "")[:80]

                moments.append(
                    {
                        "id": i + 1,
                        "start": int(start),
                        "end": int(end),
                        "text": text if text else f"Highlight {i+1}",
                        "reason": "Highlight moment (fallback)",
                    }
                )

        return {"moments": moments}

    def generate_titles(
        self,
        video_title: str,
        description: str = "",
        count: int = 5,
        duration: int = 0,
        uploader: str = "",
    ) -> Dict[str, List[str]]:
        """
        Generates viral titles for the video using AI.
        """
        if not self.client:
            logger.warning("Client not available to generate titles")
            return {"titles": self._fallback_titles(video_title, count)}

        try:
            # Build improved prompt
            prompt = self._build_titles_prompt(
                video_title, description, duration, uploader, count
            )

            # Make request
            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a viral content marketing specialist for YouTube Shorts and Reels. Create titles that generate clicks and engagement.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.9,
                max_tokens=800,
            )

            content = response.choices[0].message.content
            logger.info(f"AI response (titles): {content[:300]}...")

            # Extract titles from text
            titles = self._extract_titles_from_text(content, count)

            # If titles were extracted, return them
            if titles and len(titles) > 1:
                # Remove duplicates and clean
                titles = self._clean_titles(titles)
                logger.info(f"✅ Titles extracted: {len(titles)} titles")
                return {"titles": titles[:count]}

            # If not enough titles extracted, try fallback
            logger.warning("Could not extract enough titles, using fallback")
            fallback_titles = self._fallback_titles(video_title, count)

            # Merge AI titles with fallback if at least 1 exists
            if titles:
                combined = titles + fallback_titles
                combined = self._clean_titles(combined)
                return {"titles": combined[:count]}

            return {"titles": fallback_titles}

        except Exception as e:
            logger.error(f"Error generating titles: {e}")
            return {"titles": self._fallback_titles(video_title, count)}

    # ──────────────────────────────────────────────────────────────
    #  PROMPT BUILDERS
    # ──────────────────────────────────────────────────────────────

    def _build_titles_prompt(
        self,
        video_title: str,
        description: str,
        duration: int,
        uploader: str,
        count: int,
    ) -> str:
        """Builds the prompt for generating titles"""
        prompt = f"""
        Create {count} creative and viral titles for a YouTube video.
        
        Original title: "{video_title}"
        """

        if description:
            short_desc = description[:300]
            prompt += f"\nDescription: {short_desc}..."

        if duration > 0:
            prompt += f"\nDuration: {duration // 60} minutes"

        if uploader:
            prompt += f"\nChannel: {uploader}"

        prompt += """
        
        IMPORTANT RULES:
        1. Each title must be between 30 and 80 characters
        2. Use words that generate curiosity: "secret", "nobody tells you", "reality", "shocking"
        3. Create titles with emotional hooks
        4. Be creative, avoiding generic clichés
        5. Titles must work well for Shorts/Reels
        6. DO NOT repeat the original title
        7. DO NOT use the same title more than once
        
        RESPONSE FORMAT:
        Just list the titles, one per line, without numbering.
        """

        return prompt

    # ──────────────────────────────────────────────────────────────
    #  TEXT DATA EXTRACTION
    # ──────────────────────────────────────────────────────────────

    def _extract_titles_from_text(self, text: str, count: int) -> List[str]:
        """Extracts titles from AI text."""
        titles = []
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            line = re.sub(r"^[\d]+[\.\)]\s*", "", line)
            line = re.sub(r"^[-\*\•]\s*", "", line)
            line = re.sub(r'^["\']+|["\']+$', "", line)

            if any(
                word in line.lower()
                for word in ["here are", "list of", "titles:", "titulos:"]
            ):
                continue

            if len(line) > 10 and len(line) < 150:
                if titles and line == titles[-1]:
                    continue
                titles.append(line)
                if len(titles) >= count:
                    break

        return titles

    def _clean_titles(self, titles: List[str]) -> List[str]:
        """Cleans and removes duplicates from the titles list."""
        seen = set()
        clean = []
        for title in titles:
            title = title.strip()
            if not title:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            clean.append(title)
        return clean

    # ──────────────────────────────────────────────────────────────
    #  FALLBACKS
    # ──────────────────────────────────────────────────────────────

    def _fallback_titles(self, video_title: str, count: int) -> List[str]:
        """Fallback: generates titles without AI."""
        logger.info("Generating fallback titles")

        base_title = video_title
        base_title = re.sub(r"\s*[|:]\s*[^|:]+$", "", base_title)
        base_title = re.sub(r"^(Prof\.|Dr\.|Mestre)\s+", "", base_title)

        templates = [
            f"{base_title}",
            f"{base_title} - What nobody tells you",
            f"🔥 The truth about {base_title}",
            f"{base_title} - You need to know this",
            f"How {base_title} is changing the game",
            f"{base_title} - The best moments",
            f"SHOCKING: {base_title}",
            f"The secret behind {base_title}",
        ]

        titles = []
        seen = set()

        for template in templates:
            title = template
            if len(title) > 80:
                title = title[:77] + "..."
            key = title.lower()
            if key not in seen:
                seen.add(key)
                titles.append(title)
            if len(titles) >= count:
                break

        return titles
