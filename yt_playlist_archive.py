import argparse
import json
import os
import time

from concurrent.futures import ThreadPoolExecutor, as_completed

from youtube import Playlist, Video, get_videos_from_ids, get_id_and_url, VIDEO_URL_STEM
from rich.progress import Progress

## for finding deleted video titles https://findyoutubevideo.thetechrobo.ca/


def get_current_videos(playlist, use_cache=False):
    """Get all video urls found in playlist.
    May load from cached url result if older than one day.
    
    Returns list of urls.
    """

    cache_file_name = f"cached_urls_{playlist.title}.json"

    if use_cache and os.path.exists(cache_file_name) and (time.time() - os.path.getmtime(cache_file_name)) < 60*60*24:
        print("Getting videos from recent cache")
        with open(cache_file_name, "r", encoding="utf-8") as f:
            video_urls = json.load(f)

        # strip parameters from url
        for i, url in enumerate(video_urls):
            if "&" in url:
                chunks = url.split("&")
                video_urls[i] = chunks[0]

        video_ids = []
        for url in video_urls:
            id, _ = get_id_and_url(url, VIDEO_URL_STEM)
            video_ids.append(id)

        videos = get_videos_from_ids(video_ids)

    else:
        print("Getting videos from playlist")
        videos = playlist.get_videos()
        video_urls = [video.url for video in videos]

        if use_cache:
            with open(cache_file_name, "w", encoding="utf-8") as f:
                json.dump(list(video_urls), f, ensure_ascii=False, indent=4)

    return videos


def update_archive_info(archive_videos, update_videos):
    """Update main list with video status and append new videos from updated video info.
    
    Returns list of video info dicts
    """
    change_count = {    "available" : 0,
                        "removed" : 0,
                        "private" : 0,
                        "unavailable" : 0 }

    with Progress() as progress:
        task = progress.add_task("Update archive items", total=len(update_videos))
        for update in update_videos:
            updated = False

            if update.status == "public" or update.status =="unlisted":
                update.status = "available"
            elif update.status == "privacyStatusUnspecified" and update.title == "Deleted video":
                update.status = "unavailable"

            for i, archive in enumerate(archive_videos):
                if update == archive and update.status != archive.status and update.status in ["private", "unavailable"]:
                    archive_videos[i].update({"status": update.status})
                    change_count[update.status] += 1
                    updated = True
                    break

            # add new entries with current status
            if not updated and update not in archive_videos:
                archive_videos.append(update)
                change_count[update.status] += 1

            progress.update(task, advance=1)

    for i, archive in enumerate(archive_videos):
        # if entry exists, was deleted from playlist rather than private/deleted
        if archive not in update_videos:
            archive_videos[i].update({"status": "removed"})
            change_count["removed"] += 1

    count_str = ""
    for key, value in change_count.items():
        count_str += f"\n{key}: {value}"
    print(f"Updates:{count_str}")

    return archive_videos


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                        prog="YouTube Playlist Archive",
                        description="Archive YouTube video title and url and update over time to catch content deletions")
    parser.add_argument("playlist_url")
    parser.add_argument("-t", "--playlist_title")
    parser.add_argument("-u", "--video_urls")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    playlist = Playlist(args.playlist_url)
    playlist_title = playlist.title if args.playlist_title is None else args.playlist_title

    # has cache option, but for some reason can't get private videos when using videos.list, same num api calls anyway
    videos = get_current_videos(playlist, False) if args.video_urls is None else args.video_urls

    # get archive, if it exists
    archive_file_name = f"archive_{playlist_title}.json"
    archive_info = []
    if os.path.exists(archive_file_name):
        with open(archive_file_name, "r", encoding="utf-8") as f:
            archive_info = json.load(f)

    archive_videos = [Video().update(archive) for archive in archive_info]
    archive_videos = update_archive_info(archive_videos, videos)

    with open(archive_file_name, "w", encoding="utf-8") as f:
        json.dump(archive_videos, f, default=lambda o: o.__dict__, ensure_ascii=False, indent=4)