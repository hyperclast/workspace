from django.core.management.base import BaseCommand

from pulse.tasks import compute_dau_metrics


class Command(BaseCommand):
    help = "Compute pulse metrics (DAU, etc.) synchronously"

    def handle(self, *args, **options):
        self.stdout.write("Computing pulse metrics...")
        compute_dau_metrics()
        self.stdout.write(self.style.SUCCESS("Pulse metrics computed successfully"))
