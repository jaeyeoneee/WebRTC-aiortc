import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
import websockets
import stomper

# from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSender

ROOT = os.path.dirname(__file__)

relay = None
webcam = None
conn = None
peer_map = {}

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
                "video=LG Camera", format="dshow"
            )
        else:
            webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
        relay = MediaRelay()
    return None, relay.subscribe(webcam.video)


def create_peer(userKey):
    peer = RTCPeerConnection()

    # add track
    # TODO:audio 전달 추가, codec?
    # audio, video = create_local_tracks()

    #peer.addTrack(video)

    # TODO:iceconnectionchange

    # TODO:onicecandidate

    return peer

async def handle_offer(message_body):
    global conn
    message_body = json.loads(message_body)
    description = message_body["description"]
    user_key = message_body["userKey"]

    # offer 생성
    offer = RTCSessionDescription(sdp=description["sdp"], type=description["type"])

    # RTCPeerConnection 생성
    #TODO:여러 사람이 들어오는 경우 처리(멀티스레드?) - 우선은 한 사람과의 p2p 연결 및 트랙 전송 목표로
    local_peer = create_peer(user_key)

    peer_map[user_key] = local_peer
    await local_peer.setRemoteDescription(offer)

    # answer 전송
    # TODO:함수로 빼기?
    answer = await local_peer.createAnswer()
    await local_peer.setLocalDescription(answer)

    answer_meg = stomper.send("/app/answer/" + user_key, json.dumps({"camKey": "1234", "description": {"sdp":answer.sdp, "type": answer.type}}))
    await conn.send(answer_meg)


async def process_message(message):
    f = stomper.Frame()
    f.unpack(message)
    destination = f.headers.get("destination")
    if destination:
        if "offer" in destination:
            await handle_offer(f.body)
        elif "iceCandidate" in destination:
            print("iceCandidate message")


async def connect():
    global conn
    # 시그널링 서버 websocket 연결 & stomp 방식으로 채널 구독(test)
    ws_url = f"ws://{args.host}:{args.port}/signaling"
    ws_url_test = "ws://localhost:8080/signaling/websocket"
    async with websockets.connect(ws_url_test) as websocket:
        #TODO: conn 수정
        conn = websocket

        await websocket.send("CONNECT\naccept-version:1.0,1.1,2.0\n\n\x00\n")

        sub_offer = stomper.subscribe("/queue/offer/1234", idx="1234")
        await websocket.send(sub_offer)

        sub_ice = stomper.subscribe("/queue/iceCandidate/1234", idx="1234")
        await websocket.send(sub_ice)

        send = stomper.send("/app/initiate", "1234")
        await websocket.send(send)

        while True:
            message = await websocket.recv()
            await process_message(message)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="WebRTC webcam")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default:8080)"
    )

    args = parser.parse_args()

    asyncio.get_event_loop().run_until_complete(connect())