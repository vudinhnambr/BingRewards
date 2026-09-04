import random
import requests
from typing import List

FALLBACK_KEYWORDS = [
    "artificial intelligence trends", "machine learning in 2026", "latest tech news",
    "healthy breakfast recipes", "easy dinner ideas", "vietnam tourism destinations",
    "top rated movies this year", "space exploration news", "quantum computing basics",
    "how does solar energy work", "tips for better sleep", "python programming tips",
    "electric vehicles comparison", "world history facts", "deep sea creatures",
    "healthy meal prep ideas", "best productivity apps", "mindfulness meditation benefits",
    "renewable energy innovations", "cybersecurity best practices", "james webb telescope images",
    "ancient civilizations mysteries", "climate change solutions", "gardening for beginners",
    "financial planning tips", "stock market basics", "cloud computing advantages",
    "famous philosophy quotes", "astronomy discoveries", "daily workout routine",
    "how to learn a new language", "best podcasts to listen to", "greatest inventions in history",
    "how do airplane wings work", "nutrition facts about vegetables", "origami step by step",
    "national parks travel guide", "coffee brewing methods", "photography composition tips",
    "history of internet", "space station live stream", "marathon training plan",
    "mind mapping techniques", "history of cinema", "fastest animals in the world",
    "greenhouse effect explained", "human anatomy basics", "architecture styles through time"
]

QUESTION_TEMPLATES = [
    "what is the definition of {word}",
    "how does {word} work",
    "best examples of {word}",
    "history of {word}",
    "latest news about {word}",
    "why is {word} important",
    "benefits of {word}",
    "interesting facts about {word}",
    "guide to {word}",
    "top 10 {word}"
]

TOPICS = [
    "astronomy", "biology", "robotics", "cooking", "travel", "psychology",
    "architecture", "cybersecurity", "quantum physics", "marine biology",
    "renewable energy", "ancient history", "digital photography", "economics",
    "graphic design", "gardening", "creative writing", "world geography"
]

class WordGenerator:
    """Generates natural search queries for Bing."""

    @staticmethod
    def get_google_trends() -> List[str]:
        """Fetch trending searches from Google Trends RSS if possible."""
        try:
            url = "https://trends.google.com/trending/rss?geo=US"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(resp.content)
                titles = [item.find("title").text for item in root.findall(".//item") if item.find("title") is not None]
                if titles:
                    return [t.strip() for t in titles if t]
        except Exception:
            pass
        return []

    @classmethod
    def generate_words(cls, count: int) -> List[str]:
        """Generate a list of search queries."""
        words: List[str] = []
        
        # Try fetching trends first
        trends = cls.get_google_trends()
        if trends:
            random.shuffle(trends)
            words.extend(trends[:count // 2])

        # Fill the rest with dynamic queries and fallbacks
        pool = list(FALLBACK_KEYWORDS)
        random.shuffle(pool)
        
        for p in pool:
            if len(words) >= count:
                break
            words.append(p)

        # If still need more, generate from templates
        while len(words) < count:
            topic = random.choice(TOPICS)
            template = random.choice(QUESTION_TEMPLATES)
            words.append(template.format(word=topic))

        # Shuffle to make sequence varied
        random.shuffle(words)
        return words[:count]
