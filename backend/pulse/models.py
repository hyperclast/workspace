from django.db import models


class PulseMetric(models.Model):
    """Stores pre-computed metrics for the pulse dashboard."""

    metric_type = models.CharField(max_length=50, db_index=True)  # e.g., "dau"
    date = models.DateField(db_index=True)
    value = models.IntegerField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("metric_type", "date")
        ordering = ["-date"]

    def __str__(self):
        return f"{self.metric_type} on {self.date}: {self.value}"
