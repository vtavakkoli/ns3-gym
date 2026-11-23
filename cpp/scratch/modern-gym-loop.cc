// SPDX-License-Identifier: GPL-2.0-only
// Real ns-3.49 two-node UDP experiment controlled step-by-step over
// ZeroMQ/Protocol Buffers. One new ns-3 process per Gymnasium reset.
#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/internet-module.h"
#include "ns3/gym.pb.h"
#include "ns3/bridge.h"

#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace ns3;

namespace {
uint64_t gReceivedPackets = 0;
uint64_t gReceivedBytes = 0;
uint64_t gTransmittedPackets = 0;

void ReceivePacket(Ptr<Socket> receiver)
{
    Address from;
    while (Ptr<Packet> packet = receiver->RecvFrom(from)) {
        ++gReceivedPackets;
        gReceivedBytes += packet->GetSize();
    }
}

void Transmit(Ptr<Socket> sender)
{
    const int n = sender->Send(Create<Packet>(256));
    if (n != 256) {
        throw std::runtime_error("UDP send failed: actual network tx not completed");
    }
    ++gTransmittedPackets;
}

void Reply(vtns3gym::Bridge& bridge, vtns3gym::Response& response,
           uint32_t step, uint64_t stepRx, uint64_t stepBytes, bool done)
{
    response.set_protocol_version(1);
    response.set_ok(true);
    response.add_observation(static_cast<double>(gReceivedPackets));
    response.add_observation(static_cast<double>(gTransmittedPackets));
    response.add_observation(static_cast<double>(step));
    response.set_episode_step(step);
    response.set_received_packets(gReceivedPackets);
    response.set_transmitted_packets(gTransmittedPackets);
    response.set_received_bytes(gReceivedBytes);
    response.set_step_received_packets(stepRx);
    response.set_reward(static_cast<double>(stepRx));
    response.set_throughput_mbps(static_cast<double>(stepBytes) * 8.0 / 0.1 / 1e6);
    response.set_terminated(done);
    std::string bytes;
    if (!response.SerializeToString(&bytes)) {
        throw std::runtime_error("Protobuf serialization failed");
    }
    bridge.Send(bytes);
}

void ErrorReply(vtns3gym::Bridge& bridge, const std::string& error)
{
    vtns3gym::Response response;
    response.set_protocol_version(1);
    response.set_ok(false);
    response.set_error(error);
    std::string bytes;
    response.SerializeToString(&bytes);
    bridge.Send(bytes);
}
} // namespace

int main(int argc, char* argv[])
{
    uint32_t port = 5555;
    uint32_t horizon = 5;
    CommandLine cmd(__FILE__);
    cmd.AddValue("port", "Loopback ZeroMQ port", port);
    cmd.AddValue("horizon", "Number of 100ms simulation steps", horizon);
    cmd.Parse(argc, argv);

    if (port == 0 || port > 65535 || horizon == 0 || horizon > 10000) {
        std::cerr << "Invalid port or horizon" << std::endl;
        return 2;
    }

    try {
        vtns3gym::Bridge bridge(static_cast<uint16_t>(port), 15000);
        vtns3gym::Request request;
        if (!request.ParseFromString(bridge.Receive()) ||
            request.protocol_version() != 1 ||
            request.command() != vtns3gym::Request::RESET) {
            ErrorReply(bridge, "First message must be protocol-v1 RESET");
            return 2;
        }

        // Reset is a fresh simulator process: no global ns-3 state is reused.
        RngSeedManager::SetSeed(static_cast<uint32_t>((request.seed() % 2147483646ULL) + 1ULL));
        RngSeedManager::SetRun(1);
        NodeContainer nodes;
        nodes.Create(2);

        PointToPointHelper link;
        link.SetDeviceAttribute("DataRate", StringValue("5Mbps"));
        link.SetChannelAttribute("Delay", StringValue("2ms"));
        NetDeviceContainer devices = link.Install(nodes);

        InternetStackHelper stack;
        stack.Install(nodes);
        Ipv4AddressHelper addressing;
        addressing.SetBase("10.1.1.0", "255.255.255.0");
        Ipv4InterfaceContainer ip = addressing.Assign(devices);

        Ptr<Socket> receiver =
            Socket::CreateSocket(nodes.Get(1), UdpSocketFactory::GetTypeId());
        if (receiver->Bind(InetSocketAddress(Ipv4Address::GetAny(), 9000)) < 0) {
            throw std::runtime_error("UDP receiver bind failed");
        }
        receiver->SetRecvCallback(MakeCallback(&ReceivePacket));

        Ptr<Socket> sender =
            Socket::CreateSocket(nodes.Get(0), UdpSocketFactory::GetTypeId());
        if (sender->Connect(InetSocketAddress(ip.GetAddress(1), 9000)) < 0) {
            throw std::runtime_error("UDP sender connect failed");
        }

        uint32_t step = 0;
        vtns3gym::Response response;
        Reply(bridge, response, step, 0, 0, false);
        while (step < horizon) {
            request.Clear();
            if (!request.ParseFromString(bridge.Receive()) ||
                request.protocol_version() != 1) {
                ErrorReply(bridge, "Invalid protobuf request/protocol version");
                continue;
            }
            if (request.command() == vtns3gym::Request::CLOSE) {
                ErrorReply(bridge, "closed");
                break;
            }
            if (request.command() != vtns3gym::Request::STEP ||
                request.action() > 5) {
                ErrorReply(bridge, "Expected STEP with discrete action 0..5");
                continue;
            }
            const uint64_t rxBefore = gReceivedPackets;
            const uint64_t bytesBefore = gReceivedBytes;
            for (uint32_t i = 0; i < request.action(); ++i) {
                Simulator::Schedule(MilliSeconds(2 + i * 2), &Transmit, sender);
            }
            // The ns-3 event scheduler advances 100 ms per Python action.
            Simulator::Stop(MilliSeconds(100));
            Simulator::Run();
            ++step;

            const uint64_t rxDelta = gReceivedPackets - rxBefore;
            const uint64_t bytesDelta = gReceivedBytes - bytesBefore;
            response.Clear();
            Reply(bridge, response, step, rxDelta, bytesDelta, step >= horizon);
        }
        sender->Close();
        receiver->Close();
        Simulator::Destroy();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Native ns-3 Gym bridge failed: " << error.what() << std::endl;
        Simulator::Destroy();
        return 3;
    }
}
