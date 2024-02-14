import yt_dlp
import discord
import re
import os
import requests
from dotenv import load_dotenv
from pytube import YouTube, Search, Playlist, extract
import asyncio
import aiohttp
import time
import difflib

from helper import convert_seconds
from spotify_api import get_videos_from_spotify_album

from ytmusicapi import YTMusic

ydl_opts = {
    'format': 'bestaudio/best',
    'merge_output_format': 'opus',
    'outtmpl': "./audio/%(id)s.opus",
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = yt_dlp.YoutubeDL(ydl_opts)

yt_music = YTMusic()


def download_youtube_audio(url: str, download=True):
    data = ytdl.extract_info(url, download=download)
    time.sleep(2)
    if 'entries' in data:
        data = data['entries'][0]
    return data


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = ""

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        try:
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: download_youtube_audio(url, download=not stream))

            return {
                "file": ytdl.prepare_filename(data),
                "url": data['original_url'],
                "title": data['title'],
                "author": data['uploader'],
                "image_url": data['thumbnail'],
                "time": round(data['duration']),
                "type": "youtube",
            }
        except Exception as e:
            print('from_url:', e)
            return

    @classmethod
    async def from_spotify(cls, query, *, loop=None, stream=False):
        try:
            loop = loop or asyncio.get_event_loop()

            search_results = yt_music.search(
                query, filter='songs', limit=3)[:3]

            search_result_names = [
                f"{song.get('title')} {song.get('artists')[0].get('name')}" for song in search_results]

            song = search_results[0]
            closest_match = difflib.get_close_matches(
                query, search_result_names, n=1, cutoff=0)
            if closest_match:
                song = search_results[search_result_names.index(
                    closest_match[0])]

            videoId = song.get('videoId')

            data = await loop.run_in_executor(None, lambda: download_youtube_audio(f"https://www.youtube.com/watch?v={videoId}", download=not stream))

            return {
                "file": ytdl.prepare_filename(data),
                "time": round(data['duration']),
            }
        except Exception as e:
            print('from_spotify:', e)
            return

    @classmethod
    async def from_url_download_only(cls, url, *, loop=None):
        try:
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: download_youtube_audio(url, download=True))

            return ytdl.prepare_filename(data)
        except Exception as e:
            print('download_only:', e)
            return


def get_youtube_video(url: str):
    yt = YouTube(url)

    return {
        "url": yt.watch_url,
        "title": yt.title,
        "author": yt.author,
        "image_url": yt.thumbnail_url,
        "time": round(yt.length),
        "type": "youtube",
    }


def get_videos_from_yt_playlist(url: str):
    if not url:
        return
    p = Playlist(url)
    return p.video_urls


def search_multiple_video(query: str):
    if not query:
        return

    s = Search(query)
    return [get_youtube_video(video.watch_url) for video in s.results[:5]]
