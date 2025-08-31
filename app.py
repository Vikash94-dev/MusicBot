import os
import asyncio
import aiohttp
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.serving import run_simple
import json
import re
from youtube_api import YouTubeAPI
import config

app = Flask(__name__)
youtube_api = YouTubeAPI()

# Store for current playlist and playing status
app_state = {
    'playlist': [],
    'current_track': None,
    'is_playing': False,
    'current_index': 0
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
async def search_music():
    try:
        data = request.get_json()
        query = data.get('query', '')
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
            
        # Search for videos
        results = await youtube_api.search(query, limit=10)
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/add_to_playlist', methods=['POST'])
async def add_to_playlist():
    try:
        data = request.get_json()
        video_url = data.get('url', '')
        
        if not video_url:
            return jsonify({'error': 'URL is required'}), 400
            
        # Get video details
        title, duration, thumbnail, video_id = await youtube_api.get_details(video_url)
        
        track = {
            'id': video_id,
            'title': title,
            'duration': duration,
            'thumbnail': thumbnail,
            'url': video_url
        }
        
        app_state['playlist'].append(track)
        
        return jsonify({
            'success': True,
            'track': track,
            'playlist_length': len(app_state['playlist'])
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_stream_url', methods=['POST'])
async def get_stream_url():
    try:
        data = request.get_json()
        video_url = data.get('url', '')
        
        if not video_url:
            return jsonify({'error': 'URL is required'}), 400
            
        # Get stream URL using the API
        stream_url = await fetch_stream_url(video_url)
        
        if stream_url:
            return jsonify({
                'success': True,
                'stream_url': stream_url
            })
        else:
            return jsonify({'error': 'Could not get stream URL'}), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/playlist')
def get_playlist():
    return jsonify({
        'playlist': app_state['playlist'],
        'current_track': app_state['current_track'],
        'is_playing': app_state['is_playing'],
        'current_index': app_state['current_index']
    })

@app.route('/play', methods=['POST'])
def play_track():
    try:
        data = request.get_json()
        index = data.get('index', 0)
        
        if 0 <= index < len(app_state['playlist']):
            app_state['current_index'] = index
            app_state['current_track'] = app_state['playlist'][index]
            app_state['is_playing'] = True
            
            return jsonify({
                'success': True,
                'current_track': app_state['current_track']
            })
        else:
            return jsonify({'error': 'Invalid track index'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/next', methods=['POST'])
def next_track():
    try:
        if app_state['playlist']:
            app_state['current_index'] = (app_state['current_index'] + 1) % len(app_state['playlist'])
            app_state['current_track'] = app_state['playlist'][app_state['current_index']]
            
            return jsonify({
                'success': True,
                'current_track': app_state['current_track']
            })
        else:
            return jsonify({'error': 'No tracks in playlist'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/previous', methods=['POST'])
def previous_track():
    try:
        if app_state['playlist']:
            app_state['current_index'] = (app_state['current_index'] - 1) % len(app_state['playlist'])
            app_state['current_track'] = app_state['playlist'][app_state['current_index']]
            
            return jsonify({
                'success': True,
                'current_track': app_state['current_track']
            })
        else:
            return jsonify({'error': 'No tracks in playlist'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/remove_track', methods=['POST'])
def remove_track():
    try:
        data = request.get_json()
        index = data.get('index', 0)
        
        if 0 <= index < len(app_state['playlist']):
            removed_track = app_state['playlist'].pop(index)
            
            # Adjust current index if necessary
            if app_state['current_index'] >= index:
                app_state['current_index'] = max(0, app_state['current_index'] - 1)
                
            if app_state['playlist']:
                app_state['current_track'] = app_state['playlist'][app_state['current_index']]
            else:
                app_state['current_track'] = None
                app_state['is_playing'] = False
            
            return jsonify({
                'success': True,
                'removed_track': removed_track,
                'playlist_length': len(app_state['playlist'])
            })
        else:
            return jsonify({'error': 'Invalid track index'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def fetch_stream_url(link: str) -> str | None:
    """Fetch stream URL from external API"""
    try:
        video_id = link.split("v=")[-1].split("&")[0]
        if not video_id:
            raise ValueError("Empty video ID extracted")
    except Exception as e:
        raise ValueError(f"❌ Could not extract video ID from link: {link}") from e

    api_key = getattr(config, "API_KEY", os.getenv("API_KEY", "default_key"))
    api_url = getattr(config, "API_URL", os.getenv("API_URL", "https://deadlinetech.site"))
    
    if not api_key or not api_url:
        raise RuntimeError("❌ API_KEY or API_URL missing in config.")

    url = f"{api_url}/song/{video_id}?key={api_key}"
    timeout = aiohttp.ClientTimeout(total=10)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        for attempt in range(1, 3):
            try:
                async with session.get(url, allow_redirects=True) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "done":
                            stream_url = data.get("stream_url")
                            if stream_url:
                                return stream_url
                    elif response.status == 404:
                        return None
            except Exception as e:
                print(f"⚠️ Request error: {e}")

            if attempt < 2:
                await asyncio.sleep(0.5)

    return None

if __name__ == '__main__':
    # Use run_simple for better async support
    run_simple('0.0.0.0', 5000, app, use_reloader=True, use_debugger=True, threaded=True)
