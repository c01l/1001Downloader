from abc import ABC, abstractmethod


def auto_str(cls):
    def __str__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join("%s='%s'" % item for item in vars(self).items())
        )
    cls.__str__ = __str__
    return cls


@auto_str
class Track:
    def __init__(self):
        self.id = ""
        self.name = ""
        self.artists = []
        self.labels = []
        self.duration = -1
        self.tracklists = []
        self.remixes = []
        self.remix_of = []
        self.mashups = []
        self.mashup_tracks = []  # contains the tracks that this mashup uses
        self.medialinks = []

    def add_tracklist(self, tracklistid: str):
        self.tracklists.append(tracklistid)

    def add_label(self, labelid: str):
        self.labels.append(labelid)

    def add_artists(self, artistid: str):
        self.artists.append(artistid)

    def add_remix(self, trackid):
        self.remixes.append(trackid)

    def add_remixof(self, trackid):
        self.remix_of.append(trackid)

    def add_mashup(self, mashup):
        self.mashups.append(mashup)

    def add_mashup_track(self, trackid):
        self.mashup_tracks.append(trackid)

    def add_medialink(self, medialink):
        self.medialinks.append(medialink)


@auto_str
class Label:
    def __init__(self):
        self.id = ""
        self.name = ""


@auto_str
class Artist:
    def __init__(self):
        self.id = ""
        self.name = ""
        self.tracks = []
        self.mashups = []
        self.members = []
        self.partOf = []
        self.remixes = []
        self.aliases = []
        self.tracks_featured = []
        self.tracks_presented = []

    def add_mashup(self, trackid):
        self.mashups.append(trackid)

    def add_track_featured(self, trackid):
        self.tracks_featured.append(trackid)

    def add_track_presented(self, trackid):
        self.tracks_presented.append(trackid)

    def add_track(self, trackid):
        self.tracks.append(trackid)

    def add_remix(self, trackid):
        self.remixes.append(trackid)

    def add_member(self, artistid):
        self.members.append(artistid)

    def add_partof(self, artistid):
        self.partOf.append(artistid)

    def add_alias(self, aliasid):
        self.aliases.append(aliasid)

@auto_str
class Tracklist:
    def __init__(self):
        self.id = ""
        self.name = ""
        self.tracks = []

    def add_track(self, trackid: str):
        self.tracks.append(trackid)


class Medialink(ABC):
    @abstractmethod
    def get_obj(self):
        raise NotImplementedError()


class YoutubeMedialink(Medialink):
    def __init__(self, ytid: str):
        self.ytid = ytid

    def get_obj(self):
        return {"type": "youtube", "link": str(self)}

    def __str__(self):
        return "http://youtube.com/video/" + self.ytid


class SpotifyMedialink(Medialink):
    def __init__(self, spid: str):
        self.spid = spid

    def get_obj(self):
        return {"type": "spotify", "link": str(self)}

    def __str__(self):
        return "http://open.spotify.com/track/" + self.spid


class SoundcloudMedialink(Medialink):
    def __init__(self, link):
        self.link = link

    def get_obj(self):
        return {"type": "soundcloud", "link": str(self)}

    def __str__(self):
        return self.link


class BeatportMedialink(Medialink):
    def __init__(self, bpid):
        self.bpid = bpid

    def get_obj(self):
        return {"type": "beatport", "link": str(self)}

    def __str__(self):
        return "https://embed.beatport.com/player/?id=" + self.bpid + "&type=track"


class EntityNotFoundError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


class RateLimitException(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)