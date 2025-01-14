import argparse
import json
import os
import time

from rich.progress import Progress

from sqlite_helper import Table
from youtube import Playlist, Video, get_videos_from_ids

## for finding deleted video titles https://findyoutubevideo.thetechrobo.ca/


def get_videos_from_file(path):
    _, extension = os.path.splitext(path)
    if extension == ".json":
        with open(path, "r", encoding="utf-8") as f:
            video_info = json.load(f)

    else:
        raise NotImplementedError

    if isinstance(video_info[0], str):
        return get_videos_from_ids(video_info)

    elif isinstance(video_info[0], dict):
        return [Video().update(video) for video in video_info]

    else:
        raise NotImplementedError


def dump_videos_to_file(path, videos):
    _, extension = os.path.splitext(path)
    if extension == ".json":
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                videos,
                f,
                default=lambda o: o.__dict__,
                ensure_ascii=False,
                indent=4,
            )

    else:
        raise NotImplementedError


def setup_playlist_tables(db_path, playlist):
    # setup main table
    data = playlist.to_dict()
    columns = Video().to_dict().keys()
    with Table(db_path, "playlists") as table:
        table.create(list(data.keys()), "id")
        table.insert(data)

        # spoof title to set child table
        table.name = data["title"].lower()
        table.create(columns, "id")


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


def get_archive_videos(db_path, playllst_title):
    # get archive from playlist table
    columns = Video().to_dict().keys()
    with Table(db_path, playllst_title) as table:
        archive_data = table.select(columns)

    return [Video().update(archive) for archive in archive_data]


def update_archive(db_path, playllst_title, archive_videos, new_videos):
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
    parser.add_argument("-c", "--cache", action="store_true")
    parser.add_argument("-d", "--db_path", default="playlist_archive.db", type=str)
    parser.add_argument("-e", "--export_file", default=None, type=str)
    parser.add_argument("-i", "--import_file", default=None, type=str)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.id_or_url:
        playlist = Playlist(args.id_or_url)

    else:
        raise NotImplementedError
    # playlist.title = (
    #     playlist.title if args.playlist_title is None else args.playlist_title
    # )

    if args.export_file:
        raise NotImplementedError

    else:
        setup_playlist_tables(args.db_path, playlist)
        cache_path = f"cache_{playlist.title}.json"

        if args.import_file and os.path.exists(args.import_file):
            new_videos = get_videos_from_file(args.import_file)

        elif (
            args.cache
            and os.path.exists(cache_path)
            and (time.time() - os.path.getmtime(cache_path)) < 60 * 60 * 24
        ):
            new_videos = get_videos_from_file(cache_path)

        else:
            new_videos = playlist.get_videos()

        archive_videos = get_archive_videos(args.db_path, playlist.title)
        update_archive(args.db_path, playlist.title, archive_videos, new_videos)

        if args.cache:
            dump_videos_to_file(cache_path, new_videos)
