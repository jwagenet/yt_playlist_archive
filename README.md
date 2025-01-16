
# yt_playlist_archive

A utility for archiving basic video details (id, title, visibility status) for YouTube playlist items. Over time, YouTube videos, especialy music, tend to be deleted or go private. This tool can be used to periodically check a playlist for these changes and note the status change while retaining the id and title, and will also retain and note videos removed from the playlist. 

This utility does not (and will not) download the videos themselves. 

## Setup

- Tested with `python 3.11`, but I think `python 3.9` should work
- `sqlite3` 3.24.0 is required for `UPSERT`, but that should be included at least as far back as `python 3.8`.
- Run `pip install -r requirements.txt` or your preferred package manager
- Get a YouTube API key (following these instructions)[https://developers.google.com/youtube/v3/getting-started]
  - Save the API key to a file `key` in your working directory

## Usage

`py ./yt_playlist_archive.py <playlist id or url>` is sufficient to run the utility for the first time and again, manually or on a schedule, to update the archive. 

### Options

- `--db_path`, `-d`: set the db path to something other than `playlist_archive.db`
- `--import_file`, `-i`: import a json or csv to playlist archive with a given file name
- `--export_file`, `-e`: export a json or csv to playlist archive wiht a given file name

### Dealing with deleted or private video titles

If you have a long running playlist, it is likely some of the videos have gone private or deleted and the title is lost (the impetus for this project). Fortunately, titles of *some* videos may be recoverable thanks to (youtubevideofinder)[https://findyoutubevideo.thetechrobo.ca/]. A (currently fully manual) process for recovering titles might look like:

1. `py ./yt_playlist_archive.py <playlist id or url>`
2. `py ./yt_playlist_archive.py <playlist id or url> -e missing_videos.csv`
3. Filter the table for your videos with status `private` or `deleted`
4. Search with each id at (youtubevideofinder)[https://findyoutubevideo.thetechrobo.ca/] and update the table titles when successful
5. `py ./yt_playlist_archive.py <playlist id or url> -i missing_videos.csv`
