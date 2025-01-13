import argparse
import json
import pytube
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

## for finding deleted video titles https://findyoutubevideo.thetechrobo.ca/


def get_video_urls(playlist_url):
    """Get all video urls found in playlist.
    May load from cached url result if older than one day.
    
    Returns list of urls.
    """
    
    cache_file_name = "cached_urls.json"

    if os.path.exists(cache_file_name) and (time.time() - os.path.getmtime(cache_file_name)) < 60*60*24:
        print("Loading urls from recent cache")
        with open(cache_file_name, "r", encoding="utf-8") as f:
            video_urls = json.load(f)

        for i, url in enumerate(video_urls):
            if "&" in url:
                chunks = url.split("&")
                video_urls[i] = chunks[0]

    else:
        print("Requesting video urls")
        video_urls = pytube.Playlist(playlist_url).video_urls
        with open(cache_file_name, "w", encoding="utf-8") as f:
            json.dump(list(video_urls), f, ensure_ascii=False, indent=4)

    return video_urls


def get_video_info(url):
    """Get video title from YouTube with url, extract id from url,
    and attach availability status based on request response.
    
    Returns dict of video info
    """

    id = pytube.extract.video_id(url)

    try:
        title = pytube.YouTube(url).title
        status = "available"

    except pytube.exceptions.VideoPrivate:
        title = "Private"
        status = title.lower()

    except pytube.exceptions.VideoUnavailable:
        title = "Unavailable"
        status = title.lower()

    return {"id" : id,
            "title" : title,
            "url" : url,
            "status" : status}


def get_video_info_from_urls(video_urls):
    """Process list of urls to get video info with threading.
    
    Return list of video info dicts    
    """

    start = time.time()
    processes = []
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        for url in video_urls:
            processes.append(executor.submit(get_video_info, url))

    video_info = []
    for task in as_completed(processes):
        video_info.append(task.result())

    print(f"Time taken: {time.time() - start}")

    # reorder to match video_urls
    video_info = sorted(video_info,key=lambda x:video_urls.index(x["url"]))

    return video_info


def update_archive_info(archive_info, update_info):
    """Update main list with video status and append new videos from updated video info.
    
    Returns list of video info dicts
    """
    change_count = {   "available" : 0,
                        "removed" : 0,
                        "private" : 0,
                        "unavailable" : 0 }

    for video in update_info:
        updated = False
        for i, main_video in enumerate(archive_info):
            # if entry exists, was deleted from playlist rather than private/deleted
            if video["id"] == main_video["id"]:
                if video["status"] not in ["private", "unavailable"]:
                    archive_info[i]["status"] = "removed"
                    change_count["removed"] += 1
                else:
                    archive_info[i]["status"] = video["status"]
                    change_count[video["status"]] += 1
                
                updated = True
                break

        # add new entries with current status
        if not updated:
            archive_info.append(video)
            change_count["available"] += 1
    
    count_str = ""
    for key, value in change_count.items():
        count_str += f"\n{key}: {value}"
    print(f"Updates:{count_str}")
            
    return archive_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
                        prog="YouTube Playlist Archive",
                        description="Archive YouTube video title and url and update over time to catch content deletions")
    parser.add_argument("playlist_url")
    parser.add_argument("-t", "--playlist_title")
    parser.add_argument("-u", "--video_urls")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    
    # accept playlist_id instead of url and conform, but no validation
    playlist_url_stem = "https://www.youtube.com/playlist?list="
    playlist_url = playlist_url_stem + args.playlist_url if playlist_url_stem not in args.playlist_url else args.playlist_url
    
    playlist_title = pytube.Playlist(args.playlist_url).title if args.playlist_title is None else args.playlist_title
    
    # get current archive, if it exists
    archive_file_name = f"archive_{playlist_title}.json"
    archive_info = []    
    if os.path.exists(archive_file_name):
        with open(archive_file_name, "r", encoding="utf-8") as f:
            archive_info = json.load(f)

    archive_urls = [video["url"] for video in archive_info]
    
    # get url list and compare to archive
    video_urls = get_video_urls(playlist_url) if args.video_urls is None else args.video_urls
    update_urls = [url for url in video_urls if url not in archive_urls]

    # only make updates to archive differences
    if len(update_urls) != 0:        
        print(f"Updates to '{playlist_title}' archive: {len(update_urls)}")
    
        update_info = get_video_info_from_urls(update_urls)

        # save to timestamped file
        update_file_name = f"update__{time.strftime('%y%m%d')}.json"
        with open(update_file_name, "w", encoding="utf-8") as f:
            json.dump(update_info, f, ensure_ascii=False, indent=4)

        # update main file
        update_archive_info(archive_info, update_info)
    
        # with open(archive_file_name, "w", encoding="utf-8") as f:
            # json.dump(archive_info, f, ensure_ascii=False, indent=4)
    
    else:
        print(f"No updates to '{playlist_title}' archive")

