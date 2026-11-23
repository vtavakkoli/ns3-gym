// SPDX-License-Identifier: GPL-2.0-only
#ifndef VT_NS3_GYM_BRIDGE_H
#define VT_NS3_GYM_BRIDGE_H

#include <cstdint>
#include <string>

namespace vtns3gym {
// Strict synchronous REQ/REP wire transport. Timeouts throw, never synthesize
// observations. The simulator owns the REP socket; Python owns REQ.
class Bridge
{
  public:
    explicit Bridge(uint16_t port, int timeoutMs = 15000);
    ~Bridge();
    Bridge(const Bridge&) = delete;
    Bridge& operator=(const Bridge&) = delete;
    std::string Receive();
    void Send(const std::string& payload);

  private:
    void* m_context;
    void* m_socket;
};
} // namespace vtns3gym
#endif
