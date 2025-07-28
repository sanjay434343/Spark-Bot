# Ultimate Telegram Bot with Advanced Features & Weather Caching
# Install required packages:
# pip install python-telegram-bot==13.15 requests fastapi uvicorn

import os
import json
import time
import random
import logging
from typing import List, Dict, Optional
import requests
from urllib.parse import quote
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import re

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ParseMode, ChatAction, InputMediaAudio, ReplyKeyboardMarkup,
    KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Updater, MessageHandler, Filters, CallbackContext, 
    CallbackQueryHandler, CommandHandler, ConversationHandler,
    Dispatcher
)
import telegram

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🚨 Bot Configuration
TOKEN = os.getenv("TELEGRAM_TOKEN", "8289772457:AAEYnZhrwG5r_T3SI-1PkLwC2b3p1unMQUo")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "231a4048dfb482ff12c57b82adce8ee0")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://spark-bot-no0e.onrender.com/webhook")

# Global cache storage for user preferences
USER_CACHE = {}
CACHE_FILE = "user_cache.json"

class CacheManager:
    """Manage user preferences and caching"""
    
    @staticmethod
    def load_cache():
        """Load cache from file"""
        global USER_CACHE
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    USER_CACHE = json.load(f)
                logger.info(f"Cache loaded: {len(USER_CACHE)} users")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            USER_CACHE = {}
    
    @staticmethod
    def save_cache():
        """Save cache to file"""
        try:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(USER_CACHE, f, indent=2, ensure_ascii=False)
            logger.info("Cache saved successfully")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    @staticmethod
    def get_user_data(user_id: int) -> Dict:
        """Get user data from cache"""
        user_id = str(user_id)
        if user_id not in USER_CACHE:
            USER_CACHE[user_id] = {
                'weather_city': None,
                'language_preference': 'en',
                'timezone': None,
                'last_active': time.time(),
                'total_requests': 0
            }
        return USER_CACHE[user_id]
    
    @staticmethod
    def set_user_weather_city(user_id: int, city: str):
        """Set user's preferred weather city"""
        user_data = CacheManager.get_user_data(user_id)
        user_data['weather_city'] = city
        user_data['last_active'] = time.time()
        user_data['total_requests'] += 1
        CacheManager.save_cache()
    
    @staticmethod
    def get_user_weather_city(user_id: int) -> Optional[str]:
        """Get user's preferred weather city"""
        user_data = CacheManager.get_user_data(user_id)
        return user_data.get('weather_city')
    
    @staticmethod
    def update_user_activity(user_id: int):
        """Update user's last activity"""
        user_data = CacheManager.get_user_data(user_id)
        user_data['last_active'] = time.time()
        user_data['total_requests'] += 1

class UltimateBot:
    def __init__(self):
        self.jiosaavn_api = "https://jiosavan-api-with-playlist.vercel.app/api"
        self.openweather_api = "http://api.openweathermap.org/data/2.5/weather"
        
        # Movie APIs
        self.movie_apis = {
            'tmdb': 'https://api.themoviedb.org/3/search/movie',
            'omdb': 'http://www.omdbapi.com/',
            'yts': 'https://yts.mx/api/v2/list_movies.json'
        }
        
        # Emergency contacts (India)
        self.emergency_contacts = {
            'police': '100',
            'fire': '101',
            'ambulance': '102',
            'disaster': '108',
            'women_helpline': '1091',
            'child_helpline': '1098',
            'tourist_helpline': '1363',
            'railway_enquiry': '139',
            'covid_helpline': '1075'
        }
        
        # Health tips and first aid
        self.health_tips = [
            "💧 Drink at least 8 glasses of water daily",
            "🚶‍♀️ Walk for 30 minutes every day",
            "😴 Get 7-8 hours of sleep nightly",
            "🥗 Eat 5 servings of fruits and vegetables daily",
            "🧘‍♀️ Practice deep breathing for stress relief",
            "🚭 Avoid smoking and excessive alcohol",
            "🧼 Wash hands frequently with soap",
            "📱 Limit screen time before bed"
        ]
        
        self.first_aid_tips = {
            'burn': "🔥 **For Burns:** Run cool water over burn for 10-15 minutes. Don't use ice!",
            'cut': "🩹 **For Cuts:** Apply pressure with clean cloth. Elevate if possible.",
            'choking': "🫁 **For Choking:** 5 back blows between shoulder blades, then 5 abdominal thrusts.",
            'heart_attack': "❤️ **Heart Attack:** Call 102 immediately! Give aspirin if available and conscious.",
            'stroke': "🧠 **Stroke Signs:** Face drooping, arm weakness, speech difficulty. Call 102!",
            'poisoning': "☠️ **Poisoning:** Call 102. Don't induce vomiting unless instructed.",
            'allergic': "🤧 **Allergic Reaction:** Remove allergen, use antihistamine, call 102 if severe.",
            'fracture': "🦴 **Fracture:** Don't move the person. Immobilize the area. Call 102."
        }

    def get_command_keyboard(self):
        """Create keyboard with command buttons"""
        keyboard = [
            [KeyboardButton("🎵 @song"), KeyboardButton("🌤️ @weather"), KeyboardButton("😄 @joke")],
            [KeyboardButton("💭 @quote"), KeyboardButton("🎬 @movie"), KeyboardButton("🔍 @fact")],
            [KeyboardButton("🖼️ @image"), KeyboardButton("📚 @w"), KeyboardButton("❓ @help")],
            [KeyboardButton("⚙️ @settings"), KeyboardButton("📊 @stats")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    def search_jiosaavn(self, query: str) -> List[Dict]:
        """Search JioSaavn for songs"""
        try:
            url = f"{self.jiosaavn_api}/search?query={quote(query)}"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'songs' in data['data']:
                    songs = data['data']['songs'].get('results', [])
                    return self.process_jiosaavn_songs(songs)
            return []
        except Exception as e:
            logger.error(f"JioSaavn search error: {e}")
            return []
    
    def clean_title(self, title: str) -> str:
        """Clean the song title by removing brackets, special chars, and unwanted words"""
        # Remove content in brackets (including nested)
        title = re.sub(r'\(.*?\)', '', title)
        # Remove unwanted words like 'quot'
        title = title.replace('quot', '')
        # Remove extra spaces and special characters at ends
        title = re.sub(r'^[\s\W]+|[\s\W]+$', '', title)
        # Remove double spaces
        title = re.sub(r'\s+', ' ', title)
        return title.strip()

    def process_jiosaavn_songs(self, songs: List[Dict]) -> List[Dict]:
        """Process JioSaavn songs and get download links"""
        processed_songs = []
        for song in songs[:8]:
            try:
                song_id = song.get('id')
                if song_id:
                    detail_url = f"{self.jiosaavn_api}/songs/{song_id}"
                    detail_response = requests.get(detail_url, timeout=10)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        if 'data' in detail_data and detail_data['data']:
                            song_detail = detail_data['data'][0]
                            download_urls = song_detail.get('downloadUrl', [])
                            best_url = self.get_best_quality_url(download_urls)
                            if best_url:
                                # Clean title
                                clean_title = self.clean_title(song.get('title', 'Unknown'))
                                # Get primary artist (prefer song_detail if available)
                                artist = song_detail.get('primaryArtists', song.get('primaryArtists', 'Unknown Artist'))
                                processed_song = {
                                    'id': song_id,
                                    'title': clean_title,
                                    'artist': artist,
                                    'album': song.get('album', 'Unknown Album'),
                                    'duration': song.get('duration', '0'),
                                    'year': song.get('year', 'Unknown'),
                                    'language': song.get('language', 'Unknown'),
                                    'download_url': best_url,
                                    'image': self.get_best_image(song.get('image', [])),
                                    'play_count': song.get('playCount', '0'),
                                    'has_lyrics': song.get('hasLyrics', False)
                                }
                                processed_songs.append(processed_song)
            except Exception as e:
                logger.error(f"Error processing song: {e}")
                continue
        return processed_songs
    
    def get_best_quality_url(self, download_urls: List[Dict]) -> str:
        """Get the highest quality download URL"""
        if not download_urls:
            return ""
        
        quality_priority = ['320kbps', '160kbps', '96kbps', '48kbps', '12kbps']
        
        for quality in quality_priority:
            for url_data in download_urls:
                if quality in url_data.get('quality', ''):
                    return url_data.get('url', '')
        
        return download_urls[0].get('url', '') if download_urls else ""
    
    def get_best_image(self, images: List[Dict]) -> str:
        """Get the highest quality image"""
        if not images:
            return ""
        return images[-1].get('link', '') if images else ""

    def get_weather_with_openweather(self, city: str, user_id: int = None) -> str:
        """Get weather using OpenWeatherMap API with caching support"""
        try:
            # If no city provided, try to get from cache
            if not city and user_id:
                cached_city = CacheManager.get_user_weather_city(user_id)
                if cached_city:
                    city = cached_city
                else:
                    return self.get_weather_setup_message()
            elif not city:
                city = "London"  # Default fallback
            
            url = f"{self.openweather_api}?q={quote(city)}&appid={OPENWEATHER_API_KEY}&units=metric"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Save city to cache if user_id provided and city is valid
                if user_id and city.lower() != "london":
                    CacheManager.set_user_weather_city(user_id, city)
                
                weather_info = f"🌤️ **Weather in {data['name']}, {data['sys']['country']}:**\n\n"
                weather_info += f"🌡️ **Temperature:** {data['main']['temp']}°C (feels like {data['main']['feels_like']}°C)\n"
                weather_info += f"📊 **Condition:** {data['weather'][0]['description'].title()}\n"
                weather_info += f"💧 **Humidity:** {data['main']['humidity']}%\n"
                weather_info += f"🌪️ **Wind Speed:** {data['wind']['speed']} m/s\n"
                weather_info += f"👁️ **Visibility:** {data.get('visibility', 'N/A')/1000 if data.get('visibility') else 'N/A'} km\n"
                weather_info += f"🌅 **Sunrise:** {time.strftime('%H:%M', time.localtime(data['sys']['sunrise']))}\n"
                weather_info += f"🌇 **Sunset:** {time.strftime('%H:%M', time.localtime(data['sys']['sunset']))}\n"
                weather_info += f"🏢 **Pressure:** {data['main']['pressure']} hPa"
                
                # Add cache info if city was cached
                if user_id and CacheManager.get_user_weather_city(user_id):
                    weather_info += f"\n\n💾 **Saved as your default city**\n"
                    weather_info += f"🔄 Use `@weather <new_city>` to change location"
                
                # Add weather emoji based on condition
                condition = data['weather'][0]['main'].lower()
                if 'rain' in condition:
                    weather_info = "🌧️ " + weather_info
                elif 'cloud' in condition:
                    weather_info = "☁️ " + weather_info
                elif 'clear' in condition:
                    weather_info = "☀️ " + weather_info
                elif 'snow' in condition:
                    weather_info = "❄️ " + weather_info
                
                return weather_info
            elif response.status_code == 404:
                return f"⚠️ City '{city}' not found. Please check the spelling."
            else:
                return "⚠️ Could not fetch weather information."
                
        except Exception as e:
            logger.error(f"Weather API error: {e}")
            return "⚠️ Error fetching weather data."
    
    def get_weather_setup_message(self) -> str:
        """Get weather setup message for first-time users"""
        return """🌤️ **Weather Setup Required**

Welcome to the weather feature! 

**First time setup:**
• Use `@weather <your_city>` to get weather and save your location
• Example: `@weather Mumbai` or `@weather New York`

**After setup:**
• Just use `@weather` to get weather for your saved city
• Use `@weather <new_city>` to check other cities

**Features:**
✅ Auto-saves your preferred city
✅ Detailed weather information  
✅ Sunrise/sunset times
✅ Real-time data from OpenWeatherMap

Type `@weather <your_city>` to get started! 🌍"""

    def search_movies(self, query: str) -> List[Dict]:
        """Search for movies across multiple sources"""
        movies = []
        
        try:
            # Search YTS for torrents
            yts_url = f"https://yts.mx/api/v2/list_movies.json?query_term={quote(query)}&limit=5"
            response = requests.get(yts_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'ok' and 'movies' in data['data']:
                    for movie in data['data']['movies']:
                        movie_info = {
                            'title': movie.get('title', 'Unknown'),
                            'year': movie.get('year', 'Unknown'),
                            'rating': movie.get('rating', 'N/A'),
                            'genres': ', '.join(movie.get('genres', [])),
                            'runtime': f"{movie.get('runtime', 0)} min",
                            'summary': movie.get('summary', 'No summary available')[:200] + "...",
                            'poster': movie.get('large_cover_image', ''),
                            'torrents': movie.get('torrents', []),
                            'imdb_code': movie.get('imdb_code', ''),
                            'source': 'YTS'
                        }
                        movies.append(movie_info)
        except Exception as e:
            logger.error(f"YTS search error: {e}")
        
        return movies

    def get_joke(self) -> str:
        """Get a random joke"""
        joke_apis = [
            "https://official-joke-api.appspot.com/random_joke",
            "https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,religious,political,racist,sexist,explicit"
        ]
        
        for api_url in joke_apis:
            try:
                response = requests.get(api_url, timeout=8)
                if response.status_code == 200:
                    joke_data = response.json()
                    
                    if 'setup' in joke_data and 'punchline' in joke_data:
                        return f"😄 **Random Joke:**\n\n*{joke_data['setup']}*\n\n**{joke_data['punchline']}**"
                    elif 'joke' in joke_data:
                        return f"😄 **Random Joke:**\n\n{joke_data['joke']}"
                    elif joke_data['type'] == 'single':
                        return f"😄 **Random Joke:**\n\n{joke_data['joke']}"
                    else:
                        return f"😄 **Random Joke:**\n\n*{joke_data['setup']}*\n\n**{joke_data['delivery']}**"
            except:
                continue
        
        fallback_jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "I told my wife she was drawing her eyebrows too high. She looked surprised.",
            "Why don't eggs tell jokes? They'd crack each other up!"
        ]
        return f"😄 **Random Joke:**\n\n{random.choice(fallback_jokes)}"

    def get_quote(self) -> str:
        """Get an inspirational quote"""
        try:
            response = requests.get("https://api.quotable.io/random", timeout=8)
            if response.status_code == 200:
                quote_data = response.json()
                return f"💭 **Quote of the Day:**\n\n*\"{quote_data['content']}\"*\n\n— **{quote_data['author']}**"
        except:
            pass
        
        fallback_quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
            ("Life is what happens when you're busy making other plans.", "John Lennon")
        ]
        quote, author = random.choice(fallback_quotes)
        return f"💭 **Inspirational Quote:**\n\n*\"{quote}\"*\n\n— **{author}**"

    def get_user_stats(self, user_id: int) -> str:
        """Get user statistics"""
        user_data = CacheManager.get_user_data(user_id)
        
        stats_text = "📊 **Your Bot Statistics:**\n\n"
        stats_text += f"🎯 **Total Requests:** {user_data.get('total_requests', 0)}\n"
        
        if user_data.get('weather_city'):
            stats_text += f"🌤️ **Saved Weather City:** {user_data['weather_city']}\n"
        else:
            stats_text += f"🌤️ **Weather City:** Not set\n"
        
        last_active = user_data.get('last_active', time.time())
        last_active_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(last_active))
        stats_text += f"🕐 **Last Active:** {last_active_str}\n"
        
        stats_text += f"🌐 **Language:** {user_data.get('language_preference', 'English')}\n"
        
        stats_text += "\n**Available Commands:**\n"
        stats_text += "• `@settings` - Manage preferences\n"
        stats_text += "• `@weather reset` - Reset weather city\n"
        stats_text += "• `@help` - Show all commands"
        
        return stats_text

bot = UltimateBot()

def start_command(update: Update, context: CallbackContext):
    """Send start message with bot capabilities"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    help_text = """
🤖 **Ultimate Multi-Feature Bot** 🤖

Welcome! I'm your all-in-one assistant with advanced features.

**🎵 Music & Entertainment:**
• Music search and download
• Movie search with download links
• Jokes, quotes, and facts

**🌍 Information & Utilities:**
• Real-time weather data (with city memory!)
• Wikipedia search
• AI image generation

**✨ New Features:**
• Weather city caching - Set once, use always!
• User statistics and preferences
• Enhanced command keyboard

Type `@help` for detailed command list.
    """
    keyboard = bot.get_command_keyboard()
    update.message.reply_text(
        help_text, 
        parse_mode=ParseMode.MARKDOWN, 
        reply_markup=keyboard
    )

def help_command(update: Update, context: CallbackContext):
    """Show detailed help"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    help_text = """
📖 **Detailed Command Guide**

**🎵 MUSIC COMMANDS:**
• `@song <name>` - Search and download songs

**🎬 MOVIE COMMANDS:**
• `@movie <name>` - Search movies with download links

**🌤️ WEATHER COMMANDS:**
• `@weather <city>` - Get weather & save city (first time)
• `@weather` - Get weather for saved city
• `@weather reset` - Reset saved city

**😄 FUN COMMANDS:**
• `@joke` - Random jokes
• `@quote` - Inspirational quotes
• `@fact` - Random interesting facts

**🔍 INFORMATION:**
• `@w <topic>` - Wikipedia summaries
• `@image <prompt>` - AI image generation

**⚙️ SETTINGS & STATS:**
• `@settings` - Manage your preferences
• `@stats` - View your usage statistics

**💬 REGULAR CHAT:**
• Just type normally for AI conversation

Need help? Just ask me anything! 😊
    """
    update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

CHANGE_WEATHER_CITY = range(1)

def weather_city_callback(update: Update, context: CallbackContext):
    """Handle weather city change/reset via button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    data = query.data

    if data == "change_weather_city" or data == "set_weather_city":
        query.message.reply_text(
            "🌍 Please send your new city name to set as your default for weather updates.",
            parse_mode=ParseMode.MARKDOWN
        )
        # Set a flag in user_data to expect city name next
        context.user_data['awaiting_weather_city'] = True
        return CHANGE_WEATHER_CITY

    elif data == "reset_weather_city":
        user_data = CacheManager.get_user_data(user_id)
        user_data['weather_city'] = None
        CacheManager.save_cache()
        query.message.reply_text(
            "🌤️ Your saved weather city has been reset.\n\nUse `@weather <city>` to set a new default city.",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data['awaiting_weather_city'] = False
        return ConversationHandler.END

    elif data == "view_stats":
        stats_text = bot.get_user_stats(user_id)
        query.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    return ConversationHandler.END

def handle_new_weather_city(update: Update, context: CallbackContext):
    """Handle user reply for new weather city after button click"""
    user_id = update.effective_user.id
    city_name = update.message.text.strip()
    if len(city_name) < 2:
        update.message.reply_text("🌍 Please provide a valid city name.")
        return CHANGE_WEATHER_CITY
    CacheManager.set_user_weather_city(user_id, city_name)
    update.message.reply_text(f"🌤️ Your default weather city has been set to: {city_name}")
    context.user_data['awaiting_weather_city'] = False
    return ConversationHandler.END

def media_logger(update: Update, context: CallbackContext):
    """Enhanced media and message handler with caching"""
    try:
        user_id = update.effective_user.id
        CacheManager.update_user_activity(user_id)
        
        # Handle reply for new weather city
        if context.user_data.get('awaiting_weather_city'):
            return handle_new_weather_city(update, context)
        
        if update.message and update.message.text:
            prompt = update.message.text.strip()
            
            # Help command
            if prompt in ["@help", "❓ @help"]:
                help_command(update, context)
                return
            
            # Settings command
            elif prompt in ["@settings", "⚙️ @settings"]:
                user_data = CacheManager.get_user_data(user_id)
                settings_text = "⚙️ **Bot Settings:**\n\n"
                
                if user_data.get('weather_city'):
                    settings_text += f"🌤️ **Weather City:** {user_data['weather_city']}\n"
                    keyboard = [
                        [InlineKeyboardButton("🌍 Change Weather City", callback_data="change_weather_city")],
                        [InlineKeyboardButton("🗑️ Reset Weather City", callback_data="reset_weather_city")],
                        [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")]
                    ]
                else:
                    settings_text += f"🌤️ **Weather City:** Not set\n"
                    keyboard = [
                        [InlineKeyboardButton("🌍 Set Weather City", callback_data="set_weather_city")],
                        [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")]
                    ]
                
                settings_text += f"🎯 **Total Requests:** {user_data.get('total_requests', 0)}\n"
                settings_text += f"🌐 **Language:** {user_data.get('language_preference', 'English')}\n\n"
                settings_text += "Click the buttons below to modify your settings:"
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text(settings_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                return
            
            # Stats command
            elif prompt in ["@stats", "📊 @stats"]:
                stats_text = bot.get_user_stats(user_id)
                update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
                return
            
            # Music search
            elif prompt.startswith("@song") or prompt.startswith("🎵 @song"):
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                
                song_query = prompt.replace("🎵 @song", "").replace("@song", "").strip()
                if not song_query:
                    update.message.reply_text("🎵 Please provide a song name!\n\n**Example:** `@song Kesariya`", parse_mode=ParseMode.MARKDOWN)
                    return
                
                update.message.reply_text(f"🔍 **Searching:** `{song_query}`", parse_mode=ParseMode.MARKDOWN)
                
                songs = bot.search_jiosaavn(song_query)
                
                if not songs:
                    update.message.reply_text("😔 No songs found. Try a different search term.")
                    return
                
                keyboard = []
                for i, song in enumerate(songs):
                    button_text = f"🎵 {song['title'][:30]}{'...' if len(song['title']) > 30 else ''}"
                    keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_song:{i}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                context.user_data['songs'] = songs
                
                result_text = f"🎵 **Found {len(songs)} songs:**\n\n"
                for i, song in enumerate(songs[:3]):
                    result_text += f"**{i+1}.** {song['title']}\n   👤 {song['artist']}\n   💿 {song['album']}\n\n"
                
                if len(songs) > 3:
                    result_text += f"*...and {len(songs)-3} more*\n\n"
                
                result_text += "🎧 **Click to download:**"
                update.message.reply_text(result_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            
            # Movie search
            elif prompt.startswith("@movie") or prompt.startswith("🎬 @movie"):
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                
                movie_query = prompt.replace("🎬 @movie", "").replace("@movie", "").strip()
                if not movie_query:
                    update.message.reply_text("🎬 Please provide a movie name!\n\n**Example:** `@movie Avengers`", parse_mode=ParseMode.MARKDOWN)
                    return
                
                update.message.reply_text(f"🔍 **Searching movies:** `{movie_query}`", parse_mode=ParseMode.MARKDOWN)
                
                movies = bot.search_movies(movie_query)
                
                if not movies:
                    update.message.reply_text("😔 No movies found. Try a different search term.")
                    return
                
                for movie in movies[:3]:  # Show top 3 results
                    movie_text = f"🎬 **{movie['title']} ({movie['year']})**\n\n"
                    movie_text += f"⭐ **Rating:** {movie['rating']}/10\n"
                    movie_text += f"🎭 **Genres:** {movie['genres']}\n"
                    movie_text += f"⏱️ **Runtime:** {movie['runtime']}\n\n"
                    movie_text += f"📖 **Summary:** {movie['summary']}\n\n"
                    
                    # Add download links
                    if movie['torrents']:
                        movie_text += "📥 **Download Options:**\n"
                        for torrent in movie['torrents']:
                            quality = torrent.get('quality', 'Unknown')
                            size = torrent.get('size', 'Unknown')
                            movie_text += f"• **{quality}** ({size}) - [Magnet Link](magnet:?xt=urn:btih:{torrent.get('hash', '')})\n"
                    
                    keyboard = []
                    if movie['imdb_code']:
                        keyboard.append([InlineKeyboardButton("🎭 View on IMDb", url=f"https://www.imdb.com/title/{movie['imdb_code']}")])
                    
                    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                    
                    if movie['poster']:
                        try:
                            update.message.reply_photo(
                                photo=movie['poster'],
                                caption=movie_text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=reply_markup
                            )
                        except:
                            update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
                    else:
                        update.message.reply_text(movie_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            
            # Enhanced Weather with Caching
            elif prompt.startswith("@weather") or prompt.startswith("🌤️ @weather"):
                context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                
                weather_query = prompt.replace("🌤️ @weather", "").replace("@weather", "").strip()
                
                # Handle weather reset
                if weather_query.lower() == "reset":
                    user_data = CacheManager.get_user_data(user_id)
                    user_data['weather_city'] = None
                    CacheManager.save_cache()
                    update.message.reply_text(
                        "🌤️ Your saved weather city has been reset.\n\nUse `@weather <city>` to set a new default city.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return

                # If user provides a city, fetch and cache it
                if weather_query:
                    weather_info = bot.get_weather_with_openweather(weather_query, user_id)
                    update.message.reply_text(weather_info, parse_mode=ParseMode.MARKDOWN)
                    return

                # If no city provided, try to get from cache
                cached_city = CacheManager.get_user_weather_city(user_id)
                if cached_city:
                    weather_info = bot.get_weather_with_openweather(cached_city, user_id)
                    update.message.reply_text(weather_info, parse_mode=ParseMode.MARKDOWN)
                else:
                    setup_msg = bot.get_weather_setup_message()
                    update.message.reply_text(setup_msg, parse_mode=ParseMode.MARKDOWN)
                return

    except Exception as e:
        logger.error(f"Media logger error: {e}")
        update.message.reply_text("❌ Error processing your request. Please try again.")

# Command handlers
def song_command(update: Update, context: CallbackContext):
    """Handle song search and download"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    prompt = update.message.text.strip()
    media_logger(update, context)

def weather_command(update: Update, context: CallbackContext):
    """Handle weather requests"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    prompt = update.message.text.strip()
    
    # Directly call media_logger to handle weather as well
    media_logger(update, context)

def joke_command(update: Update, context: CallbackContext):
    """Send a random joke"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    joke = bot.get_joke()
    update.message.reply_text(joke, parse_mode=ParseMode.MARKDOWN)

def quote_command(update: Update, context: CallbackContext):
    """Send an inspirational quote"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    quote = bot.get_quote()
    update.message.reply_text(quote, parse_mode=ParseMode.MARKDOWN)

def movie_command(update: Update, context: CallbackContext):
    """Handle movie search"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    prompt = update.message.text.strip()
    media_logger(update, context)

def w_command(update: Update, context: CallbackContext):
    """Handle Wikipedia search"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    prompt = update.message.text.strip()
    
    if len(prompt) < 3:
        update.message.reply_text("🔍 Please provide a longer search term for Wikipedia.")
        return
    
    try:
        url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&list=search&srsearch={quote(prompt)}&utf8=1"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            search_results = data.get('query', {}).get('search', [])
            
            if not search_results:
                update.message.reply_text("🔍 No results found on Wikipedia.")
                return
            
            # Prepare the message with search results
            results_text = "🔍 **Wikipedia Search Results:**\n\n"
            for result in search_results[:5]:  # Limit to top 5 results
                title = result['title']
                snippet = result['snippet']
                page_id = result['pageid']
                
                # Add result to the message
                results_text += f"• [{title}](https://en.wikipedia.org/?curid={page_id})\n  {snippet}...\n\n"
            
            results_text += "🔗 Click on the titles to read more on Wikipedia."
            update.message.reply_text(results_text, parse_mode=ParseMode.MARKDOWN)
        else:
            update.message.reply_text("⚠️ Error fetching data from Wikipedia.")
    except Exception as e:
        logger.error(f"Wikipedia search error: {e}")
        update.message.reply_text("⚠️ Error processing your request.")

def image_command(update: Update, context: CallbackContext):
    """Handle AI image generation"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    prompt = update.message.text.strip()
    
    if len(prompt) < 3:
        update.message.reply_text("🖼️ Please provide a description for the image.")
        return
    
    try:
        # Call to an AI image generation API (placeholder)
        response = requests.post("https://api.example.com/generate-image", json={"prompt": prompt}, timeout=10)
        
        if response.status_code == 200:
            image_url = response.json().get('image_url')
            update.message.reply_photo(photo=image_url, caption="🖼️ Here is your generated image:")
        else:
            update.message.reply_text("⚠️ Error generating image.")
    except Exception as e:
        logger.error(f"Image generation error: {e}")
        update.message.reply_text("⚠️ Error processing your request.")

def health_command(update: Update, context: CallbackContext):
    """Send health tips"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    tips = bot.health_tips
    health_text = "💊 **Health Tips:**\n\n"
    health_text += "\n".join([f"• {tip}" for tip in tips])
    
    health_text += "\n\n🏥 **For emergencies, use `@emergency` to get contact numbers.**"
    update.message.reply_text(health_text, parse_mode=ParseMode.MARKDOWN)

def settings_command(update: Update, context: CallbackContext):
    """Handle settings management"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    if context.args and len(context.args) > 0:
        sub_command = context.args[0]
        
        if sub_command == "change_weather_city":
            # Change weather city flow
            update.message.reply_text(
                "🌍 **Change Weather City**\n\nSend your new city name to set as default for weather updates.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        elif sub_command == "reset_weather_city":
            # Reset weather city
            user_data = CacheManager.get_user_data(user_id)
            user_data['weather_city'] = None
            CacheManager.save_cache()
            update.message.reply_text(
                "🌤️ Your weather city has been reset. You can set a new city using `@weather <city>`.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        elif sub_command == "view_stats":
            # View user statistics
            stats_text = bot.get_user_stats(user_id)
            update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)
            return
    
    # Default settings response
    user_data = CacheManager.get_user_data(user_id)
    settings_text = "⚙️ **Bot Settings:**\n\n"
    
    if user_data.get('weather_city'):
        settings_text += f"🌤️ **Weather City:** {user_data['weather_city']}\n"
        keyboard = [
            [InlineKeyboardButton("🌍 Change Weather City", callback_data="change_weather_city")],
            [InlineKeyboardButton("🗑️ Reset Weather City", callback_data="reset_weather_city")],
            [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")]
        ]
    else:
        settings_text += f"🌤️ **Weather City:** Not set\n"
        keyboard = [
            [InlineKeyboardButton("🌍 Set Weather City", callback_data="set_weather_city")],
            [InlineKeyboardButton("📊 View Statistics", callback_data="view_stats")]
        ]
    
    settings_text += f"🎯 **Total Requests:** {user_data.get('total_requests', 0)}\n"
    settings_text += f"🌐 **Language:** {user_data.get('language_preference', 'English')}\n\n"
    settings_text += "Click the buttons below to modify your settings:"
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(settings_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

def set_weather_city_command(update: Update, context: CallbackContext):
    """Set the weather city"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    if context.args and len(context.args) > 0:
        city_name = " ".join(context.args)
        
        # Validate city name (basic validation)
        if len(city_name) < 2:
            update.message.reply_text("🌍 Please provide a valid city name.")
            return
        
        # Set city in cache
        CacheManager.set_user_weather_city(user_id, city_name)
        update.message.reply_text(f"🌤️ Your default weather city has been set to: {city_name}")
    else:
        update.message.reply_text("🌍 Please provide a city name.\n\nUsage: `@weather set <city_name>`")

def reset_weather_city_command(update: Update, context: CallbackContext):
    """Reset the weather city"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    # Reset city in cache
    user_data = CacheManager.get_user_data(user_id)
    user_data['weather_city'] = None
    CacheManager.save_cache()
    
    update.message.reply_text("🌤️ Your weather city has been reset. You can set a new city using `@weather <city>`.")

def view_stats_command(update: Update, context: CallbackContext):
    """View user statistics"""
    user_id = update.effective_user.id
    CacheManager.update_user_activity(user_id)
    
    stats_text = bot.get_user_stats(user_id)
    update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

def song_download_callback(update: Update, context: CallbackContext):
    """Handle song result button click, show variants, and send file"""
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    data = query.data

    # Expect callback_data like "download_song:0"
    if data.startswith("download_song:"):
        idx = int(data.split(":")[1])
        songs = context.user_data.get('songs', [])
        if idx < 0 or idx >= len(songs):
            query.message.reply_text("❌ Song not found.")
            return

        song = songs[idx]
        # Show all available variants (qualities/languages)
        download_urls = []
        # Fetch fresh details to get all variants
        try:
            detail_url = f"https://jiosavan-api-with-playlist.vercel.app/api/songs/{song['id']}"
            detail_response = requests.get(detail_url, timeout=10)
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                if 'data' in detail_data and detail_data['data']:
                    song_detail = detail_data['data'][0]
                    download_urls = song_detail.get('downloadUrl', [])
        except Exception as e:
            logger.error(f"Error fetching song details for variants: {e}")

        if not download_urls:
            query.message.reply_text("❌ No download links found for this song.")
            return

        # Show all variants as buttons
        keyboard = []
        for i, url_data in enumerate(download_urls):
            quality = url_data.get('quality', 'Unknown')
            language = url_data.get('language', song.get('language', 'Unknown'))
            button_text = f"{quality} ({language})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"download_file:{song['id']}:{i}")])

        reply_text = f"🎵 **{song['title']}**\n👤 {song['artist']}\n💿 {song['album']}\n\nSelect a file variant to download:"
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        return

    # Expect callback_data like "download_file:<song_id>:<variant_idx>"
    if data.startswith("download_file:"):
        parts = data.split(":")
        song_id = parts[1]
        variant_idx = int(parts[2])

        try:
            detail_url = f"https://jiosavan-api-with-playlist.vercel.app/api/songs/{song_id}"
            detail_response = requests.get(detail_url, timeout=10)
            if detail_response.status_code == 200:
                detail_data = detail_response.json()
                if 'data' in detail_data and detail_data['data']:
                    song_detail = detail_data['data'][0]
                    download_urls = song_detail.get('downloadUrl', [])
                    if 0 <= variant_idx < len(download_urls):
                        file_url = download_urls[variant_idx].get('url')
                        quality = download_urls[variant_idx].get('quality', 'Unknown')
                        # Get and clean title from song_detail, fallback to 'No Title'
                        title = song_detail.get('title')
                        if not title or not title.strip():
                            title = 'No Title'
                        clean_title = re.sub(r'\(.*?\)', '', title)
                        clean_title = clean_title.replace('&quot;', '').replace('quot', '')
                        clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                        if not clean_title:
                            clean_title = 'No Title'
                        # Get artist from song_detail, fallback to 'No Artist'
                        artist = song_detail.get('primaryArtists')
                        if not artist or not artist.strip():
                            artist = 'No Artist'
                        year = song_detail.get('year', 'Unknown')
                        safe_caption = (
                            f"🎵 {clean_title}\n"
                            f"👤 {artist}\n"
                            f"🎚️ Quality: {quality}\n"
                            f"📅 Year: {year}"
                        )
                        query.message.reply_audio(audio=file_url, caption=safe_caption, parse_mode=None)
                        return
        except Exception as e:
            logger.error(f"Error sending song file: {e}")
        query.message.reply_text("❌ Could not download this file.")
        return

# FastAPI app
app = FastAPI()

# Telegram bot and dispatcher setup
bot_instance = telegram.Bot(token=TOKEN)
dispatcher = Dispatcher(bot_instance, None, workers=0, use_context=True)

# Register handlers (same as in main())
def setup_handlers():
    CacheManager.load_cache()
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(CommandHandler("song", song_command))
    dispatcher.add_handler(CommandHandler("weather", weather_command))
    dispatcher.add_handler(CommandHandler("joke", joke_command))
    dispatcher.add_handler(CommandHandler("quote", quote_command))
    dispatcher.add_handler(CommandHandler("movie", movie_command))
    dispatcher.add_handler(CommandHandler("w", w_command))
    dispatcher.add_handler(CommandHandler("image", image_command))
    dispatcher.add_handler(CommandHandler("health", health_command))
    dispatcher.add_handler(CommandHandler("settings", settings_command))
    dispatcher.add_handler(CommandHandler("set_weather_city", set_weather_city_command))
    dispatcher.add_handler(CommandHandler("reset_weather_city", reset_weather_city_command))
    dispatcher.add_handler(CommandHandler("view_stats", view_stats_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, media_logger))
    dispatcher.add_handler(CallbackQueryHandler(weather_city_callback, pattern="^(change_weather_city|set_weather_city|reset_weather_city|view_stats)$"))
    dispatcher.add_handler(CallbackQueryHandler(song_download_callback, pattern="^(download_song:|download_file:)"))
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(weather_city_callback, pattern="^(change_weather_city|set_weather_city|reset_weather_city|view_stats)$")],
        states={
            CHANGE_WEATHER_CITY: [MessageHandler(Filters.text & ~Filters.command, handle_new_weather_city)]
        },
        fallbacks=[],
        allow_reentry=True
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(lambda update, context: logger.error(f"Update {update} caused error {context.error}"))

setup_handlers()

@app.get("/")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        update = Update.de_json(data, bot_instance)
        dispatcher.process_update(update)
        return JSONResponse({"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# Set webhook on startup
@app.on_event("startup")
async def on_startup():
    try:
        bot_instance.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

# To run: `uvicorn main:app --host 0.0.0.0 --port 8000`
