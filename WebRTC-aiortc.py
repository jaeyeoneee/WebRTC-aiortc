import argparse
import asyncio
import json
import logging
import os
import platform
import ssl

# from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender

ROOT = os.path.dirname(__file__)

relay = None
webcam = None


def create_local_tracks():
    global relay, webcam

    # TODO: 웹캠 경로 변경, 또는 openCV를 사용하도록, 웹캠 영상 처리 방법
    options = {"framerate": "30", "video_size": "640x480"}
    if relay is None:
        if platform.system() == "Darwin":
            webcam = MediaPlayer(
                "default:none", format="avfoundation", options=options
            )
        elif platform.system() == "Windows":
            webcam = MediaPlayer(
                "video=LG Camera", format="dshow", options=options
            )
        else:
            webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
        relay = MediaRelay()
    return None, relay.subscribe(webcam.video)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="WebRTC webcam")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default:8080)"
    )

    args = parser.parse_args()

