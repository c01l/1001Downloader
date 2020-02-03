import json
import isodate
from typing import Callable, IO, Dict


class TTLConverter:

    def __init__(self, folder: str):
        self.folder = folder
        self.prefix = "tl1001"

    def export(self, filename: str):
        with open(filename, "w", encoding="utf8") as file:
            self._write_header(file)
            self._write_from_file(file, "artists.txt", self._write_artists)
            self._write_from_file(file, "labels.txt", self._write_labels)
            self._write_from_file(file, "tracks.txt", self._write_tracks)

    def _write_header(self, outfile: IO):
        outfile.write("@prefix mo: <http://purl.org/ontology/mo/> . \n")
        outfile.write("@prefix dc: <http://purl.org/dc/elements/1.1/> . \n")
        outfile.write("@prefix foaf: <http://xmlns.com/foaf/0.1/> .\n")
        outfile.write("@prefix "+self.prefix+": <http://1001tracklists.com/> .\n")
        outfile.write("@prefix owl: <http://www.w3.org/2002/07/owl#> .\n")
        outfile.write("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n")
        outfile.write("@prefix semsys: <http://www.semsysg20.org/ontology#> .\n")

    def _conv_pred(self, pred):
        return "<"+self.prefix+":"+pred+">"

    def _conv_artist(self, artistid: str) -> str:
        return self.prefix + ":" + artistid

    def _conv_track(self, trackid: str) -> str:
        return self.prefix + ":" + trackid

    def _conv_label(self, labelid: str) -> str:
        return self.prefix + ":" + labelid

    def _conv_tracklist(self, tracklist: str) -> str:
        return self.prefix + ":" + tracklist

    def _write_from_file(self, outfile: IO, filename: str, func: Callable[[IO, Dict], None]):
        with open(self.folder + "/" + filename) as file:
            for line in file:
                obj = json.loads(line)
                func(outfile, obj)

    def _write_artists(self, out, a):
        out.write(self._conv_artist(a["id"]) + " a mo:MusicGroup ;\n")
        for member in a["members"]:
            out.write(" foaf:member " + self._conv_artist(member) + " ;\n")
        # TODO partOf
        if "aliases" in a:
            for alias in a["aliases"]:
                out.write(" owl:sameAs " + self._conv_artist(alias) + " ;\n")
        out.write(" foaf:name \"" + a["name"] + "\" .\n\n")

    def _write_labels(self, out, label):
        out.write(self._conv_label(label["id"]) + " a mo:Label ; \n foaf:name \"" + label["name"] + "\" .\n")

    def _write_tracks(self, out, track):
        s = self._conv_track(track["id"]) + " a mo:Track ; \n"
        s = s + " dc:title \"" + track["name"] + "\" ; \n"
        if track["duration"] != -1:
            delta = isodate.parse_duration(track["duration"])
            s = s + "mo:duration" + " \"" + str(delta.seconds) + str(delta.microseconds / 1000) + "\" ; \n"
        for artist in track["artists"]:
            s = s + (" foaf:maker " + self._conv_artist(artist) + " ; \n")
        for label in track["labels"]:
            s = s + (" mo:label " + self._conv_label(label) + " ; \n")
        for tracklist in track["tracklists"]:
            s = s + (self._conv_pred("tracklist") + " " + self._conv_tracklist(tracklist) + " ; \n")
        if "remix" in track:
            for remix in track["remix"]:
                s = s + (" semsys:hasRemix" + " " + self._conv_track(remix) + " ; \n")
        if "remix_of" in track:
            for remixOf in track["remix_of"]:
                s = s + (" semsys:remixOf" + " " + self._conv_track(remixOf) + " ; \n")
        if "mashup" in track:
            for mashup in track["mashup"]:
                s = s + (" semsys:hasRemix" + " " + self._conv_track(mashup) + " ; \n")
        if "mashup_tracks" in track:
            for mashup_tracks in track["mashup_tracks"]:
                s = s + (" semsys:remixOf" + " " + self._conv_track(mashup_tracks) + " ; \n")
        if "medialinks" in track:
            for medialink in track["medialinks"]:
                type = medialink["type"]
                if type == "spotify":
                    pred = "semsys:spotifyExternalUrl"
                elif type == "youtube":
                    pred = "semsys:youtubeLink"
                else:
                    pred = self._conv_pred(type + "_link")
                link = medialink["link"]
                if link[0:5] != "https" and link[0:4] == "http":
                    link = "https" + link[4:]
                s = s + " " + pred + " \"" + link + "\"^^xsd:anyURI ; \n"
        s = s[:-3] + ". \n"
        out.write(s)


datafolder = "../results"
conv = TTLConverter(datafolder)

conv.export("../results/data.ttl")
