"""Bounded loopback request proves the main event loop responds, not user traffic."""
import json
import sys
import urllib.request


def check(url='http://127.0.0.1:8081/_internal/health'):
    try:
        # Ignore proxy environment: this must be a direct localhost request.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=3) as response:
            if response.status != 200:
                return False
            body = response.read(16385)
            if len(body) > 16384:
                return False
            result = json.loads(body)
        return result.get('healthy') is True and result.get('state') in ('HEALTHY_IDLE', 'HEALTHY_ACTIVE')
    except Exception:
        return False


if __name__ == '__main__':
    sys.exit(0 if check() else 1)
