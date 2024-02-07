import cv2
import os
import json
import random
import string
import asyncio
import stomper
import argparse
import aiortc.sdp
import websockets
from abc import *
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import VideoStreamTrack
from av import VideoFrame

cam_key = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(10))
conn = None
peer_map = {}
track = cv2.VideoCapture(0)


class CommandHandler(metaclass = ABCMeta):
    def __init__(self) -> None:
        self.command = ""
    
    async def identify(self, message):
        return self.command == message

    @abstractmethod
    async def handle_command(self) -> str:
        pass


class quitCommandHandler(CommandHandler):
    def __init__(self) -> None:
        super().__init__()
        self.command = "quit"

    async def handle_command(self) -> str:
        try:
            os._exit(1)
        except:
            return "프로그램 종료 실패"


command_handler = [quitCommandHandler()]

class WebcamVideoStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        res, img = track.read()
        frame = VideoFrame.from_ndarray(img, format="bgr24")
        frame.pts = pts
        frame.time_base = time_base
        return frame


def create_peer(user_key):
    peer = RTCPeerConnection()

    peer.addTrack(WebcamVideoStreamTrack())

    @peer.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        ice_connection_state = peer.iceConnectionState
        if ice_connection_state == "completed":
            conn_meg = stomper.send("/app/connected", user_key)
            await conn.send(conn_meg)
        if ice_connection_state == "failed":
            disconn_msg = stomper.send("/app/disconnected", user_key)
            await conn.send(disconn_msg)
            peer_map.pop(user_key)


    @peer.on("datachannel")
    async def on_datachannel(channel):
        @channel.on("message")
        async def on_message(rev_message):
            flag = True
            for handler in command_handler:
                if await handler.identify(message=rev_message):
                    send_messgae = await handler.handle_command()
                    channel.send(send_messgae)
                    flag = False
            if (flag):
                channel.send("전송 성공")
            
    return peer


async def handle_offer(message_body):
    message_body = json.loads(message_body)
    description = message_body["description"]
    user_key = message_body["userKey"]

    # 받은 메시지로 offer 객체 생성
    offer = RTCSessionDescription(sdp=description["sdp"], type=description["type"])

    # RTCPeerConnection 생성
    local_peer = create_peer(user_key)
    peer_map[user_key] = local_peer

    # offer를 RTCPeerConnection에 추가
    await local_peer.setRemoteDescription(offer)

    # answer 전송, answer에 ice candidate까지 모두 전송 (trickle x)
    answer = await local_peer.createAnswer()
    await local_peer.setLocalDescription(answer)

    answer_meg = stomper.send("/app/answer/" + user_key, json.dumps({"camKey": cam_key, "description": {
        "sdp": local_peer.localDescription.sdp, "type": local_peer.localDescription.type}}))
    await conn.send(answer_meg)


async def handle_iceCandidate(message_body):
    # 들어온 ice candidate를 RTCPeerConnection에 추가
    message_body = json.loads(message_body)
    user_key = message_body["userKey"]
    description = message_body["description"]
    candidate = description["candidate"]
    candidate = candidate.replace("candidate:", "")

    candidate = aiortc.sdp.candidate_from_sdp(candidate)
    candidate.sdpMid = description["sdpMid"]
    candidate.sdpMLineIndex = description["sdpMLineIndex"]

    local_peer = peer_map.get(user_key)
    await local_peer.addIceCandidate(candidate)


async def process_message(message):
    # 메시지가 offer인지 ice candidate인지 구분
    f = stomper.Frame()
    f.unpack(message)
    destination = f.headers.get("destination")
    if destination:
        if "offer" in destination:
            await handle_offer(f.body)
        elif "iceCandidate" in destination:
            await handle_iceCandidate(f.body)


async def connect():
    global conn
    # 시그널링 서버 websocket 연결 & stomp 방식으로 채널 구독
    ws_url = f"ws://{args.host}:{args.port}/signaling/websocket"
    async with websockets.connect(ws_url) as websocket:
        conn = websocket

        await websocket.send("CONNECT\naccept-version:1.0,1.1,2.0\n\n\x00\n")

        sub_offer = stomper.subscribe("/queue/offer/" + cam_key, idx=cam_key)
        await websocket.send(sub_offer)

        sub_ice = stomper.subscribe("/queue/iceCandidate/" + cam_key, idx=cam_key)
        await websocket.send(sub_ice)

        send = stomper.send("/app/initiate", json.dumps({"camKey": cam_key, "display": args.display}))
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
    parser.add_argument(
        "--display", type=str, default=None, help="client display name"
    )

    args = parser.parse_args()

    asyncio.get_event_loop().run_until_complete(connect())
