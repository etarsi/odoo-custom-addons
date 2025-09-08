import logging, os, time
from odoo import models

try:
    import psutil
    _PROC = psutil.Process(os.getpid())
except Exception:
    _PROC = None

def _rss_mb():
    if _PROC:
        return _PROC.memory_info().rss / 1024 / 1024
    try:
        import resource
        # En Linux ru_maxrss suele venir en KB
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1.0

_logger = logging.getLogger("odoo.addons.et_perf_logger.cron")

class IrCron(models.Model):
    _inherit = "ir.cron"

    def _process_job(self, job, lock_cr=None, cron=None):
        pid = os.getpid()
        before = _rss_mb()
        t0 = time.time()
        _logger.info("[CRON-START] pid=%s job_id=%s name=%s rss=%.1fMB",
                     pid, getattr(job, 'id', '?'), getattr(job, 'name', '?'), before)
        try:
            return super()._process_job(job, lock_cr=lock_cr, cron=cron)
        finally:
            after = _rss_mb()
            dt = time.time() - t0
            _logger.info("[CRON-END] pid=%s job_id=%s name=%s rss=%.1fMB Δ=%.1fMB dur=%.2fs",
                         pid, getattr(job, 'id', '?'), getattr(job, 'name', '?'),
                         after, (after - before), dt)
