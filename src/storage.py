from domain import *
import abc
import jsonpickle
from datetime import timedelta
import isodate
import json
import logging


class TimeDeltaJSONHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        return isodate.duration_isoformat(obj)


jsonpickle.handlers.registry.register(timedelta, TimeDeltaJSONHandler)


class MusicStorage(abc.ABC):
    @abc.abstractmethod
    def has_track(self, trackid):
        raise NotImplementedError()

    @abc.abstractmethod
    def has_artist(self, artistid):
        raise NotImplementedError()

    @abc.abstractmethod
    def has_label(self, labelid):
        raise NotImplementedError()

    @abc.abstractmethod
    def has_tracklist(self, tlid):
        raise NotImplementedError()

    @abc.abstractmethod
    def put_track(self, track: Track):
        raise NotImplementedError()

    @abc.abstractmethod
    def put_artist(self, artist: Artist):
        raise NotImplementedError()

    @abc.abstractmethod
    def put_label(self, label: Label):
        raise NotImplementedError()

    @abc.abstractmethod
    def put_tracklist(self, tracklist: Tracklist):
        raise NotImplementedError()


class FileSystemMusicStorage(MusicStorage):
    def __init__(self, folder: str, append=False):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel("DEBUG")
        self.logger.addHandler(logging.StreamHandler())
        self.tracks = set()
        self.artists = set()
        self.labels = set()
        self.tracklists = set()

        if append:
            with open(folder + "/tracks.txt") as file:
                for line in file:
                    track_obj = json.loads(line)
                    self.tracks.add(track_obj["id"])
            with open(folder + "/artists.txt") as file:
                for line in file:
                    artist_obj = json.loads(line)
                    self.artists.add(artist_obj["id"])
            with open(folder + "/labels.txt") as file:
                for line in file:
                    label_obj = json.loads(line)
                    self.labels.add(label_obj["id"])
            with open(folder + "/tracklists.txt") as file:
                for line in file:
                    tracklist_obj = json.loads(line)
                    self.tracklists.add(tracklist_obj["id"])

        self.file_tracks = open(folder + "/tracks.txt", "a" if append else "w")
        self.file_artists = open(folder + "/artists.txt", "a" if append else "w")
        self.file_labels = open(folder + "/labels.txt", "a" if append else "w")
        self.file_tracklists = open(folder + "/tracklists.txt", "a" if append else "w")

        self.logger.debug("Loaded %d tracks" % len(self.tracks))
        self.logger.debug("Loaded %d artists" % len(self.artists))
        self.logger.debug("Loaded %d labels" % len(self.labels))
        self.logger.debug("Loaded %d tracklists" % len(self.tracklists))

    def __del__(self):
        self.file_tracks.close()
        self.file_artists.close()
        self.file_labels.close()
        self.file_tracklists.close()

    def has_track(self, trackid):
        return trackid in self.tracks

    def has_artist(self, artistid):
        return artistid in self.artists

    def has_label(self, labelid):
        return labelid in self.labels

    def has_tracklist(self, tlid):
        return tlid in self.tracklists

    def put_track(self, track: Track):
        self.file_tracks.write(jsonpickle.encode(track, unpicklable=False) + "\n")
        self.tracks.add(track)

    def put_artist(self, artist: Artist):
        self.file_artists.write(jsonpickle.encode(artist, unpicklable=False) + "\n")
        self.artists.add(artist)

    def put_label(self, label: Label):
        self.file_labels.write(jsonpickle.encode(label, unpicklable=False) + "\n")
        self.labels.add(label)

    def put_tracklist(self, tracklist: Tracklist):
        self.file_tracklists.write(jsonpickle.encode(tracklist, unpicklable=False) + "\n")
        self.tracks.add(tracklist)


class TemporaryMusicStorage(MusicStorage):

    def __init__(self):
        self.tracks = {}
        self.artists = {}
        self.labels = {}
        self.tracklists = {}

    def has_track(self, trackid):
        return trackid in self.tracks

    def has_artist(self, artistid):
        return artistid in self.artists

    def has_label(self, labelid):
        return labelid in self.labels

    def has_tracklist(self, tlid):
        return tlid in self.tracklists

    def put_track(self, track: Track):
        self.tracks[track.id] = track

    def put_artist(self, artist: Artist):
        self.artists[artist.id] = artist

    def put_label(self, label: Label):
        self.labels[label.id] = label

    def put_tracklist(self, tracklist: Tracklist):
        self.tracklists[tracklist.id] = tracklist

    def store_to_disk(self, file: str):
        with open(file, "w") as file:
            file.write(jsonpickle.encode(self, unpicklable=False))


class TrackingMissingMusicStorage(MusicStorage):

    def __init__(self, real: MusicStorage):
        self.real = real
        self.todo_tracks = set()
        self.todo_artists = set()
        self.todo_labels = set()
        self.todo_tracklists = set()

    def put_track(self, track: Track):
        self.real.put_track(track)
        if track.id in self.todo_tracks:
            self.todo_tracks.remove(track.id)
        self._handle_artists(track.artists)
        self._handle_labels(track.labels)
        self._handle_tracklists(track.tracklists)
        self._handle_tracks(track.remixes)
        self._handle_tracks(track.remix_of)
        self._handle_tracks(track.mashups)
        self._handle_tracks(track.mashup_tracks)

    def put_artist(self, artist: Artist):
        self.real.put_artist(artist)
        if artist.id in self.todo_artists:
            self.todo_artists.remove(artist.id)
        self._handle_artists(artist.members)
        self._handle_artists(artist.partOf)
        self._handle_tracks(artist.tracks)
        self._handle_artists(artist.aliases)
        self._handle_tracks(artist.tracks_presented)
        self._handle_tracks(artist.tracks_featured)
        self._handle_tracks(artist.mashups)

    def put_label(self, label: Label):
        self.real.put_label(label)
        if label.id in self.todo_labels:
            self.todo_labels.remove(label.id)

    def put_tracklist(self, tracklist: Tracklist):
        self.real.put_tracklist(tracklist)
        if tracklist.id in self.todo_tracklists:
            self.todo_tracklists.remove(tracklist.id)
        self._handle_tracks(tracklist.tracks)

    def has_track(self, trackid):
        return self.real.has_track(trackid)

    def has_artist(self, artistid):
        return self.real.has_artist(artistid)

    def has_label(self, labelid):
        return self.real.has_label(labelid)

    def has_tracklist(self, tlid):
        return self.real.has_tracklist(tlid)

    def _handle_tracks(self, tracks):
        for t in filter(lambda tid: not self.has_track(tid), tracks):
            self.todo_tracks.add(t)

    def _handle_artists(self, artists):
        for a in filter(lambda aid: not self.has_artist(aid), artists):
            self.todo_artists.add(a)

    def _handle_labels(self, labels):
        for l in filter(lambda lid: not self.has_label(lid), labels):
            self.todo_labels.add(l)

    def _handle_tracklists(self, tracklists):
        for tl in filter(lambda lid: not self.has_tracklist(lid), tracklists):
            self.todo_tracklists.add(tl)

    def export_todolist(self, todofile):
        obj = {
            "tracks": list(self.todo_tracks),
            "artists": list(self.todo_artists),
            "labels": list(self.todo_labels),
            "tracklists": list(self.todo_tracklists)
        }
        with open(todofile, "w") as file:
            json.dump(obj, file)

    def import_todolist(self, todofile):
        with open(todofile, "r") as file:
            todos = json.load(file)
            self.todo_tracks = set(todos["tracks"])
            self.todo_artists = set(todos["artists"])
            self.todo_labels = set(todos["labels"])
            self.todo_tracklists = set(todos["tracklists"])
