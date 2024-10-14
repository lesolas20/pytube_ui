import os
import json
import platform

from http.client import RemoteDisconnected

import pytube

from rich.text import Text
from rich.console import RenderableType

from textual import on
from textual import work
from textual.worker import Worker
from textual.app import App, ComposeResult
from textual.containers import VerticalScroll, Center
from textual.widgets import (
    Header, Footer,
    Static, Input, ProgressBar, Label, Select
)

from typing import Type
from collections.abc import Iterable


class Utils:
    @staticmethod
    def values2options(values: Iterable[str]) -> list[tuple[str, str]]:
        return [(option, option) for option in values]

    @staticmethod
    def compose_streams_value(video: bool, audio: bool) -> str:
        return f"{video * 'Video'}{(video & audio) * ' & '}{audio * 'Audio'}"

    @staticmethod
    def decompose_streams_value(value: str) -> tuple[bool, bool]:
        return (("Video" in value), ("Audio" in value))

    @staticmethod
    def select_bitrate(
        mp4_bitrate: str | list,
        webm_bitrate: str | list,
        format: str
    ) -> str | list:
        match format:
            case "mp4":
                return mp4_bitrate
            case "webm":
                return webm_bitrate


class Settings:
    SELECT_VALUES = {
        "streams": {
            "values": [
                "Video & Audio",
                "Video",
                "Audio"
            ],
            "default": "Video & Audio"
        },
        "format": {
            "values": [
                "mp4",
                "webm"
            ],
            "default": "mp4"
        },
        "resolution": {
            "values": [
                "144p",
                "240p",
                "360p",
                "480p",
                "720p",
                "1080p",
                "1440p",
                "2160p",
                "4320p"
            ],
            "default": "720p"
        },
        "bitrate": {
            "mp4_values": [
                "48kbps",
                "128kbps",
                "192kbps",
                "256kbps",
                "384kbps"
            ],
            "webm_values": [
                "50kbps",
                "70kbps",
                "128kbps",
                "160kbps",
                "256kbps"
            ],
            "mp4_default": "128kbps",
            "webm_default": "128kbps"
        },
    }

    def __init__(self, path: str) -> None:
        self.path = path

        try:
            self._data = self._load(path)

        except Exception:
            self._data = self._get_default(self.SELECT_VALUES)
            self._save(path, self._data)

        self._set_values(self._data)

    def save(self) -> None:
        print(f"Settings.save\"({self.path}\", {self._get_values()})")

        self._save(self.path, self._get_values())

    @staticmethod
    def _save(path: str, data: dict) -> None:
        with open(path, "w") as file:
            file.write(json.dumps(data))

    def _load(self, path: str) -> dict:
        with open(path, "r") as file:
            data = json.loads(file.read())

        self._validate(data)

        return data

    def _validate(self, data: dict) -> None:
        if not all(
            (
                ("output_directory"   in data),
                ("download_video"     in data),
                ("download_audio"     in data),
                ("content_format"     in data),
                ("video_resolution"   in data),
                ("mp4_audio_bitrate"  in data),
                ("webm_audio_bitrate" in data)
            )
        ):
            raise KeyError()

        if not all(
            (
                isinstance(data["output_directory"],   str),
                isinstance(data["download_video"],     bool),
                isinstance(data["download_audio"],     bool),
                isinstance(data["content_format"],     str),
                isinstance(data["video_resolution"],   str),
                isinstance(data["mp4_audio_bitrate"],  str),
                isinstance(data["webm_audio_bitrate"], str)
            )
        ):
            raise TypeError()

        if not all(
            (
                (data["content_format"]     in self.SELECT_VALUES["format"]["values"]),
                (data["video_resolution"]   in self.SELECT_VALUES["resolution"]["values"]),
                (data["mp4_audio_bitrate"]  in self.SELECT_VALUES["bitrate"]["mp4_values"]),
                (data["webm_audio_bitrate"] in self.SELECT_VALUES["bitrate"]["webm_values"])
            )
        ):
            raise ValueError()

    def _get_default(self, data: dict) -> dict:
        print("Settings._get_default is called")

        video, audio = Utils.decompose_streams_value(data["streams"]["default"])
        return {
            "output_directory":   self._get_default_output_directory(),
            "download_video"  :   video,
            "download_audio"  :   audio,
            "content_format":     data["format"]["default"],
            "video_resolution":   data["resolution"]["default"],
            "mp4_audio_bitrate":  data["bitrate"]["mp4_default"],
            "webm_audio_bitrate": data["bitrate"]["webm_default"],
        }

    @staticmethod
    def _get_default_output_directory() -> str:
        system = platform.system()

        if system == "Linux":
            if os.path.exists("/storage/emulated/0/"):    # Android
                path = "/storage/emulated/0/Download"
            else:
                path = os.path.join(os.getenv("HOME"), "Downloads")

        elif system == "Windows":
            path = os.path.join(
                os.getenv("HOMEDRIVE"),
                os.getenv("HOMEPATH"),
                "Downloads"
            )

        elif system == "Darwin":
            path = path = os.path.join(os.getenv("HOME"), "Downloads")

        else:
            path = os.path.join(os.getenv("HOME"), "Downloads")

        return path

    def _set_values(self, data: dict) -> None:
        self.output_directory   = data["output_directory"]
        self.download_video     = data["download_video"]
        self.download_audio     = data["download_audio"]
        self.content_format     = data["content_format"]
        self.video_resolution   = data["video_resolution"]
        self.mp4_audio_bitrate  = data["mp4_audio_bitrate"]
        self.webm_audio_bitrate = data["webm_audio_bitrate"]

    def _get_values(self) -> dict:
        return {
            "output_directory":   self.output_directory,
            "download_video":     self.download_video,
            "download_audio":     self.download_audio,
            "content_format":     self.content_format,
            "video_resolution":   self.video_resolution,
            "mp4_audio_bitrate":  self.mp4_audio_bitrate,
            "webm_audio_bitrate": self.webm_audio_bitrate,
        }


class YouTubeVideoDownloader:
    def __init__(self, widget: Static, URL: str) -> None:
        self.widget = widget
        self.URL = URL
        self.downloader = self.create_downloader(URL=URL)

        if self.downloader is not None:
            self.widget.download()

    def create_downloader(self, URL: str) -> pytube.YouTube | None:
        try:
            downloader = pytube.YouTube(URL)

        except Exception as error:
            self._handle_error(error=error)
            return None

        else:
            return downloader

    def _handle_error(
        self,
        error: Type[pytube.exceptions.PytubeError | Exception]
    ) -> None:
        if isinstance(error, pytube.exceptions.MaxRetriesExceeded):
            error_feedback = "Maximum number of retries exceeded. Please check your Internet connection and try again."

        elif isinstance(error, pytube.exceptions.HTMLParseError):
            error_feedback = "HTML could not be parsed. Please try again later."

        elif isinstance(error, pytube.exceptions.RegexMatchError):
            error_feedback = "Could not find the video. Please check whether this URL is correct."

        elif isinstance(error, pytube.exceptions.AgeRestrictedError):
            error_feedback = "The video is age-restricted and cannot be accessed without logging in."

        elif isinstance(error, pytube.exceptions.LiveStreamError):
            error_feedback = "The video is being streamed live and cannot be loaded."

        elif isinstance(error, pytube.exceptions.VideoPrivate):
            error_feedback = "The video is private."

        elif isinstance(error, pytube.exceptions.RecordingUnavailable):
            error_feedback = "The video does not have a live stream recording available."

        elif isinstance(error, pytube.exceptions.MembersOnly):
            error_feedback = "The video is available only for channel members."

        elif isinstance(error, pytube.exceptions.VideoRegionBlocked):
            error_feedback = "The video is not available in your region."

        else:
            error_feedback = "Sorry, something went wrong. Please check your Internet connection and try again."

        try:
            APP.call_from_thread(
                self.widget.output_error_feedback,
                error_feedback
            )
        except RuntimeError:
            self.widget.output_error_feedback(text=error_feedback)


    def download(self) -> None:
        try:
            streams = self.downloader.streams

        except Exception as error:
            self._handle_error(error=error)
            return None

        streams = streams.filter(subtype=SETTINGS.content_format)

        downloaded_data = 0
        total_data = 0

        # Select the video stream
        if SETTINGS.download_video:
            video_stream, total_data = self._get_video_stream(
                streams,
                total_data
            )

        # Select the audio stream
        if SETTINGS.download_audio:
            audio_stream, total_data = self._get_audio_stream(
                streams,
                total_data
            )

        # Start the ProgressBar
        self.widget.start_downloading()

        # Download the video stream
        if SETTINGS.download_video:
            video_path, downloaded_data = self._download_video_stream(
                video_stream,
                downloaded_data,
                total_data
            )

        # Download the audio stream
        if SETTINGS.download_audio:
            audio_path, downloaded_data = self._download_audio_stream(
                audio_stream,
                downloaded_data,
                total_data
            )

        # Merge the audio and video if needed
        ...    # TODO

    def _download_stream(
        self,
        stream: pytube.Stream,
        bytes_received: int,
        bytes_total: int
    ) -> None:
        def on_complete(
            stream: pytube.Stream,
            file_path: str
        ) -> None:
            video = SETTINGS.download_video
            audio = SETTINGS.download_audio
            bytes = bool(bytes_received)

            if not ((video & audio) ^ bytes):
                # Called only if the current stream is the last one
                APP.call_from_thread(
                    self.widget.set_progress,
                    self.widget.PROGRESS_STEPS
                )

        def on_progress(
            stream: pytube.Stream,
            chunk: bytes,
            bytes_remaining: int
        ) -> None:
            bytes_progress = bytes_received + (stream.filesize - bytes_remaining)
            progress_percentage = int(
                self.widget.PROGRESS_STEPS * (bytes_progress / bytes_total)
            )

            APP.call_from_thread(
                self.widget.set_progress,
                progress_percentage
            )

        self.downloader.register_on_complete_callback(on_complete)
        self.downloader.register_on_progress_callback(on_progress)

        filename_prefix: str = f"({stream.type}) " * stream.is_adaptive

        stream.download(
            output_path=SETTINGS.output_directory,
            filename_prefix=filename_prefix
        )

    def _get_video_stream(
        self,
        streams: pytube.query.StreamQuery,
        total_data: int
    ) -> tuple[pytube.Stream, int]:
        video_streams = streams.filter(type="video", adaptive=True)
        video_stream = self._get_nearest_by_resolution(
            streams=video_streams,
            resolution=SETTINGS.video_resolution
        )
        total_data += video_stream.filesize

        return (video_stream, total_data)

    def _get_audio_stream(
        self,
        streams: pytube.query.StreamQuery,
        total_data: int
    ) -> tuple[pytube.Stream, int]:
        audio_streams = streams.filter(type="audio")
        audio_stream = self._get_nearest_by_bitrate(
            streams=audio_streams,
            bitrate=(
                SETTINGS.mp4_audio_bitrate
                if SETTINGS.content_format == "mp4"
                else SETTINGS.webm_audio_bitrate
            )
        )
        total_data += audio_stream.filesize

        return (audio_stream, total_data)

    def _download_video_stream(
        self,
        stream: pytube.Stream,
        downloaded_data: int,
        total_data: int
    ) -> tuple[str, int]:
        video_path = self._download_stream(
            stream=stream,
            bytes_received=downloaded_data,
            bytes_total=total_data
        )

        downloaded_data += stream.filesize

        return (video_path, downloaded_data)

    def _download_audio_stream(
        self,
        stream: pytube.Stream,
        downloaded_data: int,
        total_data: int
    ) -> tuple[str, int]:
        audio_path = self._download_stream(
            stream=stream,
            bytes_received=downloaded_data,
            bytes_total=total_data
        )

        downloaded_data += stream.filesize

        return (audio_path, downloaded_data)

    @staticmethod
    def _get_nearest_by_resolution(
        streams: pytube.query.StreamQuery,
        resolution: str
    ) -> pytube.Stream:
        def difference(stream: pytube.Stream) -> int:
            return abs(
                int(stream.resolution[:-1]) - int(resolution[:-1])
            )

        return min(streams, key=difference)

    @staticmethod
    def _get_nearest_by_bitrate(
        streams: pytube.query.StreamQuery,
        bitrate: str
    ) -> pytube.Stream:
        def difference(stream: pytube.Stream) -> int:
            return abs(
                int(stream.abr[:-4]) - int(bitrate[:-4])
            )

        return min(streams, key=difference)


class Video(Static):
    PROGRESS_STEPS = 100

    def __init__(
        self,
        renderable: RenderableType = "",
        *,
        expand: bool = False,
        shrink: bool = False,
        markup: bool = True,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        URL: str = ""
    ) -> None:
        super().__init__(
            renderable=renderable,
            expand=expand,
            shrink=shrink,
            markup=markup,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled
        )

        self.URL = URL

    def compose(self) -> ComposeResult:
        yield Input(placeholder="URL", id="URL_input")

        with Center():
            yield ProgressBar(id="download_progress")

        yield Label("", id="output")

    def on_mount(self) -> None:
        if self.URL:
            self.create_downloader(URL=self.URL)

    @on(Input.Submitted)
    def create_downloader(
        self,
        event: Input.Submitted = None,
        URL: str = ""
    ) -> None:
        text = URL or event.value

        self.reset_downloading()

        URLs = text.split()
        text, URLs = URLs[0], URLs[1:]

        self.query_one("#URL_input").value = text
        self.downloader = YouTubeVideoDownloader(
            widget=self,
            URL=text
        )

        for URL in URLs:
            APP.action_add_video(URL=URL)

    @work(exclusive=True, thread=True)
    def download(self) -> None:
        # Workers are tied to DOM nodes, so they have to be created in
        #     a DOM node.
        self.downloader.download()

    def start_downloading(self) -> None:
        self.remove_class("error")
        self.query_one("#download_progress").update(
            total=self.PROGRESS_STEPS,
            progress=0
        )

    def reset_downloading(self) -> None:
        self.remove_class("error")
        self.query_one("#download_progress").update(total=None)

    def output_error_feedback(self, text: str) -> None:
        self.add_class("error")
        self.query_one("#output")._renderable = Text(text)

    def set_progress(self, value: int) -> None:
        self.query_one("#download_progress").update(progress=value)


class PytubeApp(App):
    CSS_PATHS = ["pytube_ui_light.tcss", "pytube_ui_dark.tcss"]
    CSS_PATH = CSS_PATHS[1]
    TITLE = "Pytube UI"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "toggle_settings", "Settings"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("a", "add_video", "Add"),
        ("r", "remove_videos", "Remove all videos"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

        with VerticalScroll(id="videos"):
            yield Video()

        with VerticalScroll(id="settings"):
            bitrate = SETTINGS.SELECT_VALUES["bitrate"]

            yield Select(
                options=Utils.values2options(
                    SETTINGS.SELECT_VALUES["streams"]["values"]
                ),
                value=Utils.compose_streams_value(
                    SETTINGS.download_video,
                    SETTINGS.download_audio
                ),
                allow_blank=False,
                id="streams"
            )
            yield Select(
                options=Utils.values2options(
                    SETTINGS.SELECT_VALUES["format"]["values"]
                ),
                value=SETTINGS.content_format,
                allow_blank=False,
                id="format"
            )
            yield Select(
                options=Utils.values2options(
                    SETTINGS.SELECT_VALUES["resolution"]["values"]
                ),
                value=SETTINGS.video_resolution,
                allow_blank=False,
                id="resolution"
            )
            yield Select(
                options=Utils.values2options(
                    Utils.select_bitrate(
                        bitrate["mp4_values"],
                        bitrate["webm_values"],
                        SETTINGS.content_format
                    )
                ),
                value=Utils.select_bitrate(
                    SETTINGS.mp4_audio_bitrate,
                    SETTINGS.webm_audio_bitrate,
                    SETTINGS.content_format
                ),
                allow_blank=False,
                id="bitrate"
            )

    @on(Select.Changed)
    def update_settings(self, event: Select.Changed) -> None:
        id, value = event.select.id, event.value

        match id:
            case "streams":
                video, audio = Utils.decompose_streams_value(value)
                SETTINGS.download_video = video
                SETTINGS.download_audio = audio

            case "format":
                SETTINGS.content_format = value

                bitrate_select = self.query_one("#bitrate")

                bitrate = SETTINGS.SELECT_VALUES["bitrate"]

                bitrate_select.set_options(
                    Utils.values2options(
                        Utils.select_bitrate(
                            bitrate["mp4_values"],
                            bitrate["webm_values"],
                            SETTINGS.content_format
                        )
                    )
                )
                bitrate_select.value = Utils.select_bitrate(
                    SETTINGS.mp4_audio_bitrate,
                    SETTINGS.webm_audio_bitrate,
                    SETTINGS.content_format
                )

            case "resolution":
                SETTINGS.video_resolution = value

            case "bitrate":
                match SETTINGS.content_format:
                    case "mp4":
                        SETTINGS.mp4_audio_bitrate = value
                    case "webm":
                        SETTINGS.webm_audio_bitrate = value


    def action_add_video(self, URL: str = "") -> None:
        new_video = Video(URL=URL)
        self.query_one("#videos").mount(new_video)
        new_video.scroll_visible()

    def action_remove_videos(self) -> None:
        videos = self.query("Video")
        videos.remove()

    def action_toggle_settings(self) -> None:
        settings = self.query_one("#settings")

        if settings.has_class("-open"):
            SETTINGS.save()

        settings.toggle_class("-open")

    def action_toggle_dark(self) -> None:
        self.dark = not self.dark


if __name__ == "__main__":
    SETTINGS = Settings("settings.json")
    APP = PytubeApp()
    APP.run()
