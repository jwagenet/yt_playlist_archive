import math

# import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from rich.progress import Progress


PLAYLIST_URL_STEM = "https://www.youtube.com/playlist?list="
VIDEO_URL_STEM = "https://www.youtube.com/watch?v="
MAX_RESULTS = 50

KEY_FILE = "key"
with open(KEY_FILE, "r") as f:
    api_key = f.readline()

YOUTUBE = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)


class Playlist:
    def __init__(self, id_or_url):
        id_and_url = get_id_and_url(id_or_url, PLAYLIST_URL_STEM)
        self.id = id_and_url["id"]
        self.url = id_and_url["url"]
        self.title = ""

        self.get_info()

    def get_info(self):
        """Get playlist properties"""

        callback = YOUTUBE.playlists().list
        desc = "Fetch playlist"
        params = {
            "part": "snippet",
            "id": self.id,
        }

        playlist = get_pagenated_response(callback, params, desc, max_results=1)[0]

        self.title = playlist["snippet"]["title"]

    def get_videos(self):
        """Get list of videos in playlist"""

        callback = YOUTUBE.playlistItems().list
        desc = "Fetch playlist items"
        params = {
            "part": "snippet, status",
            "playlistId": self.id,
        }

        items = get_pagenated_response(callback, params, desc)
        return [Video().from_youtube_video(item) for item in items]

    def to_dict(self):
        return {key: value for key, value in self.__dict__.items()}


class Video:
    def __init__(self, id_or_url=None):
        self.id = ""
        self.url = ""
        self.title = ""
        self.status = "unavailable"

        if id_or_url:
            self.update(get_id_and_url(id_or_url, VIDEO_URL_STEM))
            self.get_video()

    def __repr__(self):
        vals = []
        for attr, value in self.__dict__.items():
            if attr != "url":
                vals.append(f"{attr}={value}")

        repr_str = ", ".join(vals)
        return f"Video({repr_str})"

    def __eq__(self, other):
        # comparing id only because other properties could change
        if isinstance(other, Video):
            return self.id == other.id
        return False

    def update(self, other):
        """Update Video properties from other, which could be dict or Video"""

        if isinstance(other, Video):
            attrs = other.__dict__

        elif isinstance(other, dict):
            attrs = other

        else:
            raise NotImplementedError

        for attr, value in attrs.items():
            setattr(self, attr, value)

        return self

    def to_dict(self):
        return {key: value for key, value in self.__dict__.items()}

    def get_video(self, id):
        """Set video properties from id

        Only one api response expected
        Sets status to "unavailable" if empty response
        """

        callback = YOUTUBE.videos().list
        desc = "Fetch video item"
        params = {
            "part": "snippet, status",
            "id": id,
        }

        videos = get_pagenated_response(callback, params, desc, max_results=1)

        if len(videos) == 0:
            self.update({"status": "unavailable"})

        else:
            self.from_youtube_video(videos[0])

    def from_youtube_video(self, youtube_video):
        """Set Video properties from either a #video or #playlisItem response

        returns self for when initializing video without id:
            Video().from_youtube_video(youtube_video)
        """

        kind = "youtube#video"
        if isinstance(youtube_video, dict):
            if "kind" in youtube_video and youtube_video["kind"] == kind:
                self.update(get_id_and_url(youtube_video["id"], VIDEO_URL_STEM))

            elif (
                "snippet" in youtube_video
                and "resourceId" in youtube_video["snippet"]
                and "kind" in youtube_video["snippet"]["resourceId"]
                and youtube_video["snippet"]["resourceId"]["kind"] == "youtube#video"
            ):
                self.update(
                    get_id_and_url(
                        youtube_video["snippet"]["resourceId"]["videoId"],
                        VIDEO_URL_STEM,
                    )
                )

            else:
                raise NotImplementedError

            self.update(
                {
                    "title": youtube_video["snippet"]["title"],
                    "status": youtube_video["status"]["privacyStatus"],
                }
            )

        else:
            raise NotImplementedError

        return self


def get_videos_from_ids(ids_or_urls):
    """Get list of Videos from list of ids or urls

    if id is not found in result, marked as unavailable
    """

    callback = YOUTUBE.videos().list
    ids = [get_id_and_url(id, VIDEO_URL_STEM)["id"] for id in ids_or_urls]

    items = []
    total_requests = math.ceil(len(ids) / MAX_RESULTS)
    for i in range(total_requests):
        start_index = i * MAX_RESULTS
        desc = f"Fetch video items {i + 1}/{total_requests}"
        params = {
            "part": "snippet, status",
            "id": ",".join(ids[start_index : start_index + MAX_RESULTS]),
        }
        items.extend(get_pagenated_response(callback, params, desc))

    videos = [Video().from_youtube_video(item) for item in items]

    video_ids = [video.id for video in videos]
    for id in ids:
        if id not in video_ids:
            video = Video().update(get_id_and_url(id, VIDEO_URL_STEM))
            video.update({"status": "unavailable"})
            videos.append(video)

    videos = sorted(videos, key=lambda x: ids.index(x.id))

    return videos


def get_id_and_url(id_or_url, stem):
    if "&" in id_or_url:
        chunks = id_or_url.split("&")
        id_or_url = chunks[0]

    id = id_or_url if stem not in id_or_url else id_or_url.replace(stem, "")

    return {"id": id, "url": stem + id}


def get_pagenated_response(callback, params, desc, max_results=MAX_RESULTS):
    """Helper to get list of requested items from API list request.
    Loops over pageated responses to get full results
    """

    payload = {
        "pageToken": "",
        "maxResults": max_results,
    }

    payload.update(params)

    items = []
    total_results = None
    with Progress() as progress:
        task = progress.add_task(desc)

        while len(items) != total_results:
            request = callback(**payload)
            response = request.execute()

            if not total_results:
                total_results = response["pageInfo"]["totalResults"]
                progress.update(task, total=total_results)

            items.extend(response["items"])
            progress.update(task, advance=len(items))

            if "nextPageToken" in response:
                payload.update({"pageToken": response["nextPageToken"]})
            else:
                break

    return items
