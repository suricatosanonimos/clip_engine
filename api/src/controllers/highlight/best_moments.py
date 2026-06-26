"""
src/controllers/brain/best_moments.py

Class for selecting the best moments of a video based on transcription.
Inherits from the Brain class and adds specific functionality for moment analysis.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Path Configuration ──────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.services.brain_IA import Brain
from src.utils.logs import logger


class BestMoments(Brain):
    """
    Class for finding the best moments of a video.

    Inherits from the Brain class and adds specific methods for:
    - Finding viral moments based on transcription
    - Selecting the best moments from a JSON file
    - Grouping words into sentences for better analysis
    """

    def __init__(self):
        """Initializes the BestMoments class inheriting from the Brain class"""
        super().__init__()
        logger.info("BestMoments initialized")

    # ──────────────────────────────────────────────────────────────
    #  MAIN METHOD
    # ──────────────────────────────────────────────────────────────

    def find_best_moments(
        self, transcription: List[Dict], video_duration: float
    ) -> Dict[str, Any]:
        """
        Finds the best moments of the video based on the transcription.

        Args:
            transcription: List of segments with start, end, text
            video_duration: Total video duration in seconds

        Returns:
            Dictionary with the list of moments found
        """
        if not self.client or not transcription:
            logger.info("Using fallback for moments (no client or no transcription)")
            return self._fallback_moments(transcription, video_duration)

        try:
            # ── Prepare transcription ──
            formatted_transcription = self._format_transcription(transcription)

            if len(formatted_transcription) > 3000:
                formatted_transcription = formatted_transcription[:3000]

            # ── Build prompt ──
            prompt = self._build_moments_prompt(formatted_transcription)

            # ── Make request ──
            response = self.client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a video editor specializing in identifying viral moments for Shorts/Reels.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
                max_tokens=500,
            )

            content = response.choices[0].message.content
            logger.info(f"AI response (moments): {content[:300]}...")

            # ── Extract moments from text ──
            moments = self._extract_moments_from_text(content, video_duration)

            if moments:
                return {"moments": moments}

            logger.warning("Could not extract moments, using fallback")
            return self._fallback_moments(transcription, video_duration)

        except Exception as e:
            logger.error(f"Error in Brain AI (moments): {e}")
            return self._fallback_moments(transcription, video_duration)

    # ──────────────────────────────────────────────────────────────
    #  SELECT FROM FILE
    # ──────────────────────────────────────────────────────────────

    def select_best_moments_from_file(
        self,
        json_file: str,
        video_duration: Optional[float] = None,
        num_moments: int = 3,
        save_json: bool = True,
    ) -> Dict[str, Any]:
        """
        Reads a transcription JSON file, extracts the best moments and saves to JSON.

        Args:
            json_file: Path to the transcription JSON file
            video_duration: Video duration in seconds (if None, tries to extract from JSON)
            num_moments: Number of moments to extract (default: 3)
            save_json: Save the result to a JSON file

        Returns:
            Dictionary with the selected moments
        """
        # ── 1. Load JSON ──
        json_path = Path(json_file)
        if not json_path.exists():
            logger.error(f"File not found: {json_file}")
            return {"error": "File not found", "moments": []}

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Error reading JSON: {e}")
            return {"error": f"Error reading JSON: {e}", "moments": []}

        # ── 2. Extract transcription ──
        if "segments" in data:
            transcription = data["segments"]
        elif "transcription" in data:
            transcription = data["transcription"]
        elif isinstance(data, list):
            transcription = data
        else:
            logger.error("Unrecognized JSON format")
            return {"error": "Unrecognized JSON format", "moments": []}

        if not transcription:
            logger.warning("Empty transcription")
            return {"error": "Empty transcription", "moments": []}

        # ── 3. Get video duration ──
        if video_duration is None:
            video_duration = data.get("duration", 0)
            if video_duration > 10000:
                last = transcription[-1]
                video_duration = last.get("end", 60)
                if video_duration == 0:
                    video_duration = 60
            elif video_duration == 0 and transcription:
                last = transcription[-1]
                video_duration = last.get("end", 60)

        if video_duration <= 0 or video_duration > 10000:
            logger.warning(f"Invalid duration ({video_duration}), using 60s")
            video_duration = 60

        logger.info(f"📊 Processing transcription with {len(transcription)} segments")
        logger.info(f"⏱️  Video duration: {video_duration:.1f}s")

        # ── 4. Convert to sentences (group words) ──
        sentences = self._group_into_sentences(transcription)
        logger.info(f"📝 {len(sentences)} sentences grouped")

        if not sentences:
            logger.warning("No sentences found")
            return {"error": "No sentences found", "moments": []}

        # ── 5. Call AI to find the best moments ──
        result = self.find_best_moments(sentences, video_duration)

        if "error" in result:
            return result

        # ── 6. Filter and limit moments ──
        moments = result.get("moments", [])

        # If no moments or it's fallback, try manual selection
        if not moments or moments[0].get("reason") == "Highlight moment (fallback)":
            logger.info("Using manual moment selection (improved fallback)")
            moments = self._manual_moment_selection(
                sentences, video_duration, num_moments
            )

        moments = moments[:num_moments]

        # ── 7. Prepare result ──
        final_result = {
            "video": str(json_path),
            "video_name": json_path.stem,
            "video_duration": video_duration,
            "total_segments": len(transcription),
            "total_sentences": len(sentences),
            "num_moments": len(moments),
            "moments": moments,
            "source": (
                "AI (Groq)"
                if moments and moments[0].get("reason") != "Manual selection"
                else "Manual selection"
            ),
        }

        # ── 8. Save to JSON ──
        if save_json:
            output_path = Path(
                f"{ROOT_DIR}/processed_videos/moments/{json_path.stem}_moments.json"
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(final_result, f, ensure_ascii=False, indent=2)
            logger.info(f"💾 Moments saved to: {output_path}")

        logger.info(f"✅ {len(moments)} moments selected")
        for i, m in enumerate(moments, 1):
            logger.info(
                f"   {i}. {m.get('start',0)}s - {m.get('end',0)}s: {m.get('text', '')[:50]}..."
            )

        return final_result

    # ──────────────────────────────────────────────────────────────
    #  FORMAT TRANSCRIPTION FOR PROMPT
    # ──────────────────────────────────────────────────────────────

    def _format_transcription(self, transcription: List[Dict]) -> str:
        """Formats transcription for the AI prompt."""
        lines = []
        for item in transcription[:30]:
            start = item.get("start", 0)
            text = item.get("text", "")[:150]
            minutes = int(start // 60)
            seconds = int(start % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {text}")
        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────
    #  BUILD PROMPT
    # ──────────────────────────────────────────────────────────────

    def _build_moments_prompt(self, transcription: str) -> str:
        """Builds the prompt for finding best moments."""
        return f"""
        Analyze the transcription below and identify the 3 MOST IMPACTFUL AND VIRAL moments.
        
        IMPORTANT RULES:
        - Each moment must be between 5 and 15 seconds
        - FOCUS on phrases that generate CURIOSITY, SURPRISE or EMOTION
        - Prioritize moments that work well for Shorts/Reels
        - Choose moments with EMOTIONAL HOOKS or REVELATIONS
        - AVOID generic introductions or call to action parts
        
        RESPONSE FORMAT (one moment per line):
        Start: Xs, End: Ys - Text of the moment
        
        Transcription (with timestamps):
        {transcription}
        
        Answer ONLY with the list of moments in the requested format.
        """

    # ──────────────────────────────────────────────────────────────
    #  EXTRACT MOMENTS FROM AI RESPONSE
    # ──────────────────────────────────────────────────────────────

    def _extract_moments_from_text(
        self, text: str, video_duration: float
    ) -> List[Dict]:
        """
        Extracts moments from AI text response.

        Returns:
            List of moments: [{"start": int, "end": int, "text": str, "reason": str}, ...]
        """
        moments = []
        lines = text.split("\n")

        # Patterns for finding moments
        patterns = [
            r"(?:start|in[íi]cio)\s*:?\s*(\d+\.?\d*)\s*s?\s*(?:end|fim)\s*:?\s*(\d+\.?\d*)\s*s?\s*[-–]\s*(.+)",
            r"\[(\d+):(\d+)\s*[-–]\s*(\d+):(\d+)\]\s*(.+)",
            r"(\d+\.?\d*)\s*s?\s*[-–]\s*(\d+\.?\d*)\s*s?\s*:?\s*(.+)",
        ]

        for line in lines:
            line = line.strip()
            if not line:
                continue

            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()

                    if len(groups) == 3:
                        start = float(groups[0])
                        end = float(groups[1])
                        moment_text = groups[2].strip()
                    elif len(groups) == 5:
                        min_start = int(groups[0])
                        sec_start = int(groups[1])
                        min_end = int(groups[2])
                        sec_end = int(groups[3])
                        start = min_start * 60 + sec_start
                        end = min_end * 60 + sec_end
                        moment_text = groups[4].strip()
                    else:
                        continue

                    # Validate times
                    if start < 0:
                        start = 0
                    if end > video_duration:
                        end = video_duration
                    if end <= start:
                        end = start + 5

                    moment_text = re.sub(r'^["\']+|["\']+$', "", moment_text)

                    moments.append(
                        {
                            "start": int(start),
                            "end": int(end),
                            "text": moment_text[:100],
                            "reason": "Extracted from AI response",
                        }
                    )
                    break

        return moments[:3]

    # ──────────────────────────────────────────────────────────────
    #  GROUP WORDS INTO SENTENCES
    # ──────────────────────────────────────────────────────────────

    def _group_into_sentences(self, segments: List[Dict]) -> List[Dict]:
        """
        Groups individual words into complete sentences.

        Args:
            segments: List of segments (words or phrases)

        Returns:
            List of sentences with timestamps
        """
        sentences = []
        current_phrase = []
        current_start = None
        current_end = None

        for seg in segments:
            text = seg.get("text", "").strip()
            if not text:
                continue

            start = seg.get("start", 0)
            end = seg.get("end", start + 1)

            if current_start is None:
                current_start = start

            current_phrase.append(text)
            current_end = end

            # Check if it's end of sentence
            clean_text = text.rstrip()
            if clean_text.endswith((".", "!", "?")) or len(current_phrase) >= 15:
                sentence_text = " ".join(current_phrase)
                sentences.append(
                    {"start": current_start, "end": current_end, "text": sentence_text}
                )
                current_phrase = []
                current_start = None
                current_end = None

        if current_phrase:
            sentence_text = " ".join(current_phrase)
            sentences.append(
                {
                    "start": current_start or 0,
                    "end": current_end or current_start or 5,
                    "text": sentence_text,
                }
            )

        return sentences

    # ──────────────────────────────────────────────────────────────
    #  MANUAL MOMENT SELECTION (FALLBACK)
    # ──────────────────────────────────────────────────────────────

    def _manual_moment_selection(
        self, sentences: List[Dict], video_duration: float, num_moments: int
    ) -> List[Dict]:
        """
        Manual selection of moments when AI fails.
        Prioritizes hooks, revelations and emotional moments.
        """
        if not sentences:
            return []

        # Keywords to identify good moments (Portuguese + English)
        keywords_hook = [
            "mas",
            "porque",
            "isso",
            "aí",
            "então",
            "calma",
            "olha",
            "veja",
            "but",
            "because",
            "this",
            "then",
            "wait",
            "look",
            "see",
            "so",
        ]
        keywords_curiosity = [
            "vazou",
            "revelou",
            "novidade",
            "anunciou",
            "oficial",
            "surpresa",
            "leaked",
            "revealed",
            "news",
            "announced",
            "official",
            "surprise",
        ]
        keywords_emotion = [
            "uau",
            "incrível",
            "caramba",
            "nossa",
            "top",
            "muito",
            "demais",
            "wow",
            "incredible",
            "amazing",
            "awesome",
            "top",
            "very",
            "so much",
        ]

        # Score each sentence
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            text = sentence.get("text", "").lower()
            score = 0

            for kw in keywords_hook:
                if kw in text:
                    score += 3
                    break

            for kw in keywords_curiosity:
                if kw in text:
                    score += 4
                    break

            for kw in keywords_emotion:
                if kw in text:
                    score += 2
                    break

            # Questions (Portuguese + English)
            if re.match(
                r"^(o que|como|por que|qual|quando|what|how|why|which|when)", text
            ):
                score += 5

            # Ideal length (5-15 words)
            words = text.split()
            if 5 <= len(words) <= 15:
                score += 2

            scored_sentences.append({**sentence, "score": score, "index": i})

        # Sort by score and select
        scored_sentences.sort(key=lambda x: x.get("score", 0), reverse=True)

        selected = []
        for item in scored_sentences[: num_moments * 2]:
            if item.get("score", 0) > 0:
                selected.append(item)
            if len(selected) >= num_moments:
                break

        if not selected:
            selected = sentences[:num_moments]

        # Convert to expected format
        moments = []
        for item in selected:
            moments.append(
                {
                    "start": int(item.get("start", 0)),
                    "end": int(item.get("end", item.get("start", 0) + 5)),
                    "text": item.get("text", "")[:100],
                    "reason": f"Manual selection (score: {item.get('score', 0)})",
                }
            )

        return moments


if __name__ == "__main__":
    import sys

    best_moments = BestMoments()

    # Procura por transcrições em processed_videos/transcriptions/
    transcriptions_dir = Path(f"{ROOT_DIR}/processed_videos/transcriptions")

    if not transcriptions_dir.exists():
        print(f"❌ Transcriptions directory not found: {transcriptions_dir}")
        print("   Run brain_selector.py first to generate transcriptions")
        sys.exit(1)

    json_files = list(transcriptions_dir.glob("*_transcription.json"))

    if not json_files:
        print(f"❌ No transcription files found in: {transcriptions_dir}")
        sys.exit(1)

    print("=" * 60)
    print("🧠 BestMoments - Selecting Best Moments")
    print("=" * 60)
    print(f"\n📁 Available transcriptions:")
    for i, jf in enumerate(json_files, 1):
        print(f"   {i}. {jf.name}")

    # Usa o primeiro ou permite escolher
    if len(json_files) == 1:
        json_path = json_files[0]
    else:
        try:
            choice = int(input(f"\n🔢 Choose (1-{len(json_files)}): ").strip() or "1")
            json_path = json_files[choice - 1]
        except (ValueError, IndexError):
            json_path = json_files[0]

    print(f"\n📁 Selected: {json_path.name}")

    result = best_moments.select_best_moments_from_file(
        json_file=str(json_path), num_moments=3, save_json=True
    )

    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("📊 FINAL RESULT")
    print("=" * 60)
    print(f"📹 Video: {result.get('video_name', 'Unknown')}")
    print(f"📝 Total sentences: {result.get('total_sentences', 0)}")
    print(f"🎯 Moments selected: {result.get('num_moments', 0)}")
    print(f"🤖 Source: {result.get('source', 'Unknown')}")

    print("\n🏆 BEST MOMENTS:")
    for i, m in enumerate(result.get("moments", []), 1):
        start = m.get("start", 0)
        end = m.get("end", 0)
        text = m.get("text", "")
        reason = m.get("reason", "")
        print(f"\n  {i}. [{start}s - {end}s]")
        print(f"     📝 {text}")
        if reason:
            print(f"     💡 {reason}")

    print("\n" + "=" * 60)
    print("✅ Process completed!")
