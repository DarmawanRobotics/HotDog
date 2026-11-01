"""The words of the alerts, in English and Bahasa Indonesia."""

from __future__ import annotations

WORDS = {
    'en': {
        'normal': 'NORMAL',
        'attention': 'ATTENTION',
        'warning': 'WARNING',
        'critical': 'CRITICAL',
        'finding': '{sev} at {point}',
        'thermal': '{target} ({label}): {value} °C, {delta:+.1f} °C over {ref_name}',
        'absolute': '{target} ({label}): {value} °C',
        'acoustic': '{target}: {label} partial discharge, {value} dB',
        'ref_ambient': 'ambient',
        'ref_similar': 'the other phases',
        'act': {
            'attention': 'Look again on the next round.',
            'warning': 'Plan a repair.',
            'critical': 'Report to the substation now.',
        },
        'done': 'Patrol done: {points} points, worst {worst}',
        'failed': 'Patrol FAILED: {message}',
        'stopped': 'Patrol stopped: {message}',
        'returned': 'Back at the dock: {message}',
        'counts': '{critical} critical · {warning} warning · {attention} attention',
        'report': 'Report',
        'health': 'Robot health ERROR: {issues}',
        'test': 'Test alert: {robot} reaches this chat.',
        'site': 'site',
    },
    'id': {
        'normal': 'NORMAL',
        'attention': 'PERHATIAN',
        'warning': 'PERINGATAN',
        'critical': 'KRITIS',
        'finding': '{sev} di {point}',
        'thermal': '{target} ({label}): {value} °C, {delta:+.1f} °C di atas {ref_name}',
        'absolute': '{target} ({label}): {value} °C',
        'acoustic': '{target}: partial discharge {label}, {value} dB',
        'ref_ambient': 'suhu lingkungan',
        'ref_similar': 'fasa lain',
        'act': {
            'attention': 'Periksa lagi pada patroli berikutnya.',
            'warning': 'Jadwalkan perbaikan.',
            'critical': 'Segera laporkan ke petugas gardu induk.',
        },
        'done': 'Patroli selesai: {points} titik, terburuk {worst}',
        'failed': 'Patroli GAGAL: {message}',
        'stopped': 'Patroli dihentikan: {message}',
        'returned': 'Kembali ke dock: {message}',
        'counts': '{critical} kritis · {warning} peringatan · {attention} perhatian',
        'report': 'Laporan',
        'health': 'Kesehatan robot ERROR: {issues}',
        'test': 'Uji notifikasi: {robot} terhubung ke chat ini.',
        'site': 'lokasi',
    },
}
ICONS = {'normal': '🟢', 'attention': '🟡', 'warning': '🟠', 'critical': '🔴'}


def words(language: str) -> dict:
    """Return the words of a language (English when unknown)."""
    return WORDS.get(language, WORDS['en'])
