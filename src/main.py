import logging
import os
import signal
import time

from domain import RateLimitException
from storage import TrackingMissingMusicStorage, FileSystemMusicStorage
from tl1001 import TLBackend

SCRAPE_TIMEOUT = 5.5
BREAK_AFTER_NUM_ELEMENTS = -1
START_TRACKLIST = "tcblybt"

class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("Stopping now...")
        self.kill_now = True


def work_recursive(musicstore: TrackingMissingMusicStorage):
    killer = GracefulKiller()

    logger = logging.getLogger("recursive_worker")
    logger.setLevel("INFO")
    logger.addHandler(logging.StreamHandler())

    counter = 0
    tlb = TLBackend()
    while (BREAK_AFTER_NUM_ELEMENTS == -1 or counter < BREAK_AFTER_NUM_ELEMENTS) and not killer.kill_now:
        try:
            if len(musicstore.todo_tracklists) > 0:
                tlid = musicstore.todo_tracklists.pop()
                tl = tlb.get_tracklist(tlid)
                logger.debug(tl)
                musicstore.put_tracklist(tl)
                time.sleep(SCRAPE_TIMEOUT)

            if len(musicstore.todo_tracks) > 0:
                trackid = musicstore.todo_tracks.pop()
                track = tlb.get_track(trackid)
                logger.debug(track)
                musicstore.put_track(track)
                time.sleep(SCRAPE_TIMEOUT)

            if len(musicstore.todo_artists) > 0:
                artistid = musicstore.todo_artists.pop()
                artist = tlb.get_artist(artistid)
                logger.debug(artist)
                musicstore.put_artist(artist)
                time.sleep(SCRAPE_TIMEOUT)

            if len(musicstore.todo_labels) > 0:
                labelid = musicstore.todo_labels.pop()
                label = tlb.get_label(labelid)
                logger.debug(label)
                musicstore.put_label(label)
                time.sleep(SCRAPE_TIMEOUT)

            logger.info("TODO queue sizes: tracks=%d, artists=%d, labels=%d, tracklists=%d",
                        len(musicstore.todo_tracks),
                        len(musicstore.todo_artists),
                        len(musicstore.todo_labels),
                        len(musicstore.todo_tracklists))

            counter = counter + 1
        except ConnectionError:
            logger.warning("Caught connection error")
        except RateLimitException:
            logger.warning("Ran into ratelimit!!! Waiting for 61 minutes")
            time.sleep(60 * 61)


def go_real():
    datafolder = "../results"
    logger = logging.getLogger("main")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel("INFO")
    logger.info("Using data folder: " + datafolder)

    todofile = datafolder + "/todo.json"

    realmusicstore = FileSystemMusicStorage(datafolder, append=True)
    musicstore = TrackingMissingMusicStorage(realmusicstore)
    if os.path.isfile(todofile):
        musicstore.import_todolist(todofile)
    else:
        musicstore.todo_tracklists.add(START_TRACKLIST)

    try:
        work_recursive(musicstore)
    finally:
        musicstore.export_todolist(todofile)

# TODO: consider track Musicstyle table (2nx3up1x)
# TODO: consider artist side table: Similar Artist Names (2k4skk7n)
# TODO: consider track mode for artists: Other Produced Tracks (l116r4)
# TODO: consider artist table: Name Changed To (2jvxuz4)


go_real()
