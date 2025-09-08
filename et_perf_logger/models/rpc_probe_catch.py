# models/rpc_probe_patch.py
import logging, os, time
from odoo import models
from odoo.http import request
from odoo.service import model as service_model

try:
    import psutil
    _P = psutil.Process(os.getpid())
except Exception:
    _P = None

def _rss_mb():
    if _P:
        return _P.memory_info().rss / 1024 / 1024
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1.0

_logger = logging.getLogger("odoo.addons.et_perf_logger.rpc")

_orig_call_kw = service_model.call_kw

def _wrapped_call_kw(model, method, args, kwargs):
    pid = os.getpid()
    path = "rpc"
    db = getattr(request, "db", "?") if request else "?"
    uid = getattr(request, "uid", "?") if request else "?"
    before = _rss_mb()
    t0 = time.time()
    try:
        res = _orig_call_kw(model, method, args, kwargs)
        return res
    finally:
        after = _rss_mb()
        dt = time.time() - t0
        size = 0
        try:
            if method in ("search_read", "read", "read_group"):
                # estimar tamaño de respuesta
                if isinstance(res, (list, tuple)):
                    size = len(res)
                elif isinstance(res, dict) and "records" in res:
                    size = len(res["records"])
        except Exception:
            pass
        _logger.info(
            "RPC pid=%s db=%s uid=%s model=%s method=%s count=%s rss=%.1fMB Δ=%.1fMB dur=%.3fs",
            pid, db, uid, model, method, size, after, (after - before), dt
        )

class RpcProbe(models.AbstractModel):
    _name = "et.rpc.probe"
    _description = "ET RPC Probe"

    @classmethod
    def __init__(cls, pool, cr):
        super().__init__(pool, cr)
        # monkey patch una sola vez
        global _orig_call_kw
        if service_model.call_kw is not _wrapped_call_kw:
            service_model.call_kw = _wrapped_call_kw