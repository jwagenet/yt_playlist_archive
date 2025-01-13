import json
import pytube
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

## for finding deleted video titles https://findyoutubevideo.thetechrobo.ca/

playlist_link = "https://www.youtube.com/playlist?list=PLoQb4jteUerWP2U-mfYIE4C2a1hiIFc_H"
file_main = "video_list_main.json"


def get_video_urls(playlist_link):
    """Get all video urls found in playlist.
    May load from cached url result if older than one day.
    
    Returns list of urls.
    """
    
    cache_name = "cached_urls.json"

    if os.path.exists(cache_name) and (time.time() - os.path.getmtime(cache_name)) < 60*60*24:
        print("Load video links from file.")
        with open(cache_name, 'r', encoding='utf-8') as f:
            video_urls = json.load(f)

        for i, url in enumerate(video_urls):
            if "&" in url:
                chunks = url.split("&")
                video_urls[i] = chunks[0]

    else:
        print("Download video links.")
        video_urls = pytube.Playlist(playlist_link).video_urls
        with open(cache_name, 'w', encoding='utf-8') as f:
            json.dump(list(cached_urls), f, ensure_ascii=False, indent=4)

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

    print(f'Time taken: {time.time() - start}')

    # reorder to match video_urls
    video_info = sorted(video_info,key=lambda x:video_urls.index(x["url"]))

    return video_info


def update_main_info(main_info, update_info):
    """Update main list with video status and append new videos from updated video info.
    
    Returns list of video info dicts
    """

    for video in update_info:
        updated = False
        for i, main_video in enumerate(main_info):
            # if entry exists, was deleted from playlist rather than private/deleted
            if video["id"] == main_video["id"]:
                if video["status"] not in ["private", "unavailable"]:
                    main_info[i]["status"] = "removed"
                else:
                    main_info[i]["status"] = video["status"]
                updated = True

                break

        # add new entries with current status
        if not updated:
            main_info.append(video)

    print(main_info)
    # with open(file_main, 'w', encoding='utf-8') as f:
        # json.dump(main_info, f, ensure_ascii=False, indent=4)

    return main_info


video_urls = get_video_urls(playlist_link)
with open(file_main, 'r', encoding='utf-8') as f:
    main_info = json.load(f)

main_urls = [video["url"] for video in main_info]
missing_urls = [url for url in video_urls if url not in main_urls]

print(f"Missing urls: {len(missing_urls)}")

if len(missing_urls) != 0:
    update_info = get_video_info_from_urls(missing_urls)

    # save to timestamped file
    file_name = f'video_list_{time.strftime("%y%m%d")}.json'
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(update_info, f, ensure_ascii=False, indent=4)

    # update main file
    update_main_info(main_info, update_info)
    
    