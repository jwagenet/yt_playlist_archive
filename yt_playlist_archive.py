import argparse
import json
import os
import time

from rich.progress import Progress

from sqlite_helper import Table
from youtube import VIDEO_URL_STEM, Playlist, Video, get_id_and_url, get_videos_from_ids

## for finding deleted video titles https://findyoutubevideo.thetechrobo.ca/


def get_current_videos(playlist, use_cache=False):
    """Get all video urls found in playlist.
    May load from cached url result if older than one day.

    Returns list of urls.
    """

    cache_file_name = f"cached_urls_{playlist.title}.json"

    if (
        use_cache
        and os.path.exists(cache_file_name)
        and (time.time() - os.path.getmtime(cache_file_name)) < 60 * 60 * 24
    ):
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
            id = get_id_and_url(url, VIDEO_URL_STEM)["id"]
            video_ids.append(id)

        videos = get_videos_from_ids(video_ids)

    else:
        print("Getting videos from playlist")
        videos = playlist.get_videos()

        video_ids = [video.id for video in videos]
        if use_cache:
            with open(cache_file_name, "w", encoding="utf-8") as f:
                json.dump(list(video_ids), f, ensure_ascii=False, indent=4)

    return videos


def get_updated_videos(old_videos, new_videos):
    """Compare new_videos to old_videos and determines updated_videos

    Returns list of updated videos
    """

    updated_videos = []
    with Progress() as progress:
        task = progress.add_task(
            "Comparing video statuses", total=len(new_videos) + len(old_videos)
        )
        for new in new_videos:
            # conform status
            if new.status == "public" or new.status == "unlisted":
                new.status = "available"
            elif (
                new.status == "privacyStatusUnspecified"
                and new.title == "Deleted video"
            ):
                new.status = "unavailable"

            # check for private/unavailable change
            updated = False
            for i, old in enumerate(old_videos):
                if (
                    new == old
                    and new.status != old.status
                    and new.status in ["private", "unavailable"]
                ):
                    updated_videos.append(old.update({"status": new.status}))
                    updated = True
                    break

            # add new entries with current status
            if not updated and new not in old_videos:
                updated_videos.append(new)

            progress.update(task, advance=1)

        for i, old in enumerate(old_videos):
            # if entry exists, was deleted from playlist rather than private/deleted
            if old not in new_videos and old.status != "removed":
                updated_videos.append(old.update({"status": "removed"}))

            progress.update(task, advance=1)

    # build update count string
    change_count = {"available": 0, "removed": 0, "private": 0, "unavailable": 0}
    for updated in updated_videos:
        change_count[updated.status] += 1

    count_str = ""
    for key, value in change_count.items():
        count_str += f"\n{key}: {value}"
    print(f"Updates:{count_str}")

    return updated_videos


def update_archive(playllst_title, new_videos):
    # get archive from playlist table
    with Table(db_path, playllst_title) as table:
        archive_data = table.select(columns)

    # update archive playlist table
    archive_videos = [Video().update(archive) for archive in archive_data]
    update_videos = get_updated_videos(archive_videos, new_videos)

    update_data = [video.to_dict() for video in update_videos]
    with Table(db_path, playllst_title) as table:
        for update in update_data:
            table.upsert(update, "id", "status")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="YouTube Playlist Archive",
        description="Archive YouTube video properties and update over time to catch content deletions",
    )
    parser.add_argument("id_or_url")
    parser.add_argument("-t", "--playlist_title")
    parser.add_argument("-u", "--video_urls")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    db_path = "playlist_archive.db"

    playlist = Playlist(args.id_or_url)
    playlist.title = (
        playlist.title if args.playlist_title is None else args.playlist_title
    )

    # setup main table
    data = playlist.to_dict()
    columns = Video().to_dict().keys()
    with Table(db_path, "playlists") as table:
        table.create(list(data.keys()), "id")
        table.insert(data)

        # spoof title to set child table
        table.title = data["title"]
        table.create(columns, "id")

    new_videos = playlist.get_videos()
    update_archive(playlist.title, new_videos)

    # if os.path.exists(archive_file_name):
    #     with open(archive_file_name, "r", encoding="utf-8") as f:
    #         archive_info = json.load(f)

    # with open(archive_file_name, "w", encoding="utf-8") as f:
    #     json.dump(
    #         archive_videos,
    #         f,
    #         default=lambda o: o.__dict__,
    #         ensure_ascii=False,
    #         indent=4,
    #     )
