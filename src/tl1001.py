from http.client import RemoteDisconnected

from domain import *
import requests
from bs4 import BeautifulSoup, Tag
import isodate
import random
import re
import logging
import time


BASEURL = "https://www.1001tracklists.com/"


def check_rate_limit(resp, *args, **kwargs):
    if resp.status_code == 403:
        if "Your access has been blocked for one hour due to abnormal use." in resp.text:
            raise RateLimitException("Ran into ratelimit")


class TLBackend:

    def __init__(self) -> None:
        self.logger = logging.getLogger("1001tl")
        self.logger.setLevel("DEBUG")
        self.logger.addHandler(logging.StreamHandler())
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
        self._renew_session()
        self.session.hooks["response"] = [check_rate_limit, self._renew_session]

    def _renew_session(self, *args, **kwargs):
        self.session.cookies["guid"] = str(random.random()*100000000000)

    def _get_html_soup(self, html):
        html = re.sub(r'&(?!amp;)', r'&amp;', html)
        return BeautifulSoup(html, "html.parser")

    def search_track(self, trackname: str):
        req = self.session.post(BASEURL + "search/result.php",
                            data={"main_search": trackname, "search_selection": 2})
        bs = self._get_html_soup(req.text)
        print(bs)
        trs = bs.select("#middleDiv tr.trTog")
        print(trs)

    def _parse_track_metadata(self, bs, track: Track) -> Track:
        meta_duration = bs.select("body > meta[itemprop=duration]")
        if len(meta_duration) > 0:
            track.duration = isodate.parse_duration(meta_duration[0]["content"])
        else:
            self.logger.warning("Duration not set: " + str(meta_duration))
        meta = bs.select("body > meta[itemprop=name]")[0]
        track.name = meta["content"]
        return track

    def _parse_track_sides(self, bs, track: Track) -> Track:
        side_boxes = bs.find_all("div", {"class": "side"})
        for side_box in side_boxes:
            header = side_box.select("table.sideTop th")[0].contents[0]
            if header is not None and header.strip() == track.name:
                for table in side_box.find_all("table", {"class": "default"}):
                    subheader = table.find("th").contents[-1].strip()
                    if subheader == "Short Link" or subheader == "Statistics" or subheader == track.name:
                        pass  # do nothing with this
                    elif subheader == "Remix Of" or subheader == "Rework Of":
                        # TODO CHECKME assume only one track
                        url = table.find("a")["href"]
                        track.add_remixof(url.split("/")[2])
                    elif subheader == "Label":
                        atag = table.find("a")
                        if atag:
                            url = atag["href"]
                            track.add_label(url.split("/")[2])
                    elif subheader == "Supported By":
                        pass  # TODO consider adding info about who has played that
                    else:
                        self.logger.warning("Omitting side table " + subheader)
            elif header is not None and header.strip() == "Additional Credits":
                # Feature as an example
                subheader = side_box.find_all("td", {"class": "color3"})
                for header in subheader:
                    if header.contents[0].strip() == "Feature":
                        content = header.parent.next_sibling
                        print(content)
            else:
                # expect that it is an artist
                url = side_box.select("table.sideTop th a")[0]["href"]
                track.add_artists(url.split("/")[2])
        return track

    def _parse_track_tracklists(self, bs, track: Track) -> Track:
        trs = bs.select("#middleDiv .tlTbl tr .tlLink a")
        for tr in trs:
            track.add_tracklist(tr["href"].split("/")[2])
        return track

    def _parse_track_remixes(self, bs, track: Track) -> Track:
        track_tbl = bs.find(lambda tag: tag.name == "th" and
                                        ("Remixes" in tag.text or
                                         "Mashups / Bootlegs" in tag.text or
                                         "Track Is A Mashup Containing These Tracks" in tag.text))
        if track_tbl is not None:
            mode = None
            for track_row in track_tbl.parent.parent.children:
                # print(track_row)
                if type(track_row) != Tag:
                    continue
                if track_row.name != "tr":
                    continue
                th = track_row.find("th")
                if th is not None:
                    mode = th.string.strip()
                    continue
                if track_row.has_attr("class") and "adRow" in track_row["class"]:
                    continue  # skip ads...

                track_link = track_row.find("a")
                targetid = track_link["href"].split("/")[2]
                if mode == "Remixes":
                    track.add_remix(targetid)
                elif mode == "Mashups / Bootlegs":
                    track.add_mashup(targetid)
                elif mode == "Track Is A Mashup Containing These Tracks":
                    track.add_mashup_track(targetid)
                else:
                    self.logger.warning("Unknown track mode '%s'" % mode)
        return track

    def _parse_mediaplayer_link(self, src) -> Medialink:
        m = re.match(r"^https://www.youtube.com/embed/([^?]+)?.*$", src)
        if m:
            id = m.group(1)
            return YoutubeMedialink(id)
        m = re.match(r".*https://api.soundcloud.com/tracks/([0-9]+).*", src)
        if m:
            id = m.group(1)
            req = self.session.get("https://w.soundcloud.com/player/?url=https://api.soundcloud.com/tracks/" + id)
            m2 = re.match(r'"permalink_url":"(.*)"', req.text)  # TODO fix in the future
            if m2:
                return SoundcloudMedialink(m2.group(1))
            else:
                logging.error("Could not fetch soundcloud link: %s", req.text)
        m = re.match(r"^https://open.spotify.com/embed/track/(.*)$", src)
        if m:
            id = m.group(1)
            return SpotifyMedialink(id)
        m = re.match(r"^https://embed.beatport.com/player/?id=([0-9]+).*", src)
        if m:
            id = m.group(1)
            return BeatportMedialink(id)
        return None

    def _get_mediaplayer(self, mid, track: Track) -> Track:
        req = self.session.get(BASEURL + "ajax/get_medialink.php?idMedia=" + mid)
        json = req.json()
        data = json["data"]
        for datae in data:
            player = self._get_html_soup(datae["player"])
            src = player.find("iframe")["src"]
            ml = self._parse_mediaplayer_link(src)
            if ml:
                track.add_medialink(ml.get_obj())
            else:
                self.logger.warning("Unknown media link: %s", src)
        return track

    def _parse_track_media(self, bs, track: Track) -> Track:
        mlinks = bs.find_all("div" , {"class": "mediaLink"})
        for ml in mlinks:
            mid = ml["data-idmedia"]
            time.sleep(5)
            try:
                track = self._get_mediaplayer(mid, track)
            except RemoteDisconnected:
                self.logger.warning("Server disconnected without sending anything")
            except:
                self.logger.warning("Could not get medialink")
        return track

    def get_track(self, trackid: str) -> Track:
        self.logger.debug("Loading track '%s'" % trackid)
        track = Track()
        track.id = trackid

        req = self.session.get(BASEURL + "track/" + trackid + "/")
        if req.status_code == 404:
            raise EntityNotFoundError("Could not find track '%s'" % trackid)

        bs = self._get_html_soup(req.text)
        track = self._parse_track_metadata(bs, track)
        track = self._parse_track_sides(bs, track)
        track = self._parse_track_tracklists(bs, track)
        track = self._parse_track_remixes(bs, track)
        track = self._parse_track_media(bs, track)

        return track

    def _parse_label_metadata(self, bs, label: Label) -> Label:
        th = bs.select("#leftDiv .sideTop th")
        label.name = th[0].contents[0].strip()
        # TODO parse sub label info
        return label

    def get_label(self, labelid: str) -> Label:
        self.logger.debug("Loading label '%s'" % labelid)
        label = Label()
        label.id = labelid

        req = self.session.get(BASEURL + "label/" + labelid + "/")
        if req.status_code == 404:
            raise EntityNotFoundError("Could not find label '%s'" % labelid)

        bs = self._get_html_soup(req.text)
        label = self._parse_label_metadata(bs, label)
        # TODO parse tracks that are released under this label

        return label

    def _parse_tracklist_metadata(self, bs, tl: Tracklist) -> Tracklist:
        meta = bs.select("body > meta[itemprop=name]")[0]
        tl.name = meta["content"]
        return tl

    def _parse_tracklist_tracks(self, bs, tl: Tracklist) -> Tracklist:
        tracks = bs.select(".tl tr.tlpItem div.tlToogleData meta[itemprop=url]")
        for track in tracks:
            tl.add_track(track["content"].split("/")[2])
        return tl

    def get_tracklist(self, tracklistid) -> Tracklist:
        self.logger.debug("Loading tracklist '%s'" % tracklistid)

        tl = Tracklist()
        tl.id = tracklistid

        req = self.session.get(BASEURL + "tracklist/" + tracklistid + "/")
        if req.status_code == 404:
            raise EntityNotFoundError("Could not find tracklist '%s'" % tracklistid)

        bs = self._get_html_soup(req.text)
        tl = self._parse_tracklist_metadata(bs, tl)
        tl = self._parse_tracklist_tracks(bs, tl)

        return tl

    def _parse_artist_sides_top(self, bs, a: Artist) -> Artist:
        topbox = bs.select("#leftContent .side table.sideTop")[0]
        a.name = topbox.find("th").contents[0].strip()
        # TODO consider adding references to other social media?
        return a

    def _parse_artist_sides(self, bs, a: Artist) -> Artist:
        a = self._parse_artist_sides_top(bs, a)
        tables = bs.select("#leftContent .side > table.default")
        for table in tables:
            if "sideTop" in table["class"]:
                continue  # already handled by parse_*_top

            th = table.find("th")
            header = th.string.strip()
            if header == "Is Part Of":
                for sibl in th.parent.next_siblings:
                    if type(sibl) != Tag:
                        continue
                    link = sibl.find("a")
                    if link is not None:
                        a.add_partof(link["href"].split("/")[2])
            elif header == "Part Members":
                for sibl in th.parent.next_siblings:
                    if type(sibl) != Tag:
                        continue
                    if not sibl.has_attr("class"):
                        continue
                    link = sibl.find("a")
                    if link is not None:
                        a.add_member(link["href"].split("/")[2])
            elif header == "Aliases":
                for sibl in th.parent.next_siblings:
                    if type(sibl) != Tag:
                        continue
                    link = sibl.find("a")
                    if link is not None:
                        a.add_alias(link["href"].split("/")[2])
            elif header == "Short Link":
                pass  # no interesting
            else:
                self.logger.warning("Did not use artist table '%s'" % header)

        return a

    def _parse_artist_tracks(self, bs, a: Artist) -> Artist:
        track_tbl = bs.find(lambda tag: tag.name == "th" and ("Tracks" in tag.text or "Remixes" in tag.text or "Mashups" in tag.text))
        if track_tbl is not None:
            mode = None
            for track_row in track_tbl.parent.parent.children:
                if type(track_row) != Tag:
                    continue
                if track_row.name != "tr":
                    continue
                th = track_row.find("th")
                if th is not None:
                    mode = th.string.strip()
                    continue
                if track_row.has_attr("class") and "adRow" in track_row["class"]:
                    continue  # skip ads...

                track_link = track_row.find("a")
                targetid = track_link["href"].split("/")[2]
                if mode == "Tracks":
                    a.add_track(targetid)
                elif mode == "Remixes":
                    a.add_remix(targetid)
                elif mode == "Mashups":
                    a.add_mashup(targetid)
                elif mode == "Featured Tracks":
                    a.add_track_featured(targetid)
                elif mode == "Presented Tracks":
                    a.add_track_presented(targetid)
                else:
                    self.logger.warning("Unknown track mode '%s'" % mode)
        return a

    def get_artist(self, artistid) -> Artist:
        self.logger.debug("Loading artist '%s'" % artistid)

        a = Artist()
        a.id = artistid

        req = self.session.get(BASEURL + "artist/" + artistid + "/")
        if req.status_code == 404:
            raise EntityNotFoundError("Could not find artist '%s'" % artistid)

        bs = self._get_html_soup(req.text)
        a = self._parse_artist_sides(bs, a)
        a = self._parse_artist_tracks(bs, a)

        return a
