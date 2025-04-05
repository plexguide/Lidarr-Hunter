"""
Upgrade functionality for Huntarr-Lidarr
"""

from upgrade.album import process_album_upgrades
from upgrade.artist import process_artist_upgrades

__all__ = ['process_album_upgrades', 'process_artist_upgrades']