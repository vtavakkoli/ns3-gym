// SPDX-License-Identifier: GPL-2.0-only
#include "bridge.h"

#include <cerrno>
#include <stdexcept>
#include <string>
#include <zmq.h>

namespace vtns3gym {
Bridge::Bridge(uint16_t port, int timeoutMs)
    : m_context(zmq_ctx_new()),
      m_socket(nullptr)
{
    if (!m_context) {
        throw std::runtime_error("zmq_ctx_new failed");
    }
    m_socket = zmq_socket(m_context, ZMQ_REP);
    if (!m_socket) {
        zmq_ctx_term(m_context);
        throw std::runtime_error("zmq_socket failed");
    }
    const int linger = 0;
    zmq_setsockopt(m_socket, ZMQ_LINGER, &linger, sizeof(linger));
    zmq_setsockopt(m_socket, ZMQ_RCVTIMEO, &timeoutMs, sizeof(timeoutMs));
    zmq_setsockopt(m_socket, ZMQ_SNDTIMEO, &timeoutMs, sizeof(timeoutMs));
    const std::string endpoint = "tcp://127.0.0.1:" + std::to_string(port);
    if (zmq_bind(m_socket, endpoint.c_str()) != 0) {
        const std::string error = zmq_strerror(zmq_errno());
        zmq_close(m_socket);
        zmq_ctx_term(m_context);
        throw std::runtime_error("zmq_bind failed: " + error);
    }
}

Bridge::~Bridge()
{
    if (m_socket) { zmq_close(m_socket); }
    if (m_context) { zmq_ctx_term(m_context); }
}

std::string Bridge::Receive()
{
    zmq_msg_t msg;
    if (zmq_msg_init(&msg) != 0) {
        throw std::runtime_error("zmq_msg_init failed");
    }
    const int bytes = zmq_msg_recv(&msg, m_socket, 0);
    if (bytes < 0) {
        const std::string error = zmq_strerror(zmq_errno());
        zmq_msg_close(&msg);
        throw std::runtime_error("zmq receive failed: " + error);
    }
    const std::string payload(static_cast<const char*>(zmq_msg_data(&msg)),
                              static_cast<size_t>(bytes));
    zmq_msg_close(&msg);
    return payload;
}

void Bridge::Send(const std::string& payload)
{
    if (zmq_send(m_socket, payload.data(), payload.size(), 0) < 0) {
        throw std::runtime_error("zmq send failed: " + std::string(zmq_strerror(zmq_errno())));
    }
}
} // namespace vtns3gym
