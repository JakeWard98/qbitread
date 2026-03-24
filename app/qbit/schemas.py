from pydantic import BaseModel


class TorrentInfo(BaseModel):
    hash: str = ""
    name: str = ""
    size: int = 0
    progress: float = 0.0
    dlspeed: int = 0
    upspeed: int = 0
    eta: int = 0
    ratio: float = 0.0
    state: str = ""
    category: str = ""
    num_seeds: int = 0
    num_leechs: int = 0
    added_on: int = 0


class TransferInfo(BaseModel):
    dl_info_speed: int = 0
    up_info_speed: int = 0
    dl_info_data: int = 0
    up_info_data: int = 0
