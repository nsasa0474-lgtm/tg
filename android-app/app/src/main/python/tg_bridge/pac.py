from __future__ import annotations


def build_pac(http_host: str, http_port: int, socks_host: str, socks_port: int) -> str:
    proxy_http = f"PROXY {http_host}:{http_port}"
    proxy_socks = f"SOCKS5 {socks_host}:{socks_port}"
    return f"""function FindProxyForURL(url, host) {{
  var h = host.toLowerCase();
  if (h === "localhost" || h === "127.0.0.1")
    return "DIRECT";
  if (dnsDomainIs(host, ".telegram.org") ||
      dnsDomainIs(host, ".telegram.me") ||
      dnsDomainIs(host, ".telegram-cdn.org") ||
      dnsDomainIs(host, ".t.me") ||
      host === "telegram.org" || host === "t.me")
    return "{proxy_http}; {proxy_socks}; DIRECT";
  return "DIRECT";
}}
"""
