import json
import cv2
import asyncio
import stomper
import argparse
import aiortc.sdp
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import VideoStreamTrack
from av import VideoFrame

conn = None
peer_map = {}


class WebcamVideoStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.track = cv2.VideoCapture(0)

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        res, img = self.track.read()
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
        def on_message(message):
            print(message)

    return peer


async def handle_offer(message_body):
    global conn
    message_body = json.loads(message_body)
    description = message_body["description"]
    user_key = message_body["userKey"]

    # offer 생성
    offer = RTCSessionDescription(sdp=description["sdp"], type=description["type"])

    # RTCPeerConnection 생성
    # TODO:여러 사람이 들어오는 경우 처리(멀티스레드?) - 우선은 한 사람과의 p2p 연결 및 트랙 전송 목표로
    local_peer = create_peer(user_key)

    peer_map[user_key] = local_peer
    await local_peer.setRemoteDescription(offer)

    # answer 전송
    answer = await local_peer.createAnswer()
    await local_peer.setLocalDescription(answer)

    answer_meg = stomper.send("/app/answer/" + user_key, json.dumps({"camKey": "1234", "description": {
        "sdp": local_peer.localDescription.sdp, "type": local_peer.localDescription.type}}))
    await conn.send(answer_meg)


async def handle_iceCandidate(message_body):
    global conn
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
    # 시그널링 서버 websocket 연결 & stomp 방식으로 채널 구독(test)
    ws_url = f"ws://{args.host}:{args.port}/signaling"
    ws_url_test = "ws://localhost:8080/signaling/websocket"
    async with websockets.connect(ws_url_test) as websocket:
        # TODO: conn 수정
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
