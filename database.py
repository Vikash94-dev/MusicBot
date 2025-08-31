import asyncio
from typing import Dict, Any

# Simple in-memory database simulation
chat_settings = {}

async def init_db():
    """Initialize the database"""
    print("✅ Database initialized")

async def is_on_off(setting_id: int) -> bool:
    """Check if a setting is on or off"""
    # Default settings
    default_settings = {
        1: True,  # Direct download enabled
        2: False, # Video mode
        3: True,  # Queue enabled
    }
    return default_settings.get(setting_id, False)

async def get_chat_settings(chat_id: int) -> Dict[str, Any]:
    """Get settings for a specific chat"""
    return chat_settings.get(chat_id, {
        'volume': 100,
        'repeat_mode': False,
        'shuffle_mode': False,
        'auto_leave': True
    })

async def set_chat_settings(chat_id: int, settings: Dict[str, Any]):
    """Set settings for a specific chat"""
    if chat_id not in chat_settings:
        chat_settings[chat_id] = {}
    chat_settings[chat_id].update(settings)

async def add_to_history(chat_id: int, track_info: Dict[str, Any]):
    """Add track to play history"""
    # Simple implementation - could be expanded
    pass

async def get_user_stats(user_id: int) -> Dict[str, Any]:
    """Get user statistics"""
    return {
        'songs_played': 0,
        'time_listened': 0
    }