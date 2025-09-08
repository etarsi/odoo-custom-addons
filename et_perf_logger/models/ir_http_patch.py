import logging, os, time
from odoo import models
from odoo.http import request

try:
    import psutil
    import os as _os
    _PROC = psutil.Process(_os.getpid())
except Exception:
    _PROC = None

def _rss_mb():
    if _PROC:
        return _PROC.memory_info().rss / 1024 / 1024
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1.0

_logger = logging.getLogger("odoo.addons.et_perf_logger.http")

class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _dispatch(cls):
        pid = os.getpid()
        before = _rss_mb()
        t0 = time.time()
        try:
            return super()._dispatch()
        finally:
            after = _rss_mb()
            dt = time.time() - t0
            try:
                path = request.httprequest.path
                db = request.db
                uid = request.uid
            except Exception:
                path, db, uid = "?", "?", "?"
            _logger.info("HTTP pid=%s db=%s uid=%s path=%s rss=%.1fMB Δ=%.1fMB dur=%.3fs",
                         pid, db, uid, path, after, (after - before), dt)
