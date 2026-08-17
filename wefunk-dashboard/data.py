#!/usr/bin/env python3

from pathlib import Path
from common import EXPORTS, load_csv

#
# Core exported reports
#

show_stats = load_csv(EXPORTS / "wefunk_show_match_stats.csv")
missing_tracks = load_csv(EXPORTS / "wefunk_missing_tracks.csv")
missing_tracks_engine = load_csv(EXPORTS / "wefunk_missing_tracks_engine.csv")
owned_tracks = load_csv(EXPORTS / "wefunk_owned_tracks.csv")
owned_tracks_tags = load_csv(EXPORTS / "wefunk_owned_tracks_tags.csv")
owned_tracks_enriched = load_csv(EXPORTS / "wefunk_owned_tracks_enriched.csv")
genre_dna = load_csv(EXPORTS / "wefunk_genre_dna.csv")
recommended_albums = load_csv(EXPORTS / "wefunk_recommended_albums.csv")
top_missing_artists = load_csv(EXPORTS / "wefunk_top_missing_artists.csv")
play_counts = load_csv(EXPORTS / "wefunk_show_play_counts.csv")
recent_matches = load_csv(EXPORTS / "wefunk_recent_matches.csv")
album_index = load_csv(EXPORTS / "wefunk_album_index.csv")

#
# Helpful lookup dictionaries
#

play_counts_by_show = {
    str(r.get("show_id", "")).strip(): r
    for r in play_counts
}

show_stats_by_show = {
    str(r.get("show_id", "")).strip(): r
    for r in show_stats
}


album_index_by_artist_album = {
    (
        str(r.get("artist", "")).strip().lower(),
        str(r.get("album", "")).strip().lower(),
    ): r
    for r in album_index
}
