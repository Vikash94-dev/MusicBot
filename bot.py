import asyncio
import os
import logging
from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatType
import config
from utils.youtube import YouTubeAPI
from utils.database import init_db, get_chat_settings, set_chat_settings
from utils.formatters import time_to_seconds, format_duration
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize bot client
if config.STRING_SESSION:
    # Use user account session
    app = Client(
        "music_bot_user",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        session_string=config.STRING_SESSION
    )
else:
    # Use bot token
    app = Client(
        "music_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN
    )

youtube = YouTubeAPI()

# Global state for music queue and downloads
music_queue = {}
chat_downloads = {}

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Start command handler"""
    welcome_text = """
🎵 **Welcome to Music Bot!**

I can download and share music from YouTube! Here are my commands:

📻 **Music Commands:**
• `/play` - Download and send a song from YouTube
• `/video` - Download and send video from YouTube
• `/search` - Search for music on YouTube
• `/queue` - Show download queue

🎧 **Download Commands:**
• `/audio` - Download audio only
• `/mp4` - Download video in MP4 format
• `/formats` - Show available download formats

⚙️ **Other Commands:**
• `/help` - Show this help message

**Usage:** Just type `/play [song name]` or `/play [YouTube URL]`
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add to Group", url="https://t.me/your_bot_username?startgroup=true")],
        [InlineKeyboardButton("Support", url="https://t.me/your_support_chat")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=keyboard)

@app.on_message(filters.command("play"))
async def play_command(client: Client, message: Message):
    """Download and send music"""
    chat_id = message.chat.id
    
    # Get the song query
    query = ""
    if len(message.command) > 1:
        query = " ".join(message.command[1:])
    elif message.reply_to_message:
        if message.reply_to_message.text:
            query = message.reply_to_message.text
        elif message.reply_to_message.caption:
            query = message.reply_to_message.caption
    
    if not query:
        return await message.reply_text("❌ Please provide a song name or YouTube URL!\n\nExample: `/play Despacito`")
    
    status_msg = await message.reply_text("🔍 **Searching for music...**")
    
    try:
        # Check if it's a YouTube URL
        if await youtube.exists(query):
            # Direct YouTube link
            await download_and_send_audio(client, message, query, status_msg)
        else:
            # Search for the song
            search_results = await youtube.search(query, limit=5)
            
            if not search_results:
                return await status_msg.edit_text("❌ No results found for your search.")
            
            # Create inline keyboard for song selection
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    f"🎵 {result['title'][:50]}{'...' if len(result['title']) > 50 else ''} [{result['duration']}]",
                    callback_data=f"download_audio_{result['id']}"
                )] for result in search_results[:5]
            ])
            
            await status_msg.edit_text(
                f"🎵 **Search Results for:** `{query}`\n\nSelect a song to download:",
                reply_markup=keyboard
            )
    
    except Exception as e:
        logger.error(f"Play command error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command("video"))
async def video_command(client: Client, message: Message):
    """Download and send video"""
    chat_id = message.chat.id
    
    # Get the video query
    query = ""
    if len(message.command) > 1:
        query = " ".join(message.command[1:])
    elif message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text
    
    if not query:
        return await message.reply_text("❌ Please provide a YouTube URL!\n\nExample: `/video https://youtube.com/watch?v=...`")
    
    if not await youtube.exists(query):
        return await message.reply_text("❌ Please provide a valid YouTube URL!")
    
    status_msg = await message.reply_text("📹 **Downloading video...**")
    
    try:
        await download_and_send_video(client, message, query, status_msg)
    except Exception as e:
        logger.error(f"Video command error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

@app.on_callback_query(filters.regex(r"download_audio_(.+)"))
async def download_audio_callback(client: Client, callback_query):
    """Handle audio download from search results"""
    video_id = callback_query.data.split("_", 2)[2]
    chat_id = callback_query.message.chat.id
    
    try:
        await callback_query.answer("Downloading...")
        
        # Get video URL
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        await download_and_send_audio(client, callback_query.message, video_url, callback_query.message)
        
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        await callback_query.message.edit_text(f"❌ **Error:** {str(e)}")

@app.on_callback_query(filters.regex(r"download_video_(.+)"))
async def download_video_callback(client: Client, callback_query):
    """Handle video download from search results"""
    video_id = callback_query.data.split("_", 2)[2]
    chat_id = callback_query.message.chat.id
    
    try:
        await callback_query.answer("Downloading...")
        
        # Get video URL
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        await download_and_send_video(client, callback_query.message, video_url, callback_query.message)
        
    except Exception as e:
        logger.error(f"Video download error: {e}")
        await callback_query.message.edit_text(f"❌ **Error:** {str(e)}")

async def download_and_send_audio(client: Client, message: Message, url: str, status_msg: Message):
    """Download and send audio file"""
    try:
        # Update status
        await status_msg.edit_text("⬇️ **Downloading audio...**")
        
        # Get track details
        track_info, video_id = await youtube.track(url)
        
        # Download audio
        downloaded_file, direct = await youtube.download(url, None)
        
        if not downloaded_file:
            return await status_msg.edit_text("❌ **Download failed!**")
        
        # Update status
        await status_msg.edit_text("📤 **Uploading audio...**")
        
        # Send audio file
        await client.send_audio(
            message.chat.id,
            downloaded_file,
            caption=f"🎵 **{track_info['title']}**\n⏱ Duration: {track_info['duration_min']}\n👤 Requested by: {message.from_user.first_name}",
            title=track_info['title'],
            duration=time_to_seconds(track_info['duration_min']),
            thumb=track_info['thumb'],
            reply_to_message_id=message.id
        )
        
        # Delete status message
        await status_msg.delete()
        
        # Clean up downloaded file if it's a local file
        if direct and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        await status_msg.edit_text(f"❌ **Download failed:** {str(e)}")

async def download_and_send_video(client: Client, message: Message, url: str, status_msg: Message):
    """Download and send video file"""
    try:
        # Update status
        await status_msg.edit_text("⬇️ **Downloading video...**")
        
        # Get track details
        track_info, video_id = await youtube.track(url)
        
        # Download video
        downloaded_file, direct = await youtube.download(url, None, video=True)
        
        if not downloaded_file:
            return await status_msg.edit_text("❌ **Video download failed!**")
        
        # Update status
        await status_msg.edit_text("📤 **Uploading video...**")
        
        # Send video file
        await client.send_video(
            message.chat.id,
            downloaded_file,
            caption=f"📹 **{track_info['title']}**\n⏱ Duration: {track_info['duration_min']}\n👤 Requested by: {message.from_user.first_name}",
            duration=time_to_seconds(track_info['duration_min']),
            thumb=track_info['thumb'],
            reply_to_message_id=message.id
        )
        
        # Delete status message
        await status_msg.delete()
        
        # Clean up downloaded file if it's a local file
        if direct and os.path.exists(downloaded_file):
            try:
                os.remove(downloaded_file)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Video download error: {e}")
        await status_msg.edit_text(f"❌ **Video download failed:** {str(e)}")

@app.on_message(filters.command("search"))
async def search_command(client: Client, message: Message):
    """Search YouTube and show results"""
    if len(message.command) < 2:
        return await message.reply_text("❌ Please provide a search query!\n\nExample: `/search Despacito`")
    
    query = " ".join(message.command[1:])
    status_msg = await message.reply_text("🔍 **Searching YouTube...**")
    
    try:
        search_results = await youtube.search(query, limit=10)
        
        if not search_results:
            return await status_msg.edit_text("❌ No results found for your search.")
        
        # Create results text
        results_text = f"🎵 **Search Results for:** `{query}`\n\n"
        
        keyboard_buttons = []
        for i, result in enumerate(search_results[:5], 1):
            results_text += f"{i}. **{result['title'][:40]}{'...' if len(result['title']) > 40 else ''}**\n"
            results_text += f"   ⏱ {result['duration']} | 👁 {result['views']}\n"
            results_text += f"   📺 {result['channel']}\n\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(f"🎵 Download Audio #{i}", callback_data=f"download_audio_{result['id']}"),
                InlineKeyboardButton(f"📹 Download Video #{i}", callback_data=f"download_video_{result['id']}")
            ])
        
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
        await status_msg.edit_text(results_text, reply_markup=keyboard)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await status_msg.edit_text(f"❌ **Search failed:** {str(e)}")

@app.on_message(filters.command("queue"))
async def queue_command(client: Client, message: Message):
    """Show download queue status"""
    chat_id = message.chat.id
    
    queue_text = "📋 **Download Queue Status:**\n\n"
    
    if chat_id in chat_downloads and chat_downloads[chat_id]:
        for i, item in enumerate(chat_downloads[chat_id], 1):
            queue_text += f"{i}. {item['title'][:30]}{'...' if len(item['title']) > 30 else ''}\n"
            queue_text += f"   Status: {item['status']}\n\n"
    else:
        queue_text += "📭 **No downloads in queue**"
    
    await message.reply_text(queue_text)

@app.on_message(filters.command("help"))
async def help_command(client: Client, message: Message):
    """Help command handler"""
    help_text = """
🎵 **Music Bot Help**

**Download Commands:**
• `/play [song name]` - Download and send audio
• `/play [YouTube URL]` - Download from YouTube link
• `/video [YouTube URL]` - Download and send video
• `/search [query]` - Search YouTube and download

**Queue Management:**
• `/queue` - Show download queue status
• `/formats [URL]` - Show available download formats

**How to use:**
1. Add me to your group
2. Use `/play [song name]` to download music
3. Use `/video [URL]` for video downloads
4. Use `/search [query]` to find and download music

**Note:** I download and send files directly to the chat. For voice chat streaming, you need additional setup with voice chat permissions.

**Support:** Forward this message to @your_support_username
"""
    await message.reply_text(help_text)

@app.on_message(filters.command("formats"))
async def formats_command(client: Client, message: Message):
    """Show available download formats"""
    if len(message.command) < 2:
        return await message.reply_text("❌ Please provide a YouTube URL!\n\nExample: `/formats https://youtube.com/watch?v=...`")
    
    url = message.command[1]
    
    if not await youtube.exists(url):
        return await message.reply_text("❌ Please provide a valid YouTube URL!")
    
    status_msg = await message.reply_text("🔍 **Getting available formats...**")
    
    try:
        formats, link = await youtube.formats(url)
        
        if not formats:
            return await status_msg.edit_text("❌ No formats available for this video.")
        
        format_text = f"📋 **Available Formats:**\n\n"
        
        for i, fmt in enumerate(formats[:10], 1):
            size_mb = fmt.get('filesize', 0) / (1024 * 1024) if fmt.get('filesize') else 0
            format_text += f"{i}. **{fmt['format_note']}** ({fmt['ext']})\n"
            format_text += f"   📊 Size: {size_mb:.1f} MB\n\n"
        
        await status_msg.edit_text(format_text)
        
    except Exception as e:
        logger.error(f"Formats error: {e}")
        await status_msg.edit_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.regex(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)"))
async def auto_download_handler(client: Client, message: Message):
    """Auto-download when YouTube link is sent"""
    url = message.text
    
    if not await youtube.exists(url):
        return
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Download Audio", callback_data=f"quick_audio_{url}"),
            InlineKeyboardButton("📹 Download Video", callback_data=f"quick_video_{url}")
        ]
    ])
    
    await message.reply_text(
        "🎵 **YouTube link detected!**\n\nWhat would you like to download?",
        reply_markup=keyboard
    )

@app.on_callback_query(filters.regex(r"quick_(audio|video)_(.+)"))
async def quick_download_callback(client: Client, callback_query):
    """Handle quick download buttons"""
    parts = callback_query.data.split("_", 2)
    download_type = parts[1]  # audio or video
    url = parts[2]
    
    try:
        await callback_query.answer(f"Downloading {download_type}...")
        
        if download_type == "audio":
            await download_and_send_audio(client, callback_query.message, url, callback_query.message)
        else:
            await download_and_send_video(client, callback_query.message, url, callback_query.message)
            
    except Exception as e:
        logger.error(f"Quick download error: {e}")
        await callback_query.message.edit_text(f"❌ **Error:** {str(e)}")

async def main():
    """Main function to start the bot"""
    try:
        # Initialize database
        await init_db()
        
        # Start the bot
        await app.start()
        logger.info("🎵 Music Bot started successfully!")
        
        print("🎵 Telegram Music Bot is running!")
        print("📱 Add your bot to a group and try:")
        print("   /play despacito")
        print("   /search baby shark")
        print("   /help")
        
        # Keep running
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
    finally:
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())