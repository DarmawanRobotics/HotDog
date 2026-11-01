"""Blocking service calls from a worker thread while the executor spins on other threads."""

from __future__ import annotations

import threading


def call(client, request, timeout: float):
    """Return (response, '') or (None, error); never raises, never blocks past timeout."""
    if not client.service_is_ready() and not client.wait_for_service(
        timeout_sec=min(timeout, 1.0)
    ):
        return None, f'{client.srv_name} not available'
    done = threading.Event()
    future = client.call_async(request)
    future.add_done_callback(lambda _f: done.set())
    if not done.wait(timeout):
        future.cancel()
        return None, f'{client.srv_name}: no answer within {timeout:.1f} s'
    try:
        return future.result(), ''
    except Exception as error:  # the service raised: rclpy hands it over here
        return None, f'{client.srv_name}: {error}'
