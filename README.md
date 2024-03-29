# WebRTC-aiortc

## [프로젝트 소개](https://github.com/jaeyeoneee/WebRTC)

 * 자율주행 자동차에서는 파이썬 프로그램을 실행한다.
 * 따라서 step1에서의 웹캠 측 자바스크립트 WebRTC를 파이썬 aiortc로 변경해야 한다.
 * 스프링 stomp로 구현된 시그널링 서버에 websockets로 연결하고, stomper 라이브러리로 구독, 전송과 관련된 메시지를 전송한다.
 * opencv로 가져온 영상을 aiortc를 이용한 P2P 연결을 통해 사용자에게 실시간 스트리밍한다.

#### step2. 추가 기능
 * 데이터 채널로 보낸 명령어가 핸들러의 command와 동일하다면 정의된 기능을 수행한다.

#### step2. 문제점
 * aiortc는 ice candidate가 trickle 방식으로 수신되는 것은 받을 수 있지만, trickle 방식으로 송신하는 것은 지원하지 않기 때문에 초기 연결 시 약간의 딜레이가 발생한다.
 * 연결 상태 변경 이벤트 리스너가 연결 끊김을 감지하기까지의 시간이 10초 이상 걸려, 사용자가 퇴장했음에도 웹캠은 이를 바로 알아차리지 못한다.

## Getting Started

This project has been tested with Python version 3.9.7.

### Installation
1. clone the repository
```bash
git clone https://github.com/jaeyeoneee/WebRTC-aiortc.git
cd WebRTC-aiortc
```
2. install the required dependencies
```bash
pip install -r requirement.txt
```
### Execution
To run the WebRTC-aiortc.py script, use the following command:

```bash
python WebRTC-aiortc.py --host <signaling_server_ip> --port <signaling_server_port> --display <your_display_name>
```
When successfully executed, webcam information is stored on the Spring Boot signaling server, enabling a peer-to-peer connection via WebRTC with users desiring streaming.