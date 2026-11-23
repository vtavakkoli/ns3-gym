"""Basic protocol contract checks; not a replacement for native tests."""
from vtns3gym import gym_pb2


def test_protocol_version_and_wire_fields():
    request = gym_pb2.Request(
        protocol_version=1, command=gym_pb2.Request.STEP, action=3
    )
    wire = request.SerializeToString()
    decoded = gym_pb2.Request()
    decoded.ParseFromString(wire)
    assert decoded.action == 3
    assert decoded.command == gym_pb2.Request.STEP


def test_response_contains_native_kpi_fields():
    response = gym_pb2.Response(
        protocol_version=1,
        ok=True,
        observation=[1.0, 2.0, 3.0],
        reward=2.0,
        received_packets=1,
        transmitted_packets=2,
        received_bytes=256,
        step_received_packets=1,
    )
    decoded = gym_pb2.Response()
    decoded.ParseFromString(response.SerializeToString())
    assert decoded.observation == [1.0, 2.0, 3.0]
    assert decoded.received_packets == 1
