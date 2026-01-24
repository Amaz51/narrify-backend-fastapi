# Text Normalization Service

# Prepares text for TTS by normalizing numbers, dates, abbreviations, etc.
# Ensures clean, readable text for natural speech synthesis.

import re
from typing import Dict, List, Optional, Tuple

from loguru import logger
from num2words import num2words
from unidecode import unidecode

from app.config import settings


class TextService:
    
    # Text Normalization Service
    # Normalizes text for optimal TTS processing.

    def __init__(self):
        self.logger = logger.bind(name=__name__)
        self.abbreviations = settings.ABBREVIATIONS

    def normalize(self, text: str) -> str:
        
        # Complete text normalization pipeline
        # Takes raw text and returns normalized text ready for TTS

        # e.g: "Dr. Smith has $50 at 3:30 PM."
        # output will be: "Doctor Smith has fifty dollars at three thirty P M."
        
        self.logger.debug(f"Normalizing text ({len(text)} chars)")

        # Remove special characters but keep punctuation
        text = self._clean_text(text)

        # Normalize based on settings
        if settings.NORMALIZE_NUMBERS:
            text = self._normalize_numbers(text)

        if settings.NORMALIZE_DATES:
            text = self._normalize_dates(text)

        if settings.NORMALIZE_CURRENCY:
            text = self._normalize_currency(text)

        if settings.NORMALIZE_ABBREVIATIONS:
            text = self._normalize_abbreviations(text)

        # Normalize time
        text = self._normalize_time(text)

        # Normalize URLs and emails
        text = self._normalize_urls(text)
        text = self._normalize_emails(text)

        # Remove extra whitespace
        text = self._clean_whitespace(text)

        self.logger.debug(f"Normalized text ({len(text)} chars)")
        return text

    def _clean_text(self, text: str) -> str:
        # Clean text of unwanted characters
        
        # Convert unicode to ASCII
        text = unidecode(text)

        # Remove page markers
        text = re.sub(r"--- Page \d+ ---", "", text)

        # Remove excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove control characters except newlines and tabs
        text = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", text)

        return text

    def _normalize_numbers(self, text: str) -> str:
        
        # Convert numbers to words
        # "123" to "one hundred twenty three"
        # "1st" → "first"
        # "1,234.56" → "one thousand two hundred thirty four point five six"
        
        def number_to_words(match):
            number_str = match.group(0)

            try:
                # Handle ordinals (1st, 2nd, 3rd, etc.)
                if re.match(r"\d+(st|nd|rd|th)", number_str):
                    number = int(re.sub(r"(st|nd|rd|th)", "", number_str))
                    return num2words(number, to="ordinal")

                # Handle decimals
                if "." in number_str:
                    parts = number_str.split(".")
                    integer_part = num2words(int(parts[0].replace(",", "")))
                    decimal_part = " point " + " ".join(
                        [num2words(int(d)) for d in parts[1]]
                    )
                    return integer_part + decimal_part

                # Handle regular numbers (remove commas)
                number = int(number_str.replace(",", ""))

                # Special handling for years (1900-2099)
                if 1900 <= number <= 2099:
                    return num2words(number, to="year")

                return num2words(number)

            except (ValueError, OverflowError):
                # Return original if conversion fails
                return number_str

        # Match numbers (including decimals and commas)
        text = re.sub(r"\d+(?:,\d{3})*(?:\.\d+)?(?:st|nd|rd|th)?", number_to_words, text)

        return text

    def _normalize_dates(self, text: str) -> str:
        
        # Normalize date formats
        # "01/15/2024" to "January fifteenth, twenty twenty four"
        # "2024-01-15" to "January fifteenth, twenty twenty four"
        
        def date_to_words(match):
            date_str = match.group(0)

            try:
                # Parse different date formats
                if "/" in date_str:
                    # MM/DD/YYYY or DD/MM/YYYY
                    parts = date_str.split("/")
                    if len(parts) == 3:
                        month, day, year = map(int, parts)
                        month_name = self._month_to_name(month)
                        day_ord = num2words(day, to="ordinal")
                        year_words = num2words(year, to="year")
                        return f"{month_name} {day_ord}, {year_words}"

                elif "-" in date_str:
                    # YYYY-MM-DD
                    parts = date_str.split("-")
                    if len(parts) == 3:
                        year, month, day = map(int, parts)
                        month_name = self._month_to_name(month)
                        day_ord = num2words(day, to="ordinal")
                        year_words = num2words(year, to="year")
                        return f"{month_name} {day_ord}, {year_words}"

            except (ValueError, IndexError):
                pass

            return date_str

        # Match date patterns
        text = re.sub(r"\d{1,2}/\d{1,2}/\d{4}", date_to_words, text)
        text = re.sub(r"\d{4}-\d{1,2}-\d{1,2}", date_to_words, text)

        return text

    def _normalize_currency(self, text: str) -> str:
        
        # Normalize currency symbols and amounts
        # "$1,234.56" → "one thousand two hundred thirty four dollars and fifty six cents"

        def currency_to_words(match):
            symbol = match.group(1)
            amount_str = match.group(2)

            try:
                # Remove commas
                amount_str = amount_str.replace(",", "")

                # Parse amount
                if "." in amount_str:
                    dollars, cents = amount_str.split(".")
                    dollars = int(dollars)
                    cents = int(cents)

                    dollar_words = num2words(dollars)
                    currency_name = self._symbol_to_currency(symbol)

                    if cents > 0:
                        cents_words = num2words(cents)
                        return f"{dollar_words} {currency_name} and {cents_words} cents"
                    else:
                        return f"{dollar_words} {currency_name}"
                else:
                    amount = int(amount_str)
                    amount_words = num2words(amount)
                    currency_name = self._symbol_to_currency(symbol)
                    return f"{amount_words} {currency_name}"

            except (ValueError, IndexError):
                return match.group(0)

        # Match currency patterns
        text = re.sub(
            r"([\$€£¥])\s*(\d+(?:,\d{3})*(?:\.\d{2})?)", currency_to_words, text
        )

        return text

    def _normalize_abbreviations(self, text: str) -> str:
        
        # Expand common abbreviations
        # "Dr." to "Doctor"
        # "e.g." to "for example"
        
        for abbrev, expansion in self.abbreviations.items():
            # Use word boundaries to avoid partial matches
            pattern = r"\b" + re.escape(abbrev) + r"\b"
            text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)

        return text

    def _normalize_time(self, text: str) -> str:
        
        # Normalize time formats
        # "3:30 PM" → "three thirty P M"
        # "09:00" → "nine o'clock"

        def time_to_words(match):
            hours, minutes = match.group(1), match.group(2)
            period = match.group(3) if match.lastindex >= 3 else None

            try:
                h = int(hours)
                m = int(minutes)

                if m == 0:
                    time_str = f"{num2words(h)} o'clock"
                else:
                    time_str = f"{num2words(h)} {num2words(m)}"

                if period:
                    time_str += f" {period.replace('.', ' ')}"

                return time_str

            except ValueError:
                return match.group(0)

        # Match time patterns
        text = re.sub(r"(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?", time_to_words, text)

        return text

    def _normalize_urls(self, text: str) -> str:
        
        # Normalize URLs to readable text
        # "https://example.com" → "link to example dot com"

        def url_to_words(match):
            url = match.group(0)
            # Extract domain
            domain_match = re.search(r"(?:https?://)?(?:www\.)?([^/]+)", url)
            if domain_match:
                domain = domain_match.group(1)
                domain = domain.replace(".", " dot ")
                return f"link to {domain}"
            return "link"

        text = re.sub(r"https?://[^\s]+", url_to_words, text)

        return text

    def _normalize_emails(self, text: str) -> str:
        
        # Normalize email addresses
        # "john@example.com" → "john at example dot com"

        def email_to_words(match):
            email = match.group(0)
            email = email.replace("@", " at ")
            email = email.replace(".", " dot ")
            return email

        text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", email_to_words, text)

        return text

    def _clean_whitespace(self, text: str) -> str:
        
        # Clean up excessive whitespace
        # Replace multiple spaces with single space
        text = re.sub(r" {2,}", " ", text)

        # Replace multiple newlines with double newline
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Trim whitespace from each line
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(lines)

        return text.strip()

    def _month_to_name(self, month: int) -> str:
        # Convert month number to name
        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
        return months[month - 1] if 1 <= month <= 12 else str(month)

    def _symbol_to_currency(self, symbol: str) -> str:
        # Convert currency symbol to name
        currencies = {
            "$": "dollars",
            "€": "euros",
            "£": "pounds",
            "¥": "yen",
        }
        return currencies.get(symbol, "units")

    def chunk_text(
        self, text: str, max_words: int = 200, overlap: int = 20
    ) -> List[str]:
        
        # Split text into overlapping chunks for TTS
        
        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", text)

        chunks = []
        current_chunk = []
        current_word_count = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())

            # Check if adding sentence exceeds max
            if current_word_count + sentence_words > max_words and current_chunk:
                # Save current chunk
                chunks.append(" ".join(current_chunk))

                # Start new chunk with overlap
                if overlap > 0 and len(current_chunk) > 0:
                    # Take last N words as overlap
                    overlap_text = " ".join(current_chunk[-overlap:])
                    current_chunk = [overlap_text, sentence]
                    current_word_count = len(overlap_text.split()) + sentence_words
                else:
                    current_chunk = [sentence]
                    current_word_count = sentence_words
            else:
                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_word_count += sentence_words

        # Add final chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        self.logger.info(f"Split text into {len(chunks)} chunks")
        return chunks

    def validate_text(self, text: str) -> Tuple[bool, Optional[str]]:

        # Validate text for TTS processing

        if not text or len(text.strip()) == 0:
            return False, "Text cannot be empty"

        if len(text) < settings.MIN_CHAPTER_LENGTH:
            return False, f"Text too short (minimum {settings.MIN_CHAPTER_LENGTH} characters)"

        if len(text) > settings.MAX_CHAPTER_LENGTH:
            return False, f"Text too long (maximum {settings.MAX_CHAPTER_LENGTH} characters)"

        return True, None


# SINGLETON INSTANCE

text_service = TextService()

__all__ = ["TextService", "text_service"]
