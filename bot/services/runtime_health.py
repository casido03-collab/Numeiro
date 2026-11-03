"""Traffic-independent liveness; dependency probes never run in HTTP healthcheck."""
import asyncio
import threading
import time

HEARTBEAT_INTERVAL = 15
HEARTBEAT_MAX_AGE = 90
DEPENDENCY_INTERVAL = 30
DEPENDENCY_MAX_AGE = 90
DEPENDENCY_TIMEOUT = 3
WATCHDOG_TIMEOUT = 1800
WATCHDOG_INTERVAL = 30
ACTIVE_WINDOW = 300


class RuntimeHealth:
    def __init__(self, monotonic=time.monotonic, wall=time.time):
        self.monotonic, self.wall = monotonic, wall
        self.lock = threading.Lock()
        self.started = monotonic()
        self.heartbeat = None
        self.heartbeat_utc = None
        self.activity = None
        self.activity_utc = None
        self.incoming_count = 0
        self.dependencies = {}
        self.watchdog_fired = False

    def beat(self):
        with self.lock:
            self.heartbeat, self.heartbeat_utc = self.monotonic(), self.wall()

    def incoming(self):
        # Timestamp/count only. Never retain Update, user ID, text or attachments.
        with self.lock:
            self.activity, self.activity_utc = self.monotonic(), self.wall()
            self.incoming_count += 1

    def dependency(self, name, ok):
        if name not in ('postgres', 'redis'):
            raise ValueError('UNKNOWN_DEPENDENCY')
        with self.lock:
            self.dependencies[name] = (bool(ok), self.monotonic(), self.wall())

    def watchdog_required(self):
        with self.lock:
            anchor = self.heartbeat if self.heartbeat is not None else self.started
            return self.monotonic() - anchor > WATCHDOG_TIMEOUT

    def watchdog_step(self, on_stall):
        with self.lock:
            anchor = self.heartbeat if self.heartbeat is not None else self.started
            if self.watchdog_fired or self.monotonic() - anchor <= WATCHDOG_TIMEOUT:
                return False
            self.watchdog_fired = True
        on_stall()
        return True

    def snapshot(self, scheduler_running=True, polling_running=True):
        with self.lock:
            now = self.monotonic()
            age = None if self.heartbeat is None else now - self.heartbeat
            activity_age = None if self.activity is None else now - self.activity
            deps = {}
            for name in ('postgres', 'redis'):
                row = self.dependencies.get(name)
                fresh = row is not None and now - row[1] <= DEPENDENCY_MAX_AGE
                deps[name] = {'ok': bool(row and row[0] and fresh),
                              'fresh': fresh, 'checkedAt': row[2] if row else None}
            anchor = self.heartbeat if self.heartbeat is not None else self.started
            if now - anchor > WATCHDOG_TIMEOUT:
                state = 'WATCHDOG_RESTART_REQUIRED'
            elif age is None or age > HEARTBEAT_MAX_AGE or not scheduler_running or not polling_running:
                state = 'UNHEALTHY_RUNTIME'
            elif not all(row['ok'] for row in deps.values()):
                state = 'DEGRADED_DEPENDENCY'
            else:
                state = 'HEALTHY_ACTIVE' if activity_age is not None and activity_age < ACTIVE_WINDOW else 'HEALTHY_IDLE'
            return {'state': state, 'healthy': state.startswith('HEALTHY_'),
                    'heartbeatAt': self.heartbeat_utc, 'heartbeatAgeSeconds': age,
                    'lastIncomingAt': self.activity_utc, 'lastIncomingAgeSeconds': activity_age,
                    'incomingCount': self.incoming_count, 'dependencies': deps,
                    'schedulerRunning': bool(scheduler_running), 'pollingRunning': bool(polling_running)}


async def heartbeat_loop(health):
    while True:
        health.beat()
        await asyncio.sleep(HEARTBEAT_INTERVAL)


async def dependency_loop(health, postgres_probe, redis_probe):
    while True:
        for name, probe in [('postgres', postgres_probe), ('redis', redis_probe)]:
            try:
                ok = await asyncio.wait_for(probe(), timeout=DEPENDENCY_TIMEOUT)
            except Exception:
                # Safe status only: exception strings can include connection secrets.
                ok = False
            health.dependency(name, ok)
        await asyncio.sleep(DEPENDENCY_INTERVAL)


def start_watchdog(health, stop, on_stall):
    # A coroutine watchdog cannot detect a blocked event loop; this thread can.
    def watch():
        while not stop.wait(WATCHDOG_INTERVAL):
            if health.watchdog_step(on_stall):
                return
    thread = threading.Thread(target=watch, name='runtime-watchdog', daemon=True)
    thread.start()
    return thread


async def internal_health_response(request, health, scheduler_running, polling_running):
    from aiohttp import web
    # Trust the peer address, never X-Forwarded-For. No public health internals.
    if request.remote not in ('127.0.0.1', '::1'):
        return web.json_response({'error': 'LOCAL_ONLY'}, status=403)
    result = health.snapshot(scheduler_running, polling_running)
    return web.json_response(result, status=200 if result['healthy'] else 503,
                             headers={'Cache-Control': 'no-store'})
